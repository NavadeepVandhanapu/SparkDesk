# SparkDesk 2.0

A Windows automation dashboard powered by AutoHotkey v2.

## Requirements
- Windows 10/11
- AutoHotkey v2
- Windows Terminal (`wt.exe`)
- WSL distribution named `Ubuntu` for the Ubuntu Server action
- Antigravity IDE at `%LOCALAPPDATA%\Programs\Antigravity IDE\Antigravity IDE.exe` for Coding Mode

## Start
1. Extract the complete `SparkDesk` folder to a permanent location.
2. Double-click `main.ahk`.
3. The SparkDesk dashboard opens. A green AutoHotkey tray icon remains in the system tray.

## Shortcuts
| Shortcut | Action |
|---|---|
| Ctrl + Shift + Space | Command palette |
| Ctrl + Shift + 1 | Coding Mode |
| Ctrl + Shift + 2 | Study Mode |
| Ctrl + Shift + 3 | Exam Mode |
| Ctrl + Shift + 4 | Chill Mode |
| Ctrl + Alt + U | Launch Ubuntu Jet CLI server |
| Ctrl + Alt + K | Open SparkDesk dashboard |
| Ctrl + Shift + 0 | Reload SparkDesk |

## Ubuntu command
The bundled Ubuntu action runs:

```bash
cd /home/navadeep/jet && cargo run --release -p jet-cli -- server run --release
```

If your project moves, update the path in `modules/UbuntuAutomation.ahk`.

## Notes
- The dashboard and command palette are native AutoHotkey GUIs; no browser or extra runtime is needed.
- Coding Mode opens Antigravity, PowerShell, and GitHub in the default browser.
- Study, Exam, and Chill are starter mode actions and can be customized in `modules/Modes.ahk`.
- Logs are stored in `data/sparkdesk.log`.
