#Requires AutoHotkey v2.0

; ==============================================================================
; SparkDesk AgentBridge (Phases 3, 4 & 5)
; Provides authenticated HTTP communication between AutoHotkey and the
; Python Local Agent via WinHttp.WinHttpRequest.5.1 on 127.0.0.1.
; Includes Tool Execution (AgentExecute), System Info GUI, and
; Natural Language Command Processing (AgentProcessNaturalLanguage).
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
    if !SD.Has("SysInfoGui")
        SD["SysInfoGui"] := 0
    if !SD.Has("AssistantGui")
        SD["AssistantGui"] := 0

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

DecodeUtf8ResponseBody(http) {
    try {
        body := http.ResponseBody
        stream := ComObject("ADODB.Stream")
        stream.Type := 1 ; adTypeBinary
        stream.Open()
        stream.Write(body)
        stream.Position := 0
        stream.Type := 2 ; adTypeText
        stream.Charset := "utf-8"
        text := stream.ReadText()
        stream.Close()
        return (text != "") ? text : ""
    } catch {
        try return http.ResponseText
        catch
            return ""
    }
}

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
            http.SetRequestHeader("Content-Type", "application/json; charset=utf-8")
            http.Send(payload)
        } else {
            http.Send()
        }

        result["status"] := http.Status
        result["response"] := DecodeUtf8ResponseBody(http)
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

; ------------------------------------------------------------------------------
; Phase 4: Authenticated Tool Execution
; ------------------------------------------------------------------------------

MapToJson(mapObj) {
    if (!IsObject(mapObj) || Type(mapObj) != "Map")
        return "{}"
    json := "{"
    first := true
    for key, val in mapObj {
        if (!first)
            json .= ", "
        first := false
        json .= '"' key '": '
        if (Type(val) == "String")
            json .= '"' EscapeJsonString(val) '"'
        else if (Type(val) == "Integer" || Type(val) == "Float")
            json .= val
        else if (val == true)
            json .= "true"
        else if (val == false)
            json .= "false"
        else
            json .= '""'
    }
    json .= "}"
    return json
}

AgentExecute(toolName, parameters := "", customToken := "", timeoutMs := 4000) {
    if (Type(parameters) == "Map")
        payload := '{"tool": "' toolName '", "parameters": ' MapToJson(parameters) '}'
    else if (parameters == "" || parameters == "{}" || Type(parameters) != "String")
        payload := '{"tool": "' toolName '", "parameters": {}}'
    else
        payload := '{"tool": "' toolName '", "parameters": ' parameters '}'

    result := SendAgentRequest("POST", "/ipc/execute", payload, customToken, timeoutMs)

    if (result["ok"]) {
        LogInfo("AgentExecute '" toolName "': Success (HTTP " result["status"] ")")
        try {
            result["data"] := SimpleJsonParse(result["response"])
        } catch {
            result["data"] := Map()
        }
    } else {
        LogError("AgentExecute '" toolName "': Failed (" result["error"] ")")
    }
    return result
}

; ------------------------------------------------------------------------------
; Phase 5: Natural Language Command Understanding & Processing
; ------------------------------------------------------------------------------

