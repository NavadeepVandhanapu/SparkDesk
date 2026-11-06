#Requires AutoHotkey v2.0

; ==============================================================================
; SparkDesk AgentBridge (Phase 3)
; Provides authenticated HTTP communication between AutoHotkey and the
; Python Local Agent via WinHttp.WinHttpRequest.5.1 on 127.0.0.1.
; ==============================================================================

InitAgentBridge() {
    global SD

    if !SD.Has("AgentHost")
        SD["AgentHost"] := "127.0.0.1"
    if !SD.Has("AgentPort")
        SD["AgentPort"] := 8765
    if !SD.Has("AgentTokenPath")
        SD["AgentTokenPath"] := A_ScriptDir "\data\session.token"
    if !SD.Has("AgentToken")
        SD["AgentToken"] := ""
    if !SD.Has("AgentPID")
        SD["AgentPID"] := 0

    ; Read optional overrides from config/settings.ini
    if FileExist(SD["ConfigPath"]) {
        try {
            iniPort := IniRead(SD["ConfigPath"], "Agent", "Port", "")
            if (iniPort != "" && IsInteger(iniPort))
                SD["AgentPort"] := Integer(iniPort)
        }
    }

    ; Attempt to load token if file is present
    GetAgentToken()
    LogInfo("AgentBridge initialized for http://" SD["AgentHost"] ":" SD["AgentPort"])
}

; ------------------------------------------------------------------------------
; Token Management
; ------------------------------------------------------------------------------

GetAgentToken() {
    global SD
    tokenPath := SD.Has("AgentTokenPath") ? SD["AgentTokenPath"] : (A_ScriptDir "\data\session.token")

    if FileExist(tokenPath) {
        try {
            rawToken := FileRead(tokenPath, "UTF-8")
            SD["AgentToken"] := Trim(rawToken, " `t`r`n")
            return SD["AgentToken"]
        } catch as err {
            LogError("AgentBridge could not read session token: " err.Message)
        }
    }
    return SD.Has("AgentToken") ? SD["AgentToken"] : ""
}

; ------------------------------------------------------------------------------
; HTTP Request Transport via WinHttp.WinHttpRequest.5.1
; ------------------------------------------------------------------------------

SendAgentRequest(method, endpoint, payload := "", customToken := "", timeoutMs := 2000) {
    global SD

    host := SD.Has("AgentHost") ? SD["AgentHost"] : "127.0.0.1"
    port := SD.Has("AgentPort") ? SD["AgentPort"] : 8765
    url := "http://" host ":" port endpoint

    result := Map(
        "ok", false,
        "status", 0,
        "response", "",
        "error", "",
        "url", url
    )

    try {
        http := ComObject("WinHttp.WinHttpRequest.5.1")
        http.Open(method, url, false) ; Synchronous request

        ; Timeouts in milliseconds: resolve (500), connect (1000), send (timeoutMs), receive (timeoutMs)
        http.SetTimeouts(500, 1000, timeoutMs, timeoutMs)

        ; Resolve token: customToken overrides stored session token
        token := (customToken != "") ? customToken : GetAgentToken()
        if (token != "")
            http.SetRequestHeader("X-SparkDesk-Token", token)

        if (payload != "") {
            http.SetRequestHeader("Content-Type", "application/json")
            http.Send(payload)
        } else {
            http.Send()
        }

        result["status"] := http.Status
        result["response"] := http.ResponseText
        result["ok"] := (http.Status >= 200 && http.Status < 300)

        if (!result["ok"])
            result["error"] := "HTTP " http.Status ": " http.StatusText
    } catch as err {
        result["ok"] := false
        result["status"] := 0
        result["error"] := err.Message
    }

    return result
}

; ------------------------------------------------------------------------------
; Core Bridge Functions
; ------------------------------------------------------------------------------

AgentPing(customToken := "") {
    result := SendAgentRequest("GET", "/ipc/ping", "", customToken)
    if (result["ok"])
        LogInfo("AgentPing: Success (Status 200)")
    else
        LogError("AgentPing: Failed (" result["error"] ")")
    return result
}

AgentHealth() {
    return SendAgentRequest("GET", "/health", "", "", 1500)
}

AgentShutdown(customToken := "") {
    result := SendAgentRequest("POST", "/shutdown", "", customToken)
    if (result["ok"]) {
        LogInfo("AgentShutdown: Clean shutdown requested successfully.")
        global SD
        if SD.Has("AgentToken")
            SD["AgentToken"] := ""
    } else {
        LogError("AgentShutdown: Failed (" result["error"] ")")
    }
    return result
}
