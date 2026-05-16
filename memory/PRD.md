# Aphrodite Tweaks Pro v3.0.0 - PRD

## Original problem statement
> build onto this and make it better
> (Source: `build.bat` + `aphrodite_tweaks_pro.py` v2.0.0 - a Tkinter Windows tweaks tool)

## User choices
- More tweaks (privacy, performance, gaming, debloat, network)  -> done
- Better GUI (modern dark theme, sidebar navigation, search)     -> done (CustomTkinter)
- Safety features (System Restore Points, per-tweak undo)        -> done
- Profiles & presets (Gaming / Privacy / Balanced)               -> done (also Streamer + Minimal Debloat)
- GUI framework: CustomTkinter                                    -> done
- Platform: Windows 10/11 only                                    -> done

## Architecture
- Single-file Python desktop app, packaged via PyInstaller (`--onefile --windowed`).
- All state, backups and logs live next to the EXE in `AphroditeData/`.
- Subprocess for every Win32 action (reg / sc / netsh / powercfg / powershell).

## Tweak library (100 tweaks shipped)
- Performance:    24
- Privacy:        15
- Gaming:         10
- Debloat:        17
- Network:        10
- Services:       12
- UI / Explorer:  12

## Safety stack
- Auto-export each affected registry key to `.reg` backups before every apply.
- Hosts file backed up to `hosts.aphrodite.bak` before telemetry-block tweak.
- Per-tweak `undo` commands; Undo-Last-Batch button.
- One-click Windows System Restore Point creation (`Checkpoint-Computer`).
- Activity log persisted to `AphroditeData/logs/aphrodite.log`.
- Self-elevation flow (relaunch via ShellExecute /runas).

## Files
- `aphrodite_tweaks_pro.py` - main app
- `build.bat`              - PyInstaller build script (installs deps automatically)
- `README.md`              - usage guide

## Backlog / Next ideas (P1)
- Tweak detection: read current state and reflect the toggle automatically.
- Import / export selected tweak profiles as `.json`.
- Schedule applies via Task Scheduler.
- Driver tweaks (NVIDIA / AMD profile imports).
- Localisation (i18n).
