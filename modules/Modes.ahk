
InitModes() {
}

SetMode(modeName) {
    global SD

    allowed := ["Normal", "Coding", "Study", "Exam", "Chill"]
    valid := false

    for item in allowed {
        if (item = modeName) {
            valid := true
            break
        }
    }

    if !valid {
        LogError("Unknown mode: " modeName)
        return
    }

    SD["Mode"] := modeName
    LogInfo("Mode changed to " modeName)

    switch modeName {
        case "Coding":
            LaunchCodingWorkspace()

        case "Study":
            Run("https://www.google.com")

        case "Exam":
            Sleep(0)

        case "Chill":
            Run("https://www.youtube.com")

        case "Normal":
            Sleep(0)
    }

    ToolTip("SPARKDESK  |  " StrUpper(modeName) " MODE", 24, 24)
    SetTimer(ClearModeNotification, -1800)
}

LaunchCodingWorkspace() {
    antigravityPath := EnvGet("LOCALAPPDATA") "\Programs\Antigravity IDE\Antigravity IDE.exe"

    if FileExist(antigravityPath)
        Run('"' antigravityPath '"')
    else {
        MsgBox("Antigravity executable was not found:`n" antigravityPath, "SparkDesk")
        LogError("Antigravity not found: " antigravityPath)
    }

    Run("powershell.exe")
    Run("https://github.com")
}

ClearModeNotification() {
    ToolTip()
}
