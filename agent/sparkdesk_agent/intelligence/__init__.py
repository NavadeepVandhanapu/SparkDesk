"""SparkDesk Intelligence Architecture Package (Phase 6).

Provides:
- BaseIntelligenceProvider & RuleBasedIntelligenceProvider
- TaskPlanner, ExecutionPlan, PlanStep, PlanStatus
- PlanValidator & PlanValidationError
- ConversationContext, ConversationTurn, ContextManager
- IntelligencePipeline
"""

from sparkdesk_agent.intelligence.context import (
    ContextManager,
    ConversationContext,
    ConversationTurn,
    context_manager,
)
from sparkdesk_agent.intelligence.pipeline import (
    IntelligencePipeline,
    pipeline,
)
from sparkdesk_agent.intelligence.planner import (
    ExecutionPlan,
    PlanStatus,
    PlanStep,
    TaskPlanner,
    task_planner,
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
    plan_validator,
)

__all__ = [
    "BaseIntelligenceProvider",
    "RuleBasedIntelligenceProvider",
    "get_provider",
    "register_provider",
    "TaskPlanner",
    "ExecutionPlan",
    "PlanStep",
    "PlanStatus",
    "task_planner",
    "PlanValidator",
    "PlanValidationError",
    "plan_validator",
    "ConversationContext",
    "ConversationTurn",
    "ContextManager",
    "context_manager",
    "IntelligencePipeline",
    "pipeline",
]

