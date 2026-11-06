#Requires AutoHotkey v2.0
#SingleInstance Force

; Standalone launcher: Ctrl + Alt + U
^!u:: {
    command := "cd /home/navadeep/jet && cargo run --release -p jet-cli -- server run --release"
    Run('wt.exe wsl.exe -d Ubuntu -- bash -lic "' command '; exec bash"')
}
