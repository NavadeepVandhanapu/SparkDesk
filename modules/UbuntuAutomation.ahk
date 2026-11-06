RunUbuntuServer() {
    command := "cd /home/navadeep/jet && cargo run --release -p jet-cli -- server run --release"
    try {
        Run('wt.exe wsl.exe -d Ubuntu -- bash -lic "' command '; exec bash"')
        LogInfo("Ubuntu server launcher started.")
    } catch as err {
        LogError("Ubuntu launcher failed: " err.Message)
        MsgBox("Could not launch Ubuntu Terminal.`n`n" err.Message, "SparkDesk", "Icon!")
    }
}