EscapeJsonString(str) {
    str := StrReplace(str, "\", "\\")
    str := StrReplace(str, '"', '\"')
    str := StrReplace(str, "`r", "\r")
    str := StrReplace(str, "`n", "\n")
    str := StrReplace(str, "`t", "\t")
    return str
}

AgentParseIntent(prompt, customToken := "", timeoutMs := 3000) {
    payload := '{"prompt": "' EscapeJsonString(prompt) '"}'
    result := SendAgentRequest("POST", "/ipc/intent", payload, customToken, timeoutMs)
    if (result["ok"]) {
        try result["data"] := SimpleJsonParse(result["response"])
        catch
            result["data"] := Map()
    }
    return result
}

AgentProcessNaturalLanguage(prompt, customToken := "") {
    ; Step 1: Query intent understanding from the Python Agent
    intentRes := AgentParseIntent(prompt, customToken)
    if (!intentRes["ok"]) {
        errMsg := (intentRes["status"] == 401)
            ? "Authentication error. The local agent rejected the session token."
            : "Could not reach SparkDesk Local Agent. Ensure the agent is running."
        return Map(
            "ok", false,
            "status", "error",
            "message", errMsg,
            "tool", "",
            "data", Map()
        )
    }

    intentData := intentRes.Has("data") ? intentRes["data"] : Map()
    intentStatus := intentData.Has("status") ? intentData["status"] : "unsupported"

    ; Step 2: Handle ambiguous and unsupported requests safely
    if (intentStatus == "ambiguous" || intentStatus == "unsupported") {
        msg := intentData.Has("message") ? intentData["message"] : "Command was not recognized."
        return Map(
            "ok", false,
            "status", intentStatus,
            "message", msg,
            "tool", "",
            "data", Map()
        )
    }

    ; Step 3: Execute tool ONLY through the existing authenticated /ipc/execute endpoint!
    toolName := intentData.Has("tool") ? intentData["tool"] : ""
    if (toolName == "") {
        return Map(
            "ok", false,
            "status", "error",
            "message", "Intent recognized but no corresponding tool was mapped.",
            "tool", "",
            "data", Map()
        )
    }

    ; Execute the tool via /ipc/execute
    toolParams := ""
    if (intentData.Has("parameters") && IsObject(intentData["parameters"]))
        toolParams := MapToJson(intentData["parameters"])

    execRes := AgentExecute(toolName, toolParams, customToken)
    if (!execRes["ok"]) {
        errDetail := ""
        if (execRes.Has("response") && execRes["response"] != "") {
            try {
                respMap := SimpleJsonParse(execRes["response"])
                if (respMap.Has("detail") && respMap["detail"] != "")
                    errDetail := respMap["detail"]
            }
        }
        if (errDetail == "")
            errDetail := execRes["error"]

        return Map(
            "ok", false,
            "status", "execution_error",
            "message", "Failed to execute tool '" toolName "': " errDetail,
            "tool", toolName,
            "data", Map()
        )
    }

    ; Step 4: Obtain human-readable response from the agent command pipeline
    cmdPayload := '{"prompt": "' EscapeJsonString(prompt) '"}'
    cmdRes := SendAgentRequest("POST", "/ipc/command", cmdPayload, customToken, 4000)
    formattedMsg := ""

    if (cmdRes["ok"]) {
        try {
            cmdData := SimpleJsonParse(cmdRes["response"])
            if cmdData.Has("message")
                formattedMsg := cmdData["message"]
        }
    }

    if (formattedMsg == "")
        formattedMsg := "Tool '" toolName "' executed successfully."

    return Map(
        "ok", true,
        "status", "recognized",
        "message", formattedMsg,
        "tool", toolName,
        "data", execRes["data"]
    )
}

; ------------------------------------------------------------------------------
; Assistant Natural Language Response GUI
; ------------------------------------------------------------------------------

ShowAssistantResponseGui(prompt, message, toolData := "") {
    global SD

    if IsObject(SD["AssistantGui"]) {
        try SD["AssistantGui"].Destroy()
    }

    respGui := Gui("+AlwaysOnTop +Resize +MinSize560x360", "SparkDesk Assistant")
    respGui.BackColor := "111318"
    respGui.SetFont("s10", "Segoe UI")

    ; Header
    respGui.SetFont("s16 bold cF3F4F6", "Segoe UI")
    respGui.AddText("x24 y18 w510 h28", "SparkDesk Assistant")

    respGui.SetFont("s9 c9CA3AF", "Segoe UI")
    respGui.AddText("x26 y48 w510 h20", "QUERY: " SubStr(prompt, 1, 60))

    ; Output Box
    respGui.SetFont("s10 cF9FAFB", "Segoe UI")
    outputEdit := respGui.AddEdit("x24 y76 w512 h210 ReadOnly Background20242D", message)

    ; Action Buttons
    hasSysInfo := (IsObject(toolData) && toolData.Has("result") && toolData["result"].Has("memory"))

    if (hasSysInfo) {
        diagBtn := respGui.AddButton("x24 y300 w170 h30", "Open Diagnostics GUI")
        diagBtn.OnEvent("Click", (*) => (respGui.Destroy(), ShowSystemInfoGui()))
    }

    copyBtn := respGui.AddButton(hasSysInfo ? "x204 y300 w130 h30" : "x24 y300 w130 h30", "Copy Response")
    copyBtn.OnEvent("Click", (*) => (A_Clipboard := message, ToolTip("Response copied to clipboard!", 24, 24), SetTimer(() => ToolTip(), -1500)))

    closeBtn := respGui.AddButton(hasSysInfo ? "x344 y300 w90 h30" : "x164 y300 w90 h30", "Close")
    closeBtn.OnEvent("Click", (*) => respGui.Destroy())

    respGui.OnEvent("Close", (*) => (SD["AssistantGui"] := 0))
    SD["AssistantGui"] := respGui
    respGui.Show("w560 h350 Center")
}

; ------------------------------------------------------------------------------
; System Information GUI (Displaying results in native SparkDesk UI)
; ------------------------------------------------------------------------------

ShowSystemInfoGui() {
    global SD

    if IsObject(SD["SysInfoGui"]) {
        try SD["SysInfoGui"].Destroy()
    }

    infoGui := Gui("+Resize +MinSize640x520", "SparkDesk - System Information")
    infoGui.BackColor := "111318"
    infoGui.SetFont("s10", "Segoe UI")

    ; Title Header
    infoGui.SetFont("s18 bold cF3F4F6", "Segoe UI")
    infoGui.AddText("x26 y20 w450 h32", "System Diagnostics")

    infoGui.SetFont("s9 c9CA3AF", "Segoe UI")
    infoGui.AddText("x28 y54 w400 h20", "LIVE METRICS VIA PYTHON LOCAL AGENT")

    statusLabel := infoGui.AddText("x460 y26 w150 h22 Right c86EFAC", "● AGENT CONNECTED")

    ; Fetch system information from agent
    res := AgentExecute("get_system_info")

    if (!res["ok"]) {
        statusLabel.Text := "● AGENT OFFLINE"
        statusLabel.SetFont("cEF4444")

        infoGui.SetFont("s11 bold cF87171", "Segoe UI")
        infoGui.AddText("x28 y100 w580 h30", "Could not retrieve system metrics.")

        infoGui.SetFont("s9 cD1D5DB", "Segoe UI")
        infoGui.AddText("x28 y135 w580 h60", "Error Details: " res["error"] "`n`nEnsure the SparkDesk Python agent is running on 127.0.0.1.")

        retryBtn := infoGui.AddButton("x28 y210 w120 h30", "Retry")
        retryBtn.OnEvent("Click", (*) => ShowSystemInfoGui())

        closeBtn := infoGui.AddButton("x160 y210 w100 h30", "Close")
        closeBtn.OnEvent("Click", (*) => infoGui.Destroy())

        SD["SysInfoGui"] := infoGui
        infoGui.Show("w640 h320 Center")
        return
    }

    data := res["data"]
    resMap := data.Has("result") ? data["result"] : Map()

    ; Extract sections with defaults
    osMap := resMap.Has("os") ? resMap["os"] : Map()
    cpuMap := resMap.Has("cpu") ? resMap["cpu"] : Map()
    memMap := resMap.Has("memory") ? resMap["memory"] : Map()
    diskMap := resMap.Has("disk") ? resMap["disk"] : Map()
    upMap := resMap.Has("uptime") ? resMap["uptime"] : Map()

    ; 1. OS Card
    AddMetricCard(infoGui, 26, 90, 588, 70, "OPERATING SYSTEM",
        (osMap.Has("platform") ? osMap["platform"] : "Windows") . " (" . (osMap.Has("architecture") ? osMap["architecture"] : "64bit") . ")",
        "Kernel Version: " . (osMap.Has("version") ? osMap["version"] : "Unknown"))

    ; 2. CPU Card
    cpuUsage := cpuMap.Has("usage_percent") ? cpuMap["usage_percent"] : 0
    cores := cpuMap.Has("logical_cores") ? cpuMap["logical_cores"] : 1
    AddMetricCard(infoGui, 26, 170, 288, 76, "CPU METRICS",
        cpuUsage . "% Utilization",
        cores . " Logical Cores  •  " . (cpuMap.Has("processor") ? SubStr(cpuMap["processor"], 1, 32) : "CPU"))

    ; 3. Memory Card
    memUsage := memMap.Has("usage_percent") ? memMap["usage_percent"] : 0
    memUsed := memMap.Has("used_gb") ? memMap["used_gb"] : 0
    memTotal := memMap.Has("total_gb") ? memMap["total_gb"] : 0
    memAvail := memMap.Has("available_gb") ? memMap["available_gb"] : 0
    AddMetricCard(infoGui, 326, 170, 288, 76, "MEMORY (RAM)",
        memUsed . " GB / " . memTotal . " GB (" . memUsage . "%)",
        memAvail . " GB Available")

    ; 4. Disk Card
    diskUsage := diskMap.Has("usage_percent") ? diskMap["usage_percent"] : 0
    diskUsed := diskMap.Has("used_gb") ? diskMap["used_gb"] : 0
    diskTotal := diskMap.Has("total_gb") ? diskMap["total_gb"] : 0
    diskFree := diskMap.Has("free_gb") ? diskMap["free_gb"] : 0
    diskDrive := diskMap.Has("drive") ? diskMap["drive"] : "C:\"
    AddMetricCard(infoGui, 26, 256, 288, 76, "PRIMARY STORAGE (" . diskDrive . ")",
        diskUsed . " GB / " . diskTotal . " GB (" . diskUsage . "%)",
        diskFree . " GB Free Space")

    ; 5. Uptime Card
    uptimeStr := upMap.Has("uptime_formatted") ? upMap["uptime_formatted"] : "Unknown"
    bootTime := upMap.Has("boot_time") ? SubStr(upMap["boot_time"], 1, 19) : "Unknown"
    AddMetricCard(infoGui, 326, 256, 288, 76, "SYSTEM UPTIME",
        uptimeStr,
        "Boot Time (UTC): " . bootTime)

    ; Bottom action buttons
    refreshBtn := infoGui.AddButton("x26 y350 w120 h32", "Refresh")
    refreshBtn.OnEvent("Click", (*) => ShowSystemInfoGui())

    closeBtn := infoGui.AddButton("x156 y350 w100 h32", "Close")
    closeBtn.OnEvent("Click", (*) => infoGui.Destroy())

    infoGui.OnEvent("Close", (*) => (SD["SysInfoGui"] := 0))
    SD["SysInfoGui"] := infoGui
    infoGui.Show("w640 h410 Center")
}

AddMetricCard(guiObj, x, y, w, h, headerText, primaryText, subText) {
    guiObj.AddText("x" x " y" y " w" w " h" h " Background20242D Border", "")

    guiObj.SetFont("s8 bold c9CA3AF", "Segoe UI")
    guiObj.AddText("x" (x + 12) " y" (y + 8) " w" (w - 24) " h16", headerText)

    guiObj.SetFont("s11 bold cF9FAFB", "Segoe UI")
    guiObj.AddText("x" (x + 12) " y" (y + 26) " w" (w - 24) " h22", primaryText)

    guiObj.SetFont("s8 cD1D5DB", "Segoe UI")
    guiObj.AddText("x" (x + 12) " y" (y + 50) " w" (w - 24) " h18", subText)
}

; ------------------------------------------------------------------------------
; Lightweight Robust JSON Parser for AutoHotkey v2
; ------------------------------------------------------------------------------

SimpleJsonParse(str) {
    str := Trim(str)
    pos := 1
    return _JsonParseValue(str, &pos)
}

_JsonSkipWhitespace(str, &pos) {
    while (pos <= StrLen(str) && InStr(" `t`r`n", SubStr(str, pos, 1)))
        pos++
}

_JsonParseValue(str, &pos) {
    _JsonSkipWhitespace(str, &pos)
    if (pos > StrLen(str))
        return ""

    char := SubStr(str, pos, 1)

    if (char = "{")
        return _JsonParseObject(str, &pos)
    if (char = "[")
        return _JsonParseArray(str, &pos)
    if (char = '"')
        return _JsonParseString(str, &pos)
    if (InStr("-0123456789.", char))
        return _JsonParseNumber(str, &pos)
    if (SubStr(str, pos, 4) = "true") {
        pos += 4
        return true
    }
    if (SubStr(str, pos, 5) = "false") {
        pos += 5
        return false
    }
    if (SubStr(str, pos, 4) = "null") {
        pos += 4
        return ""
    }
    return ""
}

_JsonParseObject(str, &pos) {
    obj := Map()
    pos++ ; Skip '{'

    loop {
        _JsonSkipWhitespace(str, &pos)
        if (pos > StrLen(str) || SubStr(str, pos, 1) = "}") {
            pos++
            break
        }

        if (SubStr(str, pos, 1) != '"')
            break

        key := _JsonParseString(str, &pos)
        _JsonSkipWhitespace(str, &pos)

        if (SubStr(str, pos, 1) = ":")
            pos++

        val := _JsonParseValue(str, &pos)
        obj[key] := val

        _JsonSkipWhitespace(str, &pos)
        if (SubStr(str, pos, 1) = ",")
            pos++
        else if (SubStr(str, pos, 1) = "}") {
            pos++
            break
        }
    }
    return obj
}

_JsonParseArray(str, &pos) {
    arr := []
    pos++ ; Skip '['

    loop {
        _JsonSkipWhitespace(str, &pos)
        if (pos > StrLen(str) || SubStr(str, pos, 1) = "]") {
            pos++
            break
        }

        val := _JsonParseValue(str, &pos)
        arr.Push(val)

        _JsonSkipWhitespace(str, &pos)
        if (SubStr(str, pos, 1) = ",")
            pos++
        else if (SubStr(str, pos, 1) = "]") {
            pos++
            break
        }
    }
    return arr
}

_JsonParseString(str, &pos) {
    pos++ ; Skip opening '"'
    start := pos
    out := ""

    while (pos <= StrLen(str)) {
        char := SubStr(str, pos, 1)
        if (char = "\") {
            out .= SubStr(str, start, pos - start)
            pos++
            nextChar := SubStr(str, pos, 1)
            switch nextChar {
                case '"', "\", "/": out .= nextChar
                case "b": out .= "`b"
                case "f": out .= "`f"
                case "n": out .= "`n"
                case "r": out .= "`r"
                case "t": out .= "`t"
                case "u":
                    hexStr := SubStr(str, pos + 1, 4)
                    if RegExMatch(hexStr, "^[0-9a-fA-F]{4}$") {
                        codePoint := Integer("0x" hexStr)
                        ; Handle UTF-16 surrogate pairs (e.g. \uD83D\uDE80 -> emoji)
                        if (codePoint >= 0xD800 && codePoint <= 0xDBFF && SubStr(str, pos + 5, 2) = "\u") {
                            lowHex := SubStr(str, pos + 7, 4)
                            if RegExMatch(lowHex, "^[0-9a-fA-F]{4}$") {
                                lowPoint := Integer("0x" lowHex)
                                if (lowPoint >= 0xDC00 && lowPoint <= 0xDFFF) {
                                    fullCodePoint := 0x10000 + ((codePoint - 0xD800) << 10) + (lowPoint - 0xDC00)
                                    out .= Chr(fullCodePoint)
                                    pos += 11
                                    start := pos
                                    continue
                                }
                            }
                        }
                        out .= Chr(codePoint)
                        pos += 4
                    } else {
                        out .= nextChar
                    }
                default: out .= nextChar
            }
            pos++
            start := pos
        } else if (char = '"') {
            out .= SubStr(str, start, pos - start)
            pos++
            return out
        } else {
            pos++
        }
    }
    return out
}

_JsonParseNumber(str, &pos) {
    start := pos
    while (pos <= StrLen(str) && InStr("-+0123456789.eE", SubStr(str, pos, 1)))
        pos++
    numStr := SubStr(str, start, pos - start)
    return InStr(numStr, ".") ? Float(numStr) : Integer(numStr)
}
