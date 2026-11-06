#Requires AutoHotkey v2.0
#SingleInstance Force
Persistent

; SparkDesk - personal automation dashboard

global SD := Map()
SD["Root"] := A_ScriptDir
SD["ConfigPath"] := A_ScriptDir "\config\settings.ini"
SD["LogPath"] := A_ScriptDir "\data\sparkdesk.log"
SD["Mode"] := "Normal"
SD["PaletteGui"] := 0
SD["DashboardGui"] := 0

for folder in ["config", "modules", "data", "scripts"] {
    path := A_ScriptDir "\" folder
    if !DirExist(path)
        DirCreate(path)
}

InitLogging()

try {
    InitConfig()
    InitCommandPalette()
    InitModes()
    InitClipboardTools()
    InitAgentBridge()
    InitDashboard()
    BuildTrayMenu()
    LogInfo("SparkDesk started successfully.")
    TrayTip("Your automation hub is running.", "SparkDesk")
    ShowDashboard()
} catch as err {
    LogError("Startup failure: " err.Message " | What: " err.What " | Extra: " err.Extra)
    MsgBox("SparkDesk could not start.`n`n" err.Message "`n`nDetails saved to:`n" SD["LogPath"], "SparkDesk error", "Iconx")
    ExitApp()
}

InitConfig() {
    global SD
    if !FileExist(SD["ConfigPath"])
        IniWrite("true", SD["ConfigPath"], "General", "ShowStartupNotification")
}

InitLogging() {
    global SD
    if !FileExist(SD["LogPath"])
        FileAppend("", SD["LogPath"], "UTF-8")
}

LogInfo(message) {
    global SD
    try FileAppend(FormatTime(, "yyyy-MM-dd HH:mm:ss") " [INFO] " message "`n", SD["LogPath"], "UTF-8")
}

LogError(message) {
    global SD
    try FileAppend(FormatTime(, "yyyy-MM-dd HH:mm:ss") " [ERROR] " message "`n", SD["LogPath"], "UTF-8")
}

BuildTrayMenu() {
    A_TrayMenu.Delete()
    A_TrayMenu.Add("Open SparkDesk dashboard", (*) => ShowDashboard())
    A_TrayMenu.Add("Open command palette", (*) => ShowCommandPalette())
    A_TrayMenu.Add()
    A_TrayMenu.Add("Mode: Normal", (*) => SetMode("Normal"))
    A_TrayMenu.Add("Mode: Coding", (*) => SetMode("Coding"))
    A_TrayMenu.Add("Mode: Study", (*) => SetMode("Study"))
    A_TrayMenu.Add("Mode: Exam", (*) => SetMode("Exam"))
    A_TrayMenu.Add("Mode: Chill", (*) => SetMode("Chill"))
    A_TrayMenu.Add()
    A_TrayMenu.Add("Test Agent Ping", (*) => PingAgentTrayHandler())
    A_TrayMenu.Add("Open data folder", (*) => Run(A_ScriptDir "\data"))
    A_TrayMenu.Add("Reload SparkDesk", (*) => Reload())
    A_TrayMenu.Add()
    A_TrayMenu.Add("Exit SparkDesk", (*) => ExitApp())
}

PingAgentTrayHandler() {
    res := AgentPing()
    if res["ok"]
        TrayTip("Agent is connected (pong received).", "SparkDesk Agent")
    else
        TrayTip("Agent ping failed: " res["error"], "SparkDesk Agent", "Icon!")
}

#Include modules\CommandPalette.ahk
#Include modules\Modes.ahk
#Include modules\ClipboardTools.ahk
#Include modules\UbuntuAutomation.ahk
#Include modules\Dashboard.ahk
#Include modules\Hotkeys.ahk
#Include modules\AgentBridge.ahk