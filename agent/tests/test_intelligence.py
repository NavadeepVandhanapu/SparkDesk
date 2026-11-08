"""Comprehensive tests for Phase 6 Intelligence Architecture.

Verifies:
1. BaseIntelligenceProvider abstraction, provider registration, and custom provider swapping.
2. RuleBasedIntelligenceProvider classification, response formatting, and context-aware follow-ups.
3. TaskPlanner execution plan generation for recognized, ambiguous, and unsupported requests.
4. PlanValidator security validation, tool allow-list enforcement, parameter schema checks,
   and command/code injection prevention.
5. ConversationContext, ConversationTurn, and ContextManager session state isolation and history pruning.
6. End-to-end IntelligencePipeline orchestration with context updates and error isolation.
7. Authenticated /ipc/context endpoints (GET and DELETE).
"""

from typing import Any, Dict, Optional
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from sparkdesk_agent.core.config import AgentSettings
from sparkdesk_agent.intelligence.context import (
    ContextManager,
    ConversationContext,
    ConversationTurn,
)
from sparkdesk_agent.intelligence.pipeline import IntelligencePipeline
from sparkdesk_agent.intelligence.planner import (
    ExecutionPlan,
    PlanStatus,
    PlanStep,
    TaskPlanner,
)
from sparkdesk_agent.intelligence.provider import (
    BaseIntelligenceProvider,
    RuleBasedIntelligenceProvider,
    get_provider,
    register_provider,
)
from sparkdesk_agent.intelligence.validator import (
    PlanValidationError,
    PlanValidator,
)
from sparkdesk_agent.intent.models import CommandRequest, CommandResponse, IntentResult, IntentStatus
from sparkdesk_agent.ipc.auth import TOKEN_HEADER_NAME, get_active_token
from sparkdesk_agent.ipc.server import create_app
from sparkdesk_agent.tools.registry import ToolRegistry, registry as default_registry


# ==============================================================================
# 1. Intelligence Provider Interface & Implementation Tests
# ==============================================================================

class DummyMockProvider(BaseIntelligenceProvider):
    """Mock provider to verify model-independent interface extensibility."""

    @property
    def name(self) -> str:
        return "mock_test_provider"

    async def understand(
        self,
        prompt: str,
        context: Optional[ConversationContext] = None,
    ) -> IntentResult:
        if "custom_action" in prompt:
            return IntentResult(
                status=IntentStatus.RECOGNIZED,
                intent="custom_intent",
                tool="get_system_info",
                parameters={},
                confidence=0.99,
            )
        return IntentResult(
            status=IntentStatus.UNSUPPORTED,
            message="Mock cannot process this prompt.",
            confidence=0.0,
        )

    async def format_response(
        self,
        intent: IntentResult,
        tool_result: Any,
        context: Optional[ConversationContext] = None,
    ) -> str:
        return f"Mock response for intent '{intent.intent}'"


def test_provider_registration_and_retrieval() -> None:
    """Verify that custom providers can be registered and fetched by name."""
    mock = DummyMockProvider()
    register_provider("mock_test", mock)
    retrieved = get_provider("mock_test")
    assert retrieved is mock
    assert retrieved.name == "mock_test_provider"


def test_unknown_provider_raises_error() -> None:
    """Verify requesting an unlisted provider raises ValueError."""
    with pytest.raises(ValueError, match="Unknown intelligence provider"):
        get_provider("non_existent_provider_xyz")


@pytest.mark.anyio
async def test_rule_based_provider_recognizes_system_info() -> None:
    """Verify default rule-based provider analyzes system info commands."""
    provider = RuleBasedIntelligenceProvider()
    assert provider.name == "rule_based"

    result = await provider.understand("what is my memory usage")
    assert result.status == IntentStatus.RECOGNIZED
    assert result.intent == "get_system_info"
    assert result.tool == "get_system_info"
    assert result.focus == "memory"


# ==============================================================================
# 2. Conversation Context Support Tests
# ==============================================================================

