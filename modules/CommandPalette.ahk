InitCommandPalette() {
}

ShowCommandPalette() {
    global SD
    if IsObject(SD["PaletteGui"]) {
        try SD["PaletteGui"].Destroy()
    }

    palette := Gui("+AlwaysOnTop +ToolWindow", "SparkDesk Command Palette")
    palette.BackColor := "171A21"
    palette.SetFont("s10", "Segoe UI")

    palette.SetFont("s11 bold cF9FAFB", "Segoe UI")
    palette.AddText("xm cFFFFFF", "What would you like to do?")

    palette.SetFont("s9 c9CA3AF", "Segoe UI")
    palette.AddText("xm y+2", "Type a natural language request, or choose a shortcut below:")

    palette.SetFont("s10 cFFFFFF", "Segoe UI")
    palette.AddEdit("xm w420 vPromptInput Background20242D", "")

    palette.AddListBox("xm w420 r9 vCommandChoice", [
        "Open Dashboard",
        "System Information",
        "Ubuntu Server",
        "Coding Mode",
        "Study Mode",
        "Exam Mode",
        "Chill Mode",
        "Normal Mode",
        "Open Downloads folder",
        "Open SparkDesk data folder"
    ])
    palette["CommandChoice"].Choose(1)

    palette.SetFont("s9 bold", "Segoe UI")
    runButton := palette.AddButton("xm w120 Default", "Execute")
    runButton.OnEvent("Click", (*) => RunPaletteChoice(palette))

    palette["CommandChoice"].OnEvent("DoubleClick", (*) => RunDirectChoice(palette))
    palette.OnEvent("Escape", (*) => palette.Destroy())
    palette.OnEvent("Close", (*) => palette.Destroy())

    SD["PaletteGui"] := palette
    palette.Show("AutoSize Center")
}

RunPaletteChoice(palette) {
    userInput := Trim(palette["PromptInput"].Text)
    choice := palette["CommandChoice"].Text
    palette.Destroy()

    ; 1. If user typed a natural language query, route to intent engine
    if (userInput != "") {
        res := AgentProcessNaturalLanguage(userInput)
        ShowAssistantResponseGui(userInput, res["message"], res.Has("data") ? res["data"] : "")
        return
    }

    ; 2. Otherwise execute predefined palette choice
    DispatchPredefinedChoice(choice)
}

RunDirectChoice(palette) {
    choice := palette["CommandChoice"].Text
    palette.Destroy()
    DispatchPredefinedChoice(choice)
}

DispatchPredefinedChoice(choice) {
    switch choice {
        case "Open Dashboard": ShowDashboard()
        case "System Information": ShowSystemInfoGui()
        case "Ubuntu Server": RunUbuntuServer()
        case "Coding Mode": SetMode("Coding")
        case "Study Mode": SetMode("Study")
        case "Exam Mode": SetMode("Exam")
        case "Chill Mode": SetMode("Chill")
        case "Normal Mode": SetMode("Normal")
        case "Open Downloads folder": Run(EnvGet("USERPROFILE") "\Downloads")
        case "Open SparkDesk data folder": Run(A_ScriptDir "\data")
    }
}
