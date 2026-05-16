# Aphrodite Tweaks Pro v3.0.0

A modern, comprehensive Windows 10 / 11 optimization & tweaking suite written in Python with a CustomTkinter UI.

## What's new in v3.0
- **120+ tweaks** across 7 categories: Performance, Privacy, Gaming, Debloat, Network, Services, UI / Explorer.
- **Modern CustomTkinter UI** — sidebar navigation, live search, per-tweak risk badges (SAFE / CAUTION / ADVANCED), reboot indicator, and an "APPLIED" status badge.
- **One-click presets**: Gaming, Privacy, Balanced, Streamer, Minimal Debloat.
- **Safety first**:
  - Auto-backup of every affected registry key to `.reg` files **before** changes.
  - Per-tweak **undo** (true rollback commands) and **Undo Last Batch** button.
  - One-click **Windows System Restore Point** creation.
  - Activity log persisted to disk (`AphroditeData/logs/aphrodite.log`).
- **Self-elevation**: detects missing admin rights and offers to relaunch elevated.

## Build
```cmd
build.bat
```
The script installs `customtkinter` and `pyinstaller` then produces `AphroditeTweaksPro.exe` (single-file, windowed) in the current folder.

## Run
Right-click **`AphroditeTweaksPro.exe`** → **Run as administrator**.
First-run safety routine:
1. Click **Create Restore Point** in the sidebar.
2. Pick a preset or hand-pick tweaks.
3. Click **Apply Selected**.
4. Reboot if any tweak is flagged `REBOOT`.

## Data folder
All state, backups and logs live next to the EXE in `AphroditeData/`:
```
AphroditeData/
├── state.json       # which tweaks are currently applied
├── history.json     # apply batches (for Undo Last)
├── backups/         # timestamped .reg backups per tweak
└── logs/aphrodite.log
```

## File layout
- `aphrodite_tweaks_pro.py` — the entire app, single file.
- `build.bat` — PyInstaller build script.
- `README.md` — this file.
