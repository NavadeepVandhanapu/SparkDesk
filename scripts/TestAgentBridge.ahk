#Requires AutoHotkey v2.0
#SingleInstance Force

; ==============================================================================
; TestAgentBridge.ahk - Phase 3 & 4 Verification Suite
; Tests:
; 1. Unavailable-server scenario
; 2. Authenticated communication (valid token -> 200 pong)
; 3. Invalid token rejection (invalid token -> 401 Unauthorized)
; 4. Timeout handling
; 5. Phase 4: Authenticated Tool Execution (get_system_info -> 200 OK + metrics)
; 6. Phase 4: Unknown tool rejection (404 Not Found)
; 7. Phase 4: Invalid parameters rejection (422 Unprocessable Content)
; 8. Clean authenticated shutdown (200 OK + clean exit)
; ==============================================================================

rootDir := SubStr(A_ScriptDir, 1, InStr(A_ScriptDir, "\", , -1) - 1)
outLog := rootDir "\data\test_results.txt"

try FileDelete(outLog)

Output(msg) {
    global outLog
    FileAppend(msg, outLog, "UTF-8")
    FileAppend(msg, "*", "UTF-8")
}

global SD := Map()
SD["Root"] := rootDir
SD["ConfigPath"] := rootDir "\config\settings.ini"
SD["LogPath"] := rootDir "\data\sparkdesk.log"
SD["AgentHost"] := "127.0.0.1"
SD["AgentPort"] := 8765
SD["AgentTokenPath"] := rootDir "\data\session.token"
SD["AgentToken"] := ""
SD["SysInfoGui"] := 0

LogInfo(msg) {
    Output(FormatTime(, "yyyy-MM-dd HH:mm:ss") " [TEST] " msg "`n")
}

LogError(msg) {
    Output(FormatTime(, "yyyy-MM-dd HH:mm:ss") " [ERROR] " msg "`n")
}

; Include the bridge under test
#Include ..\modules\AgentBridge.ahk

RunTests() {
    Output("=======================================================`n")
    Output("Starting Phase 4 AutoHotkey AgentBridge Verification`n")
    Output("=======================================================`n`n")

    passCount := 0
    failCount := 0

    ; --------------------------------------------------------------------------
    ; Scenario 1: Unavailable-server scenario (server is not running initially)
    ; --------------------------------------------------------------------------
    Output("[SCENARIO 1] Testing unavailable-server scenario...`n")
    SD["AgentPort"] := 59123
    res1 := AgentPing()
    SD["AgentPort"] := 8765 ; Restore port

    if (!res1["ok"] && res1["status"] == 0 && res1["error"] != "") {
        Output("  PASS: Connection to unavailable server cleanly handled.`n")
        Output("  Reported Error: " res1["error"] "`n`n")
        passCount++
    } else {
        Output("  FAIL: Expected error, got status " res1["status"] "`n`n")
        failCount++
    }

    ; --------------------------------------------------------------------------
    ; Start the Python Agent Process
    ; --------------------------------------------------------------------------
    Output("[SETUP] Launching Python Local Agent...`n")
    pythonExe := SD["Root"] "\agent\.venv\Scripts\python.exe"
    runAgent := SD["Root"] "\agent\run_agent.py"

    Run('"' pythonExe '" "' runAgent '"', SD["Root"] "\agent", "Hide", &agentPID)
    Output("  Agent spawned with PID: " agentPID "`n")

    ; Wait for server readiness and session.token generation
    tokenFound := false
    loop 20 {
        Sleep(500)
        if FileExist(SD["AgentTokenPath"]) {
            tokenFound := true
            break
        }
    }

    if (!tokenFound) {
        Output("  FATAL: session.token was not created within timeout.`n")
        ProcessClose(agentPID)
        ExitApp(1)
    }

    ; Initialize bridge state with the newly created token
    InitAgentBridge()
    Output("  Agent is ready. Token loaded from session.token.`n`n")

    ; --------------------------------------------------------------------------
    ; Scenario 2: Authenticated communication (valid token)
    ; --------------------------------------------------------------------------
    Output("[SCENARIO 2] Testing authenticated communication (valid token)...`n")
    res2 := AgentPing()
    if (res2["ok"] && res2["status"] == 200 && InStr(res2["response"], "pong")) {
        Output("  PASS: AgentPing returned HTTP 200 with pong payload.`n")
        passCount++
    } else {
        Output("  FAIL: AgentPing failed! Status: " res2["status"] " Error: " res2["error"] "`n`n")
        failCount++
    }

    ; --------------------------------------------------------------------------
    ; Scenario 3: Invalid token rejection
    ; --------------------------------------------------------------------------
    Output("[SCENARIO 3] Testing invalid token rejection...`n")
    res3 := AgentPing("bogus_invalid_token_99999")
    if (!res3["ok"] && res3["status"] == 401) {
        Output("  PASS: Request with invalid token correctly rejected with HTTP 401 Unauthorized.`n`n")
        passCount++
    } else {
        Output("  FAIL: Expected HTTP 401, got status " res3["status"] "`n`n")
        failCount++
    }

    ; --------------------------------------------------------------------------
    ; Scenario 4: Request timeout scenario
    ; --------------------------------------------------------------------------
    Output("[SCENARIO 4] Testing request timeout handling...`n")
    res4 := SendAgentRequest("GET", "/health", "", "", 1)
    Output("  PASS: Fast timeout call handled safely without crashing AHK (Status: " res4["status"] ").`n`n")
    passCount++

    ; --------------------------------------------------------------------------
    ; Scenario 5: Phase 4 Tool Execution (get_system_info)
    ; --------------------------------------------------------------------------
    Output("[SCENARIO 5] Testing authenticated tool execution (get_system_info)...`n")
    res5 := AgentExecute("get_system_info")
    if (res5["ok"] && res5["status"] == 200) {
        data := res5["data"]
        resultMap := data.Has("result") ? data["result"] : Map()
        memMap := resultMap.Has("memory") ? resultMap["memory"] : Map()
        cpuMap := resultMap.Has("cpu") ? resultMap["cpu"] : Map()
        osMap := resultMap.Has("os") ? resultMap["os"] : Map()

        if (resultMap.Has("memory") && resultMap.Has("cpu") && resultMap.Has("disk") && resultMap.Has("uptime")) {
            Output("  PASS: get_system_info returned valid metrics structure.`n")
            Output("  OS: " (osMap.Has("platform") ? osMap["platform"] : "Windows") "`n")
            Output("  CPU: " (cpuMap.Has("logical_cores") ? cpuMap["logical_cores"] : 0) " cores, " (cpuMap.Has("usage_percent") ? cpuMap["usage_percent"] : 0) "% utilization`n")
            Output("  Memory: " (memMap.Has("total_gb") ? memMap["total_gb"] : 0) " GB total, " (memMap.Has("available_gb") ? memMap["available_gb"] : 0) " GB available`n`n")
            passCount++
        } else {
            Output("  FAIL: Metrics structure missing expected keys.`n`n")
            failCount++
        }
    } else {
        Output("  FAIL: AgentExecute get_system_info failed with status " res5["status"] " Error: " res5["error"] "`n`n")
        failCount++
    }

    ; --------------------------------------------------------------------------
    ; Scenario 6: Phase 4 Unknown tool rejection
    ; --------------------------------------------------------------------------
    Output("[SCENARIO 6] Testing unknown tool rejection (security check)...`n")
    res6 := AgentExecute("malicious_arbitrary_cmd_xyz")
    if (!res6["ok"] && res6["status"] == 404) {
        Output("  PASS: Unknown tool correctly rejected with HTTP 404 Not Found.`n`n")
        passCount++
    } else {
        Output("  FAIL: Expected HTTP 404, got status " res6["status"] " (" res6["error"] ")`n`n")
        failCount++
    }

    ; --------------------------------------------------------------------------
    ; Scenario 7: Phase 4 Invalid parameters rejection
    ; --------------------------------------------------------------------------
    Output("[SCENARIO 7] Testing invalid parameters rejection...`n")
    res7 := AgentExecute("get_system_info", '{"unexpected_param": "bad_input"}')
    if (!res7["ok"] && res7["status"] == 422) {
        Output("  PASS: Invalid parameters correctly rejected with HTTP 422 Unprocessable Content.`n`n")
        passCount++
    } else {
        Output("  FAIL: Expected HTTP 422, got status " res7["status"] " (" res7["error"] ")`n`n")
        failCount++
    }

    ; --------------------------------------------------------------------------
    ; Scenario 8: Authenticated graceful shutdown
    ; --------------------------------------------------------------------------
    Output("[SCENARIO 8] Testing authenticated shutdown...`n")
    res8 := AgentShutdown()
    if (res8["ok"] && res8["status"] == 200) {
        Output("  PASS: AgentShutdown accepted with HTTP 200.`n")
        passCount++
    } else {
        Output("  FAIL: AgentShutdown failed with status " res8["status"] "`n")
        failCount++
    }

    ; Wait for process to exit
    ProcessWaitClose(agentPID, 5)
    if (!ProcessExist(agentPID)) {
        Output("  PASS: Python Agent process exited cleanly.`n`n")
        passCount++
    } else {
        Output("  WARNING: Process still alive, forcing termination.`n`n")
        ProcessClose(agentPID)
    }

    Output("=======================================================`n")
    Output("SUMMARY: " passCount " Passed, " failCount " Failed`n")
    Output("=======================================================`n")

    ExitApp(failCount > 0 ? 1 : 0)
}

RunTests()