def test_conversation_context_turn_management() -> None:
    """Verify turns are properly appended, retrieved, and cleared in context."""
    ctx = ConversationContext(session_id="session_abc")
    assert ctx.session_id == "session_abc"
    assert len(ctx.turns) == 0
    assert ctx.last_turn() is None

    # Add turn 1
    t1 = ctx.add_turn(
        user_prompt="check my ram",
        response_message="RAM is 8 GB free",
        intent="get_system_info",
        tool="get_system_info",
        focus="memory",
        tool_result={"memory": {"free_gb": 8}},
    )
    assert len(ctx.turns) == 1
    assert ctx.last_tool() == "get_system_info"
    assert ctx.last_focus() == "memory"
    assert ctx.last_tool_result() == {"memory": {"free_gb": 8}}
    assert ctx.last_turn() == t1

    # Add turn 2
    ctx.add_turn(
        user_prompt="what about cpu?",
        response_message="CPU is at 15%",
        intent="get_system_info",
        tool="get_system_info",
        focus="cpu",
    )
    assert len(ctx.turns) == 2
    assert ctx.last_focus() == "cpu"

    # History summary
    hist = ctx.get_history(max_turns=5)
    assert len(hist) == 2
    assert hist[0]["user"] == "check my ram"
    assert hist[1]["user"] == "what about cpu?"

    # Clear context
    ctx.clear()
    assert len(ctx.turns) == 0
    assert ctx.last_turn() is None


def test_context_manager_session_isolation_and_pruning() -> None:
    """Verify ContextManager creates distinct sessions and respects turn limits."""
    mgr = ContextManager(max_turns_per_session=3)

    ctx_a = mgr.get_or_create("user_alpha")
    ctx_b = mgr.get_or_create("user_beta")
    assert ctx_a is not ctx_b
    assert ctx_a.session_id == "user_alpha"
    assert ctx_b.session_id == "user_beta"

    # Add 4 turns to session A (limit is 3)
    for i in range(4):
        ctx_a.add_turn(f"prompt {i}", f"response {i}")

    # Re-retrieve and check that turns were pruned to 3
    ctx_a_pruned = mgr.get_or_create("user_alpha")
    assert len(ctx_a_pruned.turns) == 3
    assert ctx_a_pruned.turns[0].user_prompt == "prompt 1"
    assert ctx_a_pruned.turns[-1].user_prompt == "prompt 3"

    # Verify session B is untouched
    assert len(ctx_b.turns) == 0

    # Test clear and remove
    assert mgr.clear("user_alpha") is True
    assert len(ctx_a.turns) == 0
    assert mgr.remove("user_alpha") is True
    assert "user_alpha" not in mgr.list_sessions()


@pytest.mark.anyio
async def test_contextual_followup_resolution() -> None:
    """Verify RuleBasedIntelligenceProvider resolves follow-ups using prior context."""
    provider = RuleBasedIntelligenceProvider()
    ctx = ConversationContext(session_id="followup_test")

    # Turn 1: User asks for RAM
    ctx.add_turn(
        user_prompt="check memory",
        response_message="8 GB RAM free",
        intent="get_system_info",
        tool="get_system_info",
        focus="memory",
    )

    # Turn 2: Follow-up asking "what about cpu?"
    result_cpu = await provider.understand("what about cpu?", ctx)
    assert result_cpu.status == IntentStatus.RECOGNIZED
    assert result_cpu.tool == "get_system_info"
    assert result_cpu.focus == "cpu"

    # Turn 3: Follow-up asking "and disk storage?"
    result_disk = await provider.understand("and storage space?", ctx)
    assert result_disk.status == IntentStatus.RECOGNIZED
    assert result_disk.tool == "get_system_info"
    assert result_disk.focus == "disk"

    # Turn 4: Follow-up asking "check again"
    result_repeat = await provider.understand("refresh", ctx)
    assert result_repeat.status == IntentStatus.RECOGNIZED
    assert result_repeat.tool == "get_system_info"


# ==============================================================================
# 3. Task Planner Tests
# ==============================================================================

def test_task_planner_recognized_intent() -> None:
    """Verify TaskPlanner produces an executable ExecutionPlan for recognized intent."""
    planner = TaskPlanner()
    intent = IntentResult(
        status=IntentStatus.RECOGNIZED,
        intent="get_system_info",
        tool="get_system_info",
        parameters={},
        confidence=0.95,
        focus="memory",
    )
    plan = planner.create_plan(intent)

    assert plan.is_executable() is True
    assert plan.status == PlanStatus.DRAFT
    assert plan.intent == "get_system_info"
    assert plan.focus == "memory"
    assert len(plan.steps) == 1
    assert plan.steps[0].step_id == 1
    assert plan.steps[0].tool == "get_system_info"
    assert plan.steps[0].parameters == {}
    assert "get_system_info" in plan.rationale


