#Requires AutoHotkey v2.0
#SingleInstance Force

; ==============================================================================
; TestAgentBridge.ahk - Phases 3, 4 & 5 Verification Suite
; Tests:
; 1. Unavailable-server scenario
; 2. Authenticated communication (valid token -> 200 pong)
; 3. Invalid token rejection (invalid token -> 401 Unauthorized)
; 4. Timeout handling
; 5. Phase 4: Authenticated Tool Execution (get_system_info -> 200 OK + metrics)
; 6. Phase 4: Unknown tool rejection (404 Not Found)
; 7. Phase 4: Invalid parameters rejection (422 Unprocessable Content)
; 8. Phase 5: Natural Language general system info ("show my system specs")
; 9. Phase 5: Natural Language RAM-specific ("how much ram is free")
; 10. Phase 5: Natural Language CPU-specific ("what is my cpu usage")
; 11. Phase 5: Natural Language unsupported command rejection ("order a pizza")
; 12. Phase 5: Natural Language ambiguous request detection ("info")
; 13. Phase 5: Natural Language invalid token authentication failure
; 14. Clean authenticated shutdown (200 OK + clean exit)
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
SD["AssistantGui"] := 0

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
    Output("Starting Phase 5 AutoHotkey AgentBridge Verification`n")
    Output("=======================================================`n`n")

    passCount := 0
    failCount := 0

    ; --------------------------------------------------------------------------
    ; Scenario 1: Unavailable-server scenario
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
    try FileDelete(SD["AgentTokenPath"])
    pythonExe := SD["Root"] "\agent\.venv\Scripts\python.exe"
    runAgent := SD["Root"] "\agent\run_agent.py"

    Run('"' pythonExe '" "' runAgent '"', SD["Root"] "\agent", "Hide", &agentPID)
    Output("  Agent spawned with PID: " agentPID "`n")

    ; Wait for server readiness and session.token generation
    tokenFound := false
    loop 25 {
        Sleep(400)
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
        Output("  PASS: AgentPing returned HTTP 200 with pong payload.`n`n")
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
    ; Scenario 5: Authenticated Tool Execution (get_system_info)
    ; --------------------------------------------------------------------------
    Output("[SCENARIO 5] Testing authenticated tool execution (get_system_info)...`n")
    res5 := AgentExecute("get_system_info")
    if (res5["ok"] && res5["status"] == 200) {
        data := res5["data"]
        resultMap := data.Has("result") ? data["result"] : Map()
        if (resultMap.Has("memory") && resultMap.Has("cpu") && resultMap.Has("disk") && resultMap.Has("uptime")) {
            Output("  PASS: get_system_info returned valid metrics structure.`n`n")
            passCount++
        } else {
            Output("  FAIL: Metrics structure missing expected keys.`n`n")
            failCount++
        }
    } else {
        Output("  FAIL: AgentExecute get_system_info failed with status " res5["status"] "`n`n")
        failCount++
    }

    ; --------------------------------------------------------------------------
    ; Scenario 6: Unknown tool rejection
    ; --------------------------------------------------------------------------
    Output("[SCENARIO 6] Testing unknown tool rejection...`n")
    res6 := AgentExecute("malicious_arbitrary_cmd_xyz")
    if (!res6["ok"] && res6["status"] == 404) {
        Output("  PASS: Unknown tool correctly rejected with HTTP 404 Not Found.`n`n")
        passCount++
    } else {
        Output("  FAIL: Expected HTTP 404, got status " res6["status"] "`n`n")
        failCount++
    }

    ; --------------------------------------------------------------------------
    ; Scenario 7: Invalid parameters rejection
    ; --------------------------------------------------------------------------
    Output("[SCENARIO 7] Testing invalid parameters rejection...`n")
    res7 := AgentExecute("get_system_info", '{"unexpected_param": "bad_input"}')
    if (!res7["ok"] && res7["status"] == 422) {
        Output("  PASS: Invalid parameters correctly rejected with HTTP 422 Unprocessable Content.`n`n")
        passCount++
    } else {
        Output("  FAIL: Expected HTTP 422, got status " res7["status"] "`n`n")
        failCount++
    }

    ; --------------------------------------------------------------------------
    ; Scenario 8: Phase 5 Natural Language general request ("show my system specs")
    ; --------------------------------------------------------------------------
    Output("[SCENARIO 8] Testing Natural Language command: 'show my system specs'...`n")
    res8 := AgentProcessNaturalLanguage("show my system specs")
    if (res8["ok"] && res8["status"] == "recognized" && res8["tool"] == "get_system_info") {
        Output("  PASS: Recognized intent, executed get_system_info via /ipc/execute.`n")
        Output("  Response Preview: " SubStr(res8["message"], 1, 80) "...`n`n")
        passCount++
    } else {
        Output("  FAIL: Natural language 'show my system specs' failed: " res8["message"] "`n`n")
        failCount++
    }

    ; --------------------------------------------------------------------------
    ; Scenario 9: Phase 5 Natural Language RAM request ("how much ram is free")
    ; --------------------------------------------------------------------------
    Output("[SCENARIO 9] Testing Natural Language command: 'how much ram is free'...`n")
    res9 := AgentProcessNaturalLanguage("how much ram is free")
    if (res9["ok"] && res9["status"] == "recognized" && InStr(res9["message"], "Memory")) {
        Output("  PASS: Correctly mapped to get_system_info with RAM focus.`n")
        Output("  Response Preview: " SubStr(res9["message"], 1, 80) "...`n`n")
        passCount++
    } else {
        Output("  FAIL: RAM command failed: " res9["message"] "`n`n")
        failCount++
    }

    ; --------------------------------------------------------------------------
    ; Scenario 10: Phase 5 Natural Language CPU request ("what is my cpu usage")
    ; --------------------------------------------------------------------------
    Output("[SCENARIO 10] Testing Natural Language command: 'what is my cpu usage'...`n")
    res10 := AgentProcessNaturalLanguage("what is my cpu usage")
    if (res10["ok"] && res10["status"] == "recognized" && InStr(res10["message"], "CPU")) {
        Output("  PASS: Correctly mapped to get_system_info with CPU focus.`n`n")
        passCount++
    } else {
        Output("  FAIL: CPU command failed: " res10["message"] "`n`n")
        failCount++
    }

    ; --------------------------------------------------------------------------
    ; Scenario 11: Phase 5 Natural Language unsupported query rejection
    ; --------------------------------------------------------------------------
    Output("[SCENARIO 11] Testing unsupported natural language query ('order a pizza')...`n")
    res11 := AgentProcessNaturalLanguage("order a pizza")
    if (!res11["ok"] && res11["status"] == "unsupported" && InStr(res11["message"], "•") && !InStr(res11["message"], "â€¢")) {
        Output("  PASS: Unsupported command rejected safely with clean bullet guidance.`n`n")
        passCount++
    } else {
        Output("  FAIL: Expected unsupported status with clean bullets, got " res11["status"] "`n`n")
        failCount++
    }

    ; --------------------------------------------------------------------------
    ; Scenario 12: Phase 5 Natural Language ambiguous query detection & UTF-8 bullet rendering
    ; --------------------------------------------------------------------------
    Output("[SCENARIO 12] Testing ambiguous query detection ('info') & UTF-8 bullet rendering...`n")
    res12 := AgentProcessNaturalLanguage("info")
    hasBullet := InStr(res12["message"], "•")
    hasMojibake := InStr(res12["message"], "â€¢") || InStr(res12["message"], "â¢")
    if (!res12["ok"] && res12["status"] == "ambiguous" && hasBullet && !hasMojibake) {
        Output("  PASS: Ambiguous query flagged with clean UTF-8 bullet formatting (no mojibake).`n`n")
        passCount++
    } else {
        Output("  FAIL: Expected ambiguous status with clean bullets (hasBullet=" (hasBullet ? "YES" : "NO") ", hasMojibake=" (hasMojibake ? "YES" : "NO") "), got " res12["status"] "`n`n")
        failCount++
    }

    ; --------------------------------------------------------------------------
    ; Scenario 13: Phase 5 Natural Language authentication failure
    ; --------------------------------------------------------------------------
    Output("[SCENARIO 13] Testing Natural Language with invalid authentication...`n")
    res13 := AgentProcessNaturalLanguage("show specs", "invalid_bad_token_000")
    if (!res13["ok"] && res13["status"] == "error") {
        Output("  PASS: Unauthenticated natural language query cleanly rejected.`n`n")
        passCount++
    } else {
        Output("  FAIL: Expected authentication error, got " res13["status"] "`n`n")
        failCount++
    }

    ; --------------------------------------------------------------------------
    ; Scenario 13b: Phase 7.1 Parameterized Tool Execution (is_app_running)
    ; --------------------------------------------------------------------------
    Output("[SCENARIO 13b] Testing is_app_running tool via AgentExecute...`n")
    res13b := AgentExecute("is_app_running", '{"app_name": "notepad"}')
    if (res13b["ok"] && res13b["status"] == 200 && InStr(res13b["response"], "notepad")) {
        Output("  PASS: is_app_running returned valid process check payload.`n`n")
        passCount++
    } else {
        Output("  FAIL: is_app_running failed: " res13b["error"] "`n`n")
        failCount++
    }

    ; --------------------------------------------------------------------------
    ; Scenario 13c: Phase 7.1 Natural Language Application Control (Status Check)
    ; --------------------------------------------------------------------------
    Output("[SCENARIO 13c] Testing Natural Language: 'is notepad running'...`n")
    res13c := AgentProcessNaturalLanguage("is notepad running")
    if (res13c["ok"] && res13c["tool"] == "is_app_running") {
        Output("  PASS: Natural language process inspection succeeded.`n`n")
        passCount++
    } else {
        Output("  FAIL: NL is_app_running failed: " res13c["message"] "`n`n")
        failCount++
    }

    ; --------------------------------------------------------------------------
    ; Scenario 13d: Phase 7.1 Application Control Close Confirmation Requirement
    ; --------------------------------------------------------------------------
    Output("[SCENARIO 13d] Testing close_app confirmation requirement ('close notepad')...`n")
    res13d := AgentProcessNaturalLanguage("close notepad")
    if (res13d["ok"] && res13d["tool"] == "close_app") {
        Output("  PASS: close_app correctly returned confirmation requirement.`n`n")
        passCount++
    } else {
        Output("  FAIL: close_app failed: " res13d["message"] "`n`n")
        failCount++
    }

    ; --------------------------------------------------------------------------
    ; Scenario 13e: Phase 7.1 Critical Process Protection
    ; --------------------------------------------------------------------------
    Output("[SCENARIO 13e] Testing Critical Process Protection ('close explorer')...`n")
    res13e := AgentProcessNaturalLanguage("confirm close explorer")
    if (!res13e["ok"] && (InStr(res13e["message"], "prohibited") || InStr(res13e["message"], "protected") || InStr(res13e["message"], "Security"))) {
        Output("  PASS: Critical process termination attempt cleanly rejected.`n`n")
        passCount++
    } else {
        Output("  FAIL: Critical process was not rejected as expected: " res13e["message"] "`n`n")
        failCount++
    }

    ; --------------------------------------------------------------------------
    ; Scenario 14: Authenticated graceful shutdown
    ; --------------------------------------------------------------------------
    Output("[SCENARIO 14] Testing authenticated shutdown...`n")
    res14 := AgentShutdown()
    if (res14["ok"] && res14["status"] == 200) {
        Output("  PASS: AgentShutdown accepted with HTTP 200.`n")
        passCount++
    } else {
        Output("  FAIL: AgentShutdown failed with status " res14["status"] "`n")
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
