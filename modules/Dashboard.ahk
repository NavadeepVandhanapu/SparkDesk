
InitDashboard() {
}

ShowDashboard() {
    global SD

    if IsObject(SD["DashboardGui"]) {
        try SD["DashboardGui"].Destroy()
    }

    dashboardGui := Gui("+Resize +MinSize720x560", "SparkDesk")
    dashboardGui.BackColor := "111318"
    dashboardGui.SetFont("s10", "Segoe UI")

    dashboardGui.SetFont("s19 bold cF3F4F6", "Segoe UI")
    dashboardGui.AddText("x28 y22 w420 h34", "SparkDesk")

    dashboardGui.SetFont("s9 c9CA3AF", "Segoe UI")
    dashboardGui.AddText("x30 y60 w500 h22", "YOUR PERSONAL AUTOMATION WORKSPACE")
    dashboardGui.AddText("x580 y34 w150 h24 Right c86EFAC", "●  SYSTEM READY")

    ; Sidebar
    dashboardGui.AddText("x28 y112 w160 h28 cA5B4FC", "WORKSPACE")
    AddNavText(dashboardGui, "x30 y151 w150 h28", "▦   Overview")
    AddNavText(dashboardGui, "x30 y188 w150 h28", "⌘   Automations")
    AddNavText(dashboardGui, "x30 y225 w150 h28", "⌨   Shortcuts")
    AddNavText(dashboardGui, "x30 y262 w150 h28", "⚙   Settings")
    dashboardGui.AddText("x28 y510 w160 h30 c6B7280", "SPARKDESK  •  v2.0")

    ; Main panel
    dashboardGui.SetFont("s20 bold cF9FAFB", "Segoe UI")
    dashboardGui.AddText("x220 y116 w470 h34", "Good to see you.")

    dashboardGui.SetFont("s10 c9CA3AF", "Segoe UI")
    dashboardGui.AddText("x222 y153 w470 h24", "Launch your tools and workflows from one place.")

    AddStatCard(dashboardGui, 220, 198, "04", "AUTOMATIONS")
    AddStatCard(dashboardGui, 390, 198, "04", "MODE SHORTCUTS")
    AddStatCard(dashboardGui, 560, 198, "01", "UBUNTU WORKFLOW")

    dashboardGui.SetFont("s12 bold cF3F4F6", "Segoe UI")
    dashboardGui.AddText("x222 y300 w450 h26", "QUICK LAUNCH")

    AddAutomationCard(dashboardGui, 220, 336, "Ubuntu Server", "Run the Jet CLI server in WSL Ubuntu", "Ctrl + Alt + U", "ubuntu")
    AddAutomationCard(dashboardGui, 220, 414, "Coding Mode", "Antigravity IDE  •  PowerShell  •  GitHub", "Ctrl + Shift + 1", "coding")

    dashboardGui.SetFont("s9 c6B7280", "Segoe UI")
    dashboardGui.AddText("x222 y505 w480 h22", "Tip: Use Ctrl + Shift + Space to open the command palette.")

    dashboardGui.OnEvent("Close", (*) => (SD["DashboardGui"] := 0))

    SD["DashboardGui"] := dashboardGui
    dashboardGui.Show("w760 h570 Center")
}

AddNavText(guiObj, options, label) {
    guiObj.SetFont("s10 cD1D5DB", "Segoe UI")
    guiObj.AddText(options, label)
}

AddStatCard(guiObj, x, y, number, label) {
    guiObj.AddText("x" x " y" y " w155 h82 Background20242D Border", "")

    guiObj.SetFont("s20 bold cF9FAFB", "Segoe UI")
    guiObj.AddText("x" (x + 14) " y" (y + 10) " w125 h30", number)

    guiObj.SetFont("s8 c9CA3AF", "Segoe UI")
    guiObj.AddText("x" (x + 14) " y" (y + 48) " w130 h18", label)
}

AddAutomationCard(guiObj, x, y, title, description, shortcut, action) {
    guiObj.AddText("x" x " y" y " w500 h66 Background20242D Border", "")

    guiObj.SetFont("s11 bold cF9FAFB", "Segoe UI")
    guiObj.AddText("x" (x + 14) " y" (y + 9) " w250 h22", title)

    guiObj.SetFont("s9 c9CA3AF", "Segoe UI")
    guiObj.AddText("x" (x + 14) " y" (y + 34) " w320 h20", description)

    guiObj.SetFont("s8 cA5B4FC", "Segoe UI")
    guiObj.AddText("x" (x + 340) " y" (y + 13) " w145 h18 Right", shortcut)

    guiObj.SetFont("s9 bold cFFFFFF", "Segoe UI")
    button := guiObj.AddButton("x" (x + 375) " y" (y + 35) " w105 h24", "Launch")

    if (action = "ubuntu")
        button.OnEvent("Click", (*) => RunUbuntuServer())
    else if (action = "coding")
        button.OnEvent("Click", (*) => SetMode("Coding"))
    else if (action = "sysinfo")
        button.OnEvent("Click", (*) => ShowSystemInfoGui())
}