def test_task_planner_ambiguous_and_unsupported_intents() -> None:
    """Verify TaskPlanner rejects ambiguous and unsupported requests without steps."""
    planner = TaskPlanner()

    # Ambiguous
    ambiguous_intent = IntentResult(
        status=IntentStatus.AMBIGUOUS,
        message="Did you mean system info?",
        confidence=0.4,
    )
    plan_amb = planner.create_plan(ambiguous_intent)
    assert plan_amb.is_executable() is False
    assert plan_amb.status == PlanStatus.REJECTED
    assert len(plan_amb.steps) == 0

    # Unsupported
    unsupported_intent = IntentResult(
        status=IntentStatus.UNSUPPORTED,
        message="I cannot order pizza.",
        confidence=0.0,
    )
    plan_unsup = planner.create_plan(unsupported_intent)
    assert plan_unsup.is_executable() is False
    assert plan_unsup.status == PlanStatus.REJECTED
    assert len(plan_unsup.steps) == 0


# ==============================================================================
# 4. Plan Validator & Security Tests
# ==============================================================================

def test_validator_accepts_valid_plan() -> None:
    """Verify validator approves a valid plan matching ToolRegistry definitions."""
    validator = PlanValidator(tool_registry=default_registry)
    plan = ExecutionPlan(
        intent="get_system_info",
        steps=[PlanStep(step_id=1, tool="get_system_info", parameters={})],
    )
    validated = validator.validate(plan)
    assert validated.status == PlanStatus.VALIDATED


def test_validator_rejects_unregistered_tool() -> None:
    """Verify validator strictly rejects any tool not registered in ToolRegistry."""
    validator = PlanValidator(tool_registry=default_registry)
    plan = ExecutionPlan(
        intent="arbitrary_cmd",
        steps=[PlanStep(step_id=1, tool="unregistered_dangerous_tool", parameters={})],
    )
    with pytest.raises(PlanValidationError, match="not registered in ToolRegistry"):
        validator.validate(plan)


def test_validator_rejects_invalid_tool_parameters() -> None:
    """Verify validator rejects plans where parameters fail tool schema validation."""
    validator = PlanValidator(tool_registry=default_registry)
    # get_system_info accepts NO parameters
    plan = ExecutionPlan(
        intent="get_system_info",
        steps=[PlanStep(step_id=1, tool="get_system_info", parameters={"unsupported_key": "val"})],
    )
    with pytest.raises(PlanValidationError, match="accepts no parameters"):
        validator.validate(plan)


def test_validator_rejects_step_limit_exceeded() -> None:
    """Verify validator enforces max_steps threshold to prevent resource exhaustion."""
    validator = PlanValidator(tool_registry=default_registry, max_steps=2)
    plan = ExecutionPlan(
        intent="multi_step",
        steps=[
            PlanStep(step_id=1, tool="get_system_info", parameters={}),
            PlanStep(step_id=2, tool="get_system_info", parameters={}),
            PlanStep(step_id=3, tool="get_system_info", parameters={}),
        ],
    )
    with pytest.raises(PlanValidationError, match="limit exceeded"):
        validator.validate(plan)


@pytest.mark.parametrize(
    "dangerous_payload",
    [
        "; rm -rf /",
        "&& powershell.exe -Command Write-Host PWNED",
        "eval('__import__(\"os\").system(\"calc\")')",
        "__import__('os').system('whoami')",
        "subprocess.Popen(['calc.exe'])",
        "`powershell Start-Process notepad`",
        "$(whoami)",
    ],
)
def test_validator_blocks_code_and_command_injection(dangerous_payload: str) -> None:
    """Security test: Ensure PlanValidator blocks shell command and python code injection."""
    # Register a temporary parameterized tool for testing
    test_reg = ToolRegistry()

    class ParamModel(BaseModel):
        query: str

    @test_reg.register("search_tool", "A test search tool", ParamModel)
    def dummy_search(query: str) -> str:
        return f"result: {query}"

    validator = PlanValidator(tool_registry=test_reg)

    plan = ExecutionPlan(
        intent="search",
        steps=[PlanStep(step_id=1, tool="search_tool", parameters={"query": dangerous_payload})],
    )
    with pytest.raises(PlanValidationError, match="Security violation|forbidden code execution"):
        validator.validate(plan)


