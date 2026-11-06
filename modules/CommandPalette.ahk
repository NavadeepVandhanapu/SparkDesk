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
    palette.AddText("xm cFFFFFF", "What would you like to launch?")
    palette.AddListBox("xm w390 r9 vCommandChoice", [
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
    runButton := palette.AddButton("xm w120 Default", "Run")
    runButton.OnEvent("Click", (*) => RunPaletteChoice(palette))
    palette["CommandChoice"].OnEvent("DoubleClick", (*) => RunPaletteChoice(palette))
    palette.OnEvent("Escape", (*) => palette.Destroy())
    palette.OnEvent("Close", (*) => palette.Destroy())
    SD["PaletteGui"] := palette
    palette.Show("AutoSize Center")
}

RunPaletteChoice(palette) {
    choice := palette["CommandChoice"].Text
    palette.Destroy()
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