# ==============================================================================
# 5. Intelligence Pipeline End-to-End Tests
# ==============================================================================

@pytest.mark.anyio
async def test_pipeline_end_to_end_success() -> None:
    """Verify full pipeline flow: understand -> plan -> validate -> execute -> format -> context."""
    pipe = IntelligencePipeline()
    req = CommandRequest(prompt="show my cpu usage", session_id="test_pipe_session")

    resp = await pipe.process(req)
    assert resp.success is True
    assert resp.status == "recognized"
    assert resp.intent == "get_system_info"
    assert resp.tool == "get_system_info"
    assert "Processor" in resp.message
    assert resp.plan_id is not None
    assert resp.session_id == "test_pipe_session"

    # Verify context was updated
    ctx = pipe.context_manager.get("test_pipe_session")
    assert ctx is not None
    assert len(ctx.turns) == 1
    assert ctx.last_focus() == "cpu"


@pytest.mark.anyio
async def test_pipeline_ambiguous_request_handling() -> None:
    """Verify pipeline cleanly handles ambiguous requests without executing tools."""
    pipe = IntelligencePipeline()
    req = CommandRequest(prompt="info", session_id="test_amb_session")

    resp = await pipe.process(req)
    assert resp.success is False
    assert resp.status == "ambiguous"
    assert resp.tool is None
    assert "ambiguous" in resp.message.lower()

    # Context records the interaction
    ctx = pipe.context_manager.get("test_amb_session")
    assert ctx is not None
    assert len(ctx.turns) == 1


@pytest.mark.anyio
async def test_pipeline_unsupported_request_handling() -> None:
    """Verify pipeline cleanly handles unsupported requests safely."""
    pipe = IntelligencePipeline()
    req = CommandRequest(prompt="bake a cake", session_id="test_unsup_session")

    resp = await pipe.process(req)
    assert resp.success is False
    assert resp.status == "unsupported"
    assert resp.tool is None

    # Context records the interaction
    ctx = pipe.context_manager.get("test_unsup_session")
    assert ctx is not None
    assert len(ctx.turns) == 1


# ==============================================================================
# 6. HTTP API Integration & Context Endpoints Tests
# ==============================================================================

def test_http_context_endpoints_authenticated() -> None:
    """Verify GET and DELETE /ipc/context endpoints with valid authentication."""
    app = create_app(AgentSettings(debug=True))
    with TestClient(app) as client:
        token = get_active_token()
        headers = {TOKEN_HEADER_NAME: token}

        # 1. Send a command to populate context
        cmd_res = client.post(
            "/ipc/command",
            headers=headers,
            json={"prompt": "check ram", "session_id": "api_test_session"},
        )
        assert cmd_res.status_code == 200
        assert cmd_res.json()["success"] is True

        # 2. Query GET /ipc/context
        ctx_res = client.get(
            "/ipc/context?session_id=api_test_session",
            headers=headers,
        )
        assert ctx_res.status_code == 200
        data = ctx_res.json()
        assert data["session_id"] == "api_test_session"
        assert data["turns_count"] == 1
        assert data["last_focus"] == "memory"
        assert len(data["history"]) == 1

        # 3. Query DELETE /ipc/context
        del_res = client.delete(
            "/ipc/context?session_id=api_test_session",
            headers=headers,
        )
        assert del_res.status_code == 200
        assert del_res.json()["cleared"] is True

        # Verify context is now empty
        ctx_after = client.get(
            "/ipc/context?session_id=api_test_session",
            headers=headers,
        )
        assert ctx_after.status_code == 200
        assert ctx_after.json()["turns_count"] == 0


def test_http_context_endpoints_unauthenticated_rejection() -> None:
    """Verify unauthenticated requests to /ipc/context are rejected with 401."""
    app = create_app(AgentSettings(debug=True))
    with TestClient(app) as client:
        # Missing token
        res_missing = client.get("/ipc/context")
        assert res_missing.status_code == 401

        # Invalid token
        res_invalid = client.get("/ipc/context", headers={TOKEN_HEADER_NAME: "wrong_token"})
        assert res_invalid.status_code == 401

