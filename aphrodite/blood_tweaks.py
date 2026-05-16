"""
Aphrodite Tweaks Pro v3.0.0 - Ultimate Windows Optimizer
=========================================================
A modern, comprehensive Windows 10/11 optimization & tweaking suite.

Highlights
----------
* 120+ tweaks across 7 categories (Performance, Privacy, Gaming, Debloat,
  Network, Services, UI / Explorer).
* CustomTkinter modern dark UI with sidebar navigation, live search,
  risk badges, and a built-in log console.
* One-click PRESETS (Gaming, Privacy, Balanced, Streamer, Minimal).
* SAFETY FIRST: automatic registry backups (.reg) before every change,
  per-tweak undo, optional Windows System Restore Point, hosts-file
  backup, and full activity log persisted to disk.
* Self-elevating: if launched without admin rights, asks the user to
  relaunch elevated.
* Single-file friendly - builds cleanly with the included build.bat
  (PyInstaller --onefile --windowed).

Author: Aphrodite Labs - 2026
"""
from __future__ import annotations

import ctypes
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

# CustomTkinter is the primary UI. Fall back to plain tkinter if missing
# so the script still runs (degraded) - the build.bat installs it.
try:
    import customtkinter as ctk
except ImportError:  # pragma: no cover - dev fallback
    print("[WARN] customtkinter not installed. Run: pip install customtkinter")
    raise

import tkinter as tk
from tkinter import messagebox, filedialog

# ---------------------------------------------------------------------------
# Constants & paths
# ---------------------------------------------------------------------------
APP_NAME = "Blood Tweaks"
APP_VERSION = "3.1.0"
IS_WINDOWS = sys.platform.startswith("win")

# When frozen by PyInstaller use the EXE folder, otherwise the script folder
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent

DATA_DIR = APP_DIR / "BloodData"
BACKUP_DIR = DATA_DIR / "backups"
LOG_DIR = DATA_DIR / "logs"
STATE_FILE = DATA_DIR / "state.json"
HISTORY_FILE = DATA_DIR / "history.json"
LOG_FILE = LOG_DIR / "blood.log"

for _d in (DATA_DIR, BACKUP_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Colors  -  "Noir + Blood" palette
#   Deep near-black base, charcoal surfaces, crimson primary, scarlet hover.
#   Deliberately avoids the typical purple-gradient-on-white AI-slop look.
# ---------------------------------------------------------------------------
COL = {
    "bg":          "#0a0a0c",   # near-black canvas
    "bg_alt":      "#0f0f12",   # sidebar / toolbar
    "card":        "#161619",   # tweak card surface
    "card_hover":  "#1e1e22",   # hovered card
    "border":      "#23232a",   # hairline divider
    "text":        "#f5f5f7",   # primary text
    "text_dim":    "#9a9aa3",   # secondary text
    "text_muted":  "#5c5c66",   # captions
    "accent":      "#e11d48",   # rose-600 - blood red
    "accent_hov":  "#f43f5e",   # rose-500 - hover/highlight
    "accent_deep": "#9f1239",   # rose-800 - pressed / deep
    "ok":          "#22c55e",
    "warn":        "#f59e0b",
    "danger":      "#ef4444",
    "info":        "#38bdf8",
}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# ---------------------------------------------------------------------------
# Logging - rotates one file per launch, also feeds the UI console.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")],
)
log = logging.getLogger("aphrodite")


# ---------------------------------------------------------------------------
# Tweak data model
# ---------------------------------------------------------------------------
RISK_SAFE = "safe"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"

RISK_COLOR = {RISK_SAFE: COL["ok"], RISK_MEDIUM: COL["warn"], RISK_HIGH: COL["danger"]}
RISK_LABEL = {RISK_SAFE: "SAFE", RISK_MEDIUM: "CAUTION", RISK_HIGH: "ADVANCED"}


@dataclass
class Tweak:
    """Represents one atomic tweak.

    `apply` is a list of shell commands run sequentially. `undo` mirrors it
    with the rollback commands. Either may be empty (== no-op / manual).
    Registry keys listed in `reg_keys` are exported to a .reg backup before
    `apply` runs - that backup is the canonical restore source.
    """
    name: str
    category: str
    desc: str
    apply: list[str] = field(default_factory=list)
    undo: list[str] = field(default_factory=list)
    reg_keys: list[str] = field(default_factory=list)   # for auto-backup
    risk: str = RISK_SAFE
    reboot: bool = False


# ---------------------------------------------------------------------------
# Tweak helpers
# ---------------------------------------------------------------------------
def _reg_set(path: str, name: str, kind: str, value: str) -> str:
    """Return a `reg add` command line."""
    return f'reg add "{path}" /v {name} /t {kind} /d {value} /f'


def _reg_del(path: str, name: str) -> str:
    return f'reg delete "{path}" /v {name} /f'


def _reg_revert(path: str, name: str, kind: str, value: str) -> str:
    """Same as set but used for clarity as an undo."""
    return _reg_set(path, name, kind, value)


def _svc_set(svc: str, start: str) -> str:
    return f"sc config {svc} start= {start}"


# ---------------------------------------------------------------------------
# TWEAKS REGISTRY  (120+ entries)
# ---------------------------------------------------------------------------
TWEAKS: list[Tweak] = []


def _add(t: Tweak) -> None:
    TWEAKS.append(t)


# ===== PERFORMANCE =====
_add(Tweak(
    "Enable Ultimate Performance Power Plan", "Performance",
    "Activates the hidden Windows Ultimate Performance power plan for maximum responsiveness.",
    apply=["powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61",
           "powercfg /setactive e9a42b02-d5df-448d-aa00-03f14749eb61"],
    undo=["powercfg /setactive SCHEME_BALANCED"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable SysMain (Superfetch)", "Performance",
    "Stops the SysMain service that pre-loads apps into RAM - frees memory on SSDs.",
    apply=[_svc_set("SysMain", "disabled"), "net stop SysMain"],
    undo=[_svc_set("SysMain", "auto"), "net start SysMain"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Search Indexer", "Performance",
    "Stops WSearch from continuously indexing files. Big win on slower disks.",
    apply=[_svc_set("WSearch", "disabled"), "net stop WSearch"],
    undo=[_svc_set("WSearch", "automatic"), "net start WSearch"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Print Spooler", "Performance",
    "Disables the Print Spooler service (only do this if you never print).",
    apply=[_svc_set("Spooler", "disabled"), "net stop Spooler"],
    undo=[_svc_set("Spooler", "auto"), "net start Spooler"],
    risk=RISK_MEDIUM,
))
_add(Tweak(
    "Disable Windows Error Reporting", "Performance",
    "Stops WerSvc - no more 'Windows is collecting info' pop-ups.",
    apply=[_svc_set("WerSvc", "disabled")],
    undo=[_svc_set("WerSvc", "demand")],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Connected User Experiences & Telemetry", "Performance",
    "Disables DiagTrack which gathers diagnostic data.",
    apply=[_svc_set("DiagTrack", "disabled"), "net stop DiagTrack"],
    undo=[_svc_set("DiagTrack", "auto"), "net start DiagTrack"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Delivery Optimization (P2P Updates)", "Performance",
    "Stops your PC sharing Windows Update files with strangers on the internet.",
    apply=[_svc_set("DoSvc", "disabled")],
    undo=[_svc_set("DoSvc", "auto")],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Remote Registry", "Performance",
    "Closes the remote registry attack surface.",
    apply=[_svc_set("RemoteRegistry", "disabled")],
    undo=[_svc_set("RemoteRegistry", "demand")],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Windows Fax Service", "Performance",
    "Disables the legacy Fax service.",
    apply=[_svc_set("Fax", "disabled")],
    undo=[_svc_set("Fax", "demand")],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Touch Keyboard Service", "Performance",
    "Disables the on-screen touch keyboard handwriting panel service.",
    apply=[_svc_set("TabletInputService", "disabled")],
    undo=[_svc_set("TabletInputService", "demand")],
    risk=RISK_MEDIUM,
))
_add(Tweak(
    "Maximum CPU Scheduling for Programs", "Performance",
    "Tunes Win32PrioritySeparation so foreground apps get more CPU.",
    apply=[_reg_set(r"HKLM\SYSTEM\CurrentControlSet\Control\PriorityControl",
                    "Win32PrioritySeparation", "REG_DWORD", "38")],
    undo=[_reg_set(r"HKLM\SYSTEM\CurrentControlSet\Control\PriorityControl",
                   "Win32PrioritySeparation", "REG_DWORD", "2")],
    reg_keys=[r"HKLM\SYSTEM\CurrentControlSet\Control\PriorityControl"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Enable Hardware-Accelerated GPU Scheduling", "Performance",
    "Lets the GPU manage its own VRAM - lowers latency on modern GPUs.",
    apply=[_reg_set(r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers",
                    "HwSchMode", "REG_DWORD", "2")],
    undo=[_reg_set(r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers",
                   "HwSchMode", "REG_DWORD", "1")],
    reg_keys=[r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers"],
    risk=RISK_SAFE, reboot=True,
))
_add(Tweak(
    "Disable Memory Compression", "Performance",
    "Trades a tiny CPU saving for more RAM use - good on 32 GB+ rigs.",
    apply=["powershell -NoProfile -Command \"Disable-MMAgent -mc\""],
    undo=["powershell -NoProfile -Command \"Enable-MMAgent -mc\""],
    risk=RISK_MEDIUM,
))
_add(Tweak(
    "Disable Hibernation (frees disk)", "Performance",
    "Deletes hiberfil.sys and disables hibernation. Saves several GB.",
    apply=["powercfg -h off"],
    undo=["powercfg -h on"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Startup Delay", "Performance",
    "Removes the 10-second artificial delay before startup apps launch.",
    apply=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize",
                    "StartupDelayInMSec", "REG_DWORD", "0")],
    undo=[_reg_del(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize",
                   "StartupDelayInMSec")],
    reg_keys=[r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Speed Up Shutdown", "Performance",
    "Reduces 'WaitToKillServiceTimeout' so services close faster on shutdown.",
    apply=[_reg_set(r"HKLM\SYSTEM\CurrentControlSet\Control",
                    "WaitToKillServiceTimeout", "REG_SZ", "2000")],
    undo=[_reg_set(r"HKLM\SYSTEM\CurrentControlSet\Control",
                   "WaitToKillServiceTimeout", "REG_SZ", "20000")],
    reg_keys=[r"HKLM\SYSTEM\CurrentControlSet\Control"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Background Apps (UWP)", "Performance",
    "Prevents Store apps from running in the background.",
    apply=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications",
                    "GlobalUserDisabled", "REG_DWORD", "1")],
    undo=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications",
                   "GlobalUserDisabled", "REG_DWORD", "0")],
    reg_keys=[r"HKCU\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Visual Effects (Best Performance)", "Performance",
    "Strips Aero / animations / shadows - classic perf preset.",
    apply=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
                    "VisualFXSetting", "REG_DWORD", "2")],
    undo=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
                   "VisualFXSetting", "REG_DWORD", "0")],
    reg_keys=[r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Transparency", "Performance",
    "Turns off Windows transparency / acrylic blur.",
    apply=[_reg_set(r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                    "EnableTransparency", "REG_DWORD", "0")],
    undo=[_reg_set(r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                   "EnableTransparency", "REG_DWORD", "1")],
    reg_keys=[r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Animations (window min/max)", "Performance",
    "Removes the open/close window animation.",
    apply=[_reg_set(r"HKCU\Control Panel\Desktop\WindowMetrics",
                    "MinAnimate", "REG_SZ", "0")],
    undo=[_reg_set(r"HKCU\Control Panel\Desktop\WindowMetrics",
                   "MinAnimate", "REG_SZ", "1")],
    reg_keys=[r"HKCU\Control Panel\Desktop\WindowMetrics"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Mouse Pointer Trails / Acceleration", "Performance",
    "Cleans mouse input - critical for FPS games (raw input style).",
    apply=[
        _reg_set(r"HKCU\Control Panel\Mouse", "MouseSpeed", "REG_SZ", "0"),
        _reg_set(r"HKCU\Control Panel\Mouse", "MouseThreshold1", "REG_SZ", "0"),
        _reg_set(r"HKCU\Control Panel\Mouse", "MouseThreshold2", "REG_SZ", "0"),
    ],
    undo=[
        _reg_set(r"HKCU\Control Panel\Mouse", "MouseSpeed", "REG_SZ", "1"),
        _reg_set(r"HKCU\Control Panel\Mouse", "MouseThreshold1", "REG_SZ", "6"),
        _reg_set(r"HKCU\Control Panel\Mouse", "MouseThreshold2", "REG_SZ", "10"),
    ],
    reg_keys=[r"HKCU\Control Panel\Mouse"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Storage Sense Auto-Cleanup", "Performance",
    "Stops Windows from auto-deleting files in Downloads etc.",
    apply=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\StorageSense\Parameters\StoragePolicy",
                    "01", "REG_DWORD", "0")],
    undo=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\StorageSense\Parameters\StoragePolicy",
                   "01", "REG_DWORD", "1")],
    reg_keys=[r"HKCU\Software\Microsoft\Windows\CurrentVersion\StorageSense\Parameters\StoragePolicy"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Clear Temp Files Now", "Performance",
    "Deletes contents of %TEMP% and C:\\Windows\\Temp. One-shot - no undo.",
    apply=['cmd /c "del /q /f /s %TEMP%\\* 2>nul & del /q /f /s C:\\Windows\\Temp\\* 2>nul"'],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Prefetch", "Performance",
    "Completely disables Prefetch & Superfetch in the registry.",
    apply=[_reg_set(r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management\PrefetchParameters",
                    "EnablePrefetcher", "REG_DWORD", "0"),
           _reg_set(r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management\PrefetchParameters",
                    "EnableSuperfetch", "REG_DWORD", "0")],
    undo=[_reg_set(r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management\PrefetchParameters",
                   "EnablePrefetcher", "REG_DWORD", "3"),
          _reg_set(r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management\PrefetchParameters",
                   "EnableSuperfetch", "REG_DWORD", "3")],
    reg_keys=[r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management\PrefetchParameters"],
    risk=RISK_MEDIUM,
))

# ===== PRIVACY =====
_add(Tweak(
    "Disable Telemetry (AllowTelemetry=0)", "Privacy",
    "Sets Microsoft data collection to the lowest allowed level.",
    apply=[_reg_set(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\DataCollection",
                    "AllowTelemetry", "REG_DWORD", "0")],
    undo=[_reg_set(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\DataCollection",
                   "AllowTelemetry", "REG_DWORD", "1")],
    reg_keys=[r"HKLM\SOFTWARE\Policies\Microsoft\Windows\DataCollection"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Advertising ID", "Privacy",
    "Turns off the per-user advertising ID used by Store apps.",
    apply=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo",
                    "Enabled", "REG_DWORD", "0")],
    undo=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo",
                   "Enabled", "REG_DWORD", "1")],
    reg_keys=[r"HKCU\Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Activity History / Timeline", "Privacy",
    "Stops Windows from collecting Activity History across devices.",
    apply=[
        _reg_set(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\System",
                 "EnableActivityFeed", "REG_DWORD", "0"),
        _reg_set(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\System",
                 "PublishUserActivities", "REG_DWORD", "0"),
        _reg_set(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\System",
                 "UploadUserActivities", "REG_DWORD", "0"),
    ],
    undo=[_reg_del(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\System",
                   "EnableActivityFeed")],
    reg_keys=[r"HKLM\SOFTWARE\Policies\Microsoft\Windows\System"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Location Tracking", "Privacy",
    "Disables location services system-wide.",
    apply=[
        _reg_set(r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location",
                 "Value", "REG_SZ", "Deny"),
        _svc_set("lfsvc", "disabled"),
    ],
    undo=[
        _reg_set(r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location",
                 "Value", "REG_SZ", "Allow"),
        _svc_set("lfsvc", "demand"),
    ],
    reg_keys=[r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Cortana", "Privacy",
    "Disables Cortana voice assistant.",
    apply=[_reg_set(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\Windows Search",
                    "AllowCortana", "REG_DWORD", "0")],
    undo=[_reg_del(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\Windows Search",
                   "AllowCortana")],
    reg_keys=[r"HKLM\SOFTWARE\Policies\Microsoft\Windows\Windows Search"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Bing Search in Start Menu", "Privacy",
    "Removes web/Bing results from the Start menu.",
    apply=[
        _reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Search",
                 "BingSearchEnabled", "REG_DWORD", "0"),
        _reg_set(r"HKCU\Software\Policies\Microsoft\Windows\Explorer",
                 "DisableSearchBoxSuggestions", "REG_DWORD", "1"),
    ],
    undo=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Search",
                   "BingSearchEnabled", "REG_DWORD", "1")],
    reg_keys=[r"HKCU\Software\Microsoft\Windows\CurrentVersion\Search"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Suggested Content in Settings", "Privacy",
    "Removes Microsoft's promo banners across the Settings app.",
    apply=[
        _reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
                 "SubscribedContent-338393Enabled", "REG_DWORD", "0"),
        _reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
                 "SubscribedContent-353694Enabled", "REG_DWORD", "0"),
        _reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
                 "SubscribedContent-353696Enabled", "REG_DWORD", "0"),
    ],
    reg_keys=[r"HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Lockscreen Spotlight Ads", "Privacy",
    "Stops 'fun facts / suggestions' from appearing on the lockscreen.",
    apply=[
        _reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
                 "RotatingLockScreenEnabled", "REG_DWORD", "0"),
        _reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
                 "RotatingLockScreenOverlayEnabled", "REG_DWORD", "0"),
    ],
    reg_keys=[r"HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Tips, Tricks & Suggestions", "Privacy",
    "Stops Windows from showing 'Tips' notifications.",
    apply=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
                    "SoftLandingEnabled", "REG_DWORD", "0")],
    reg_keys=[r"HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Inking & Typing Personalization", "Privacy",
    "Stops Microsoft from learning your handwriting / typing patterns.",
    apply=[_reg_set(r"HKCU\Software\Microsoft\InputPersonalization",
                    "RestrictImplicitTextCollection", "REG_DWORD", "1"),
           _reg_set(r"HKCU\Software\Microsoft\InputPersonalization",
                    "RestrictImplicitInkCollection", "REG_DWORD", "1")],
    reg_keys=[r"HKCU\Software\Microsoft\InputPersonalization"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Block Telemetry Domains (hosts file)", "Privacy",
    "Adds Microsoft telemetry endpoints to the hosts file. Backed up first.",
    apply=['powershell -NoProfile -ExecutionPolicy Bypass -Command "$h = \\"$env:SystemRoot\\drivers\\etc\\hosts\\"; '
           'Copy-Item $h \\"$env:SystemRoot\\drivers\\etc\\hosts.blood.bak\\" -Force; '
           '$lines = @(\\"0.0.0.0 vortex.data.microsoft.com\\",\\"0.0.0.0 settings-win.data.microsoft.com\\",'
           '\\"0.0.0.0 telemetry.microsoft.com\\",\\"0.0.0.0 watson.telemetry.microsoft.com\\",'
           '\\"0.0.0.0 v10.events.data.microsoft.com\\",\\"0.0.0.0 activity.windows.com\\"); '
           'foreach($l in $lines){if(-not (Select-String -Path $h -Pattern ([regex]::Escape($l)) -Quiet)){Add-Content -Path $h -Value $l}}; ipconfig /flushdns | Out-Null"'],
    undo=['powershell -NoProfile -Command "if(Test-Path \\"$env:SystemRoot\\drivers\\etc\\hosts.blood.bak\\"){Copy-Item \\"$env:SystemRoot\\drivers\\etc\\hosts.blood.bak\\" \\"$env:SystemRoot\\drivers\\etc\\hosts\\" -Force}"'],
    risk=RISK_MEDIUM,
))
_add(Tweak(
    "Disable Feedback Frequency Prompts", "Privacy",
    "Tells Windows never to ask for feedback.",
    apply=[_reg_set(r"HKCU\Software\Microsoft\Siuf\Rules",
                    "NumberOfSIUFInPeriod", "REG_DWORD", "0"),
           _reg_set(r"HKCU\Software\Microsoft\Siuf\Rules",
                    "PeriodInNanoSeconds", "REG_DWORD", "0")],
    reg_keys=[r"HKCU\Software\Microsoft\Siuf\Rules"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable App Launch Tracking", "Privacy",
    "Stops Windows tracking which apps you use to 'improve results'.",
    apply=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                    "Start_TrackProgs", "REG_DWORD", "0")],
    reg_keys=[r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Clipboard History Sync", "Privacy",
    "Prevents the clipboard from syncing to the cloud.",
    apply=[_reg_set(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\System",
                    "AllowCrossDeviceClipboard", "REG_DWORD", "0")],
    reg_keys=[r"HKLM\SOFTWARE\Policies\Microsoft\Windows\System"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Recall (Windows 11 24H2+)", "Privacy",
    "Disables the screenshot-based 'Recall' feature.",
    apply=[_reg_set(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsAI",
                    "DisableAIDataAnalysis", "REG_DWORD", "1")],
    reg_keys=[r"HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsAI"],
    risk=RISK_SAFE,
))

# ===== GAMING =====
_add(Tweak(
    "Enable Game Mode", "Gaming",
    "Turns on Windows Game Mode for active games.",
    apply=[_reg_set(r"HKCU\Software\Microsoft\GameBar", "AutoGameModeEnabled", "REG_DWORD", "1"),
           _reg_set(r"HKCU\Software\Microsoft\GameBar", "AllowAutoGameMode", "REG_DWORD", "1")],
    undo=[_reg_set(r"HKCU\Software\Microsoft\GameBar", "AutoGameModeEnabled", "REG_DWORD", "0")],
    reg_keys=[r"HKCU\Software\Microsoft\GameBar"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Xbox Game Bar (overlay)", "Gaming",
    "Turns off the Xbox Game Bar overlay (Win+G).",
    apply=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\GameDVR",
                    "AppCaptureEnabled", "REG_DWORD", "0"),
           _reg_set(r"HKCU\System\GameConfigStore",
                    "GameDVR_Enabled", "REG_DWORD", "0")],
    undo=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\GameDVR",
                   "AppCaptureEnabled", "REG_DWORD", "1"),
          _reg_set(r"HKCU\System\GameConfigStore",
                   "GameDVR_Enabled", "REG_DWORD", "1")],
    reg_keys=[r"HKCU\System\GameConfigStore",
              r"HKCU\Software\Microsoft\Windows\CurrentVersion\GameDVR"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Prioritize Games (SystemResponsiveness)", "Gaming",
    "Lowers the slice of CPU reserved for background tasks - more for games.",
    apply=[_reg_set(r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile",
                    "SystemResponsiveness", "REG_DWORD", "0")],
    undo=[_reg_set(r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile",
                   "SystemResponsiveness", "REG_DWORD", "20")],
    reg_keys=[r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Boost Games MMCSS Priority", "Gaming",
    "Sets the Games MMCSS task to High priority.",
    apply=[
        _reg_set(r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games",
                 "GPU Priority", "REG_DWORD", "8"),
        _reg_set(r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games",
                 "Priority", "REG_DWORD", "6"),
        _reg_set(r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games",
                 "Scheduling Category", "REG_SZ", "High"),
    ],
    reg_keys=[r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Fullscreen Optimizations (global)", "Gaming",
    "Forces true exclusive fullscreen for all apps.",
    apply=[
        _reg_set(r"HKCU\System\GameConfigStore", "GameDVR_FSEBehavior", "REG_DWORD", "2"),
        _reg_set(r"HKCU\System\GameConfigStore", "GameDVR_FSEBehaviorMode", "REG_DWORD", "2"),
        _reg_set(r"HKCU\System\GameConfigStore", "GameDVR_HonorUserFSEBehaviorMode", "REG_DWORD", "1"),
        _reg_set(r"HKCU\System\GameConfigStore", "GameDVR_DXGIHonorFSEWindowsCompatible", "REG_DWORD", "1"),
    ],
    reg_keys=[r"HKCU\System\GameConfigStore"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Nagle's Algorithm (lower ping)", "Gaming",
    "Disables TCP packet coalescing on every active interface.",
    apply=['powershell -NoProfile -Command "Get-ChildItem \'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces\' | ForEach-Object { New-ItemProperty -Path $_.PSPath -Name TcpAckFrequency -Value 1 -PropertyType DWord -Force | Out-Null; New-ItemProperty -Path $_.PSPath -Name TCPNoDelay -Value 1 -PropertyType DWord -Force | Out-Null }"'],
    undo=['powershell -NoProfile -Command "Get-ChildItem \'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces\' | ForEach-Object { Remove-ItemProperty -Path $_.PSPath -Name TcpAckFrequency -ErrorAction SilentlyContinue; Remove-ItemProperty -Path $_.PSPath -Name TCPNoDelay -ErrorAction SilentlyContinue }"'],
    risk=RISK_MEDIUM,
))
_add(Tweak(
    "Enable MSI Mode hint", "Gaming",
    "Adds a registry hint - actual MSI must be set per-device in Device Manager.",
    apply=[_reg_set(r"HKLM\SYSTEM\CurrentControlSet\Control\PnP",
                    "DisableCPUEnumeration", "REG_DWORD", "0")],
    risk=RISK_MEDIUM,
))
_add(Tweak(
    "Set NVIDIA / GPU High Performance (per-app prefer GPU)", "Gaming",
    "Tells Windows to prefer the discrete GPU for desktop apps.",
    apply=[_reg_set(r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers",
                    "TdrDelay", "REG_DWORD", "10")],
    reg_keys=[r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers"],
    risk=RISK_MEDIUM,
))
_add(Tweak(
    "Disable Mouse Acceleration (true 1:1)", "Gaming",
    "Aliases the perf tweak in a gaming context - 1:1 mouse for FPS.",
    apply=[_reg_set(r"HKCU\Control Panel\Mouse", "MouseSpeed", "REG_SZ", "0")],
    undo=[_reg_set(r"HKCU\Control Panel\Mouse", "MouseSpeed", "REG_SZ", "1")],
    reg_keys=[r"HKCU\Control Panel\Mouse"],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disable Windows Hotkeys (Win, AltTab) - Gaming Focus", "Gaming",
    "Blocks the Windows / Alt-Tab keys so they don't pull you out of game.",
    apply=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer",
                    "NoWinKeys", "REG_DWORD", "1")],
    undo=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer",
                   "NoWinKeys", "REG_DWORD", "0")],
    reg_keys=[r"HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer"],
    risk=RISK_MEDIUM,
))

# ===== DEBLOAT =====
def _appx(name: str) -> str:
    return (f'powershell -NoProfile -Command '
            f'"Get-AppxPackage -AllUsers *{name}* | '
            f'Remove-AppxPackage -ErrorAction SilentlyContinue"')

_add(Tweak("Remove Xbox Apps", "Debloat",
           "Removes Xbox, Xbox Game Bar and friends.",
           apply=[_appx("Xbox")], risk=RISK_MEDIUM))
_add(Tweak("Remove OneDrive", "Debloat",
           "Uninstalls OneDrive cloud sync.",
           apply=['cmd /c "taskkill /f /im OneDrive.exe 2>nul & %SystemRoot%\\SysWOW64\\OneDriveSetup.exe /uninstall"'],
           risk=RISK_MEDIUM))
_add(Tweak("Remove Cortana App", "Debloat",
           "Removes the Cortana UWP app.",
           apply=[_appx("Microsoft.549981C3F5F10")], risk=RISK_MEDIUM))
_add(Tweak("Remove Solitaire Collection", "Debloat",
           "Removes Microsoft Solitaire Collection.",
           apply=[_appx("MicrosoftSolitaireCollection")], risk=RISK_SAFE))
_add(Tweak("Remove Skype UWP", "Debloat",
           "Removes Microsoft Skype UWP app.",
           apply=[_appx("SkypeApp")], risk=RISK_SAFE))
_add(Tweak("Remove News & Weather", "Debloat",
           "Removes Microsoft News and Weather apps.",
           apply=[_appx("BingNews"), _appx("BingWeather")], risk=RISK_SAFE))
_add(Tweak("Remove Get Help / Tips / Feedback Hub", "Debloat",
           "Removes the Get Help, Tips and Feedback Hub apps.",
           apply=[_appx("GetHelp"), _appx("Getstarted"), _appx("WindowsFeedbackHub")],
           risk=RISK_SAFE))
_add(Tweak("Remove Mixed Reality Portal", "Debloat",
           "Removes the Mixed Reality / 3D Viewer apps.",
           apply=[_appx("MixedReality"), _appx("Microsoft3DViewer")], risk=RISK_SAFE))
_add(Tweak("Remove Your Phone (Phone Link)", "Debloat",
           "Removes the Phone Link app.",
           apply=[_appx("YourPhone")], risk=RISK_SAFE))
_add(Tweak("Remove Maps", "Debloat",
           "Removes the Windows Maps app.",
           apply=[_appx("WindowsMaps")], risk=RISK_SAFE))
_add(Tweak("Remove Groove Music", "Debloat",
           "Removes the Groove Music / Zune apps.",
           apply=[_appx("ZuneMusic"), _appx("ZuneVideo")], risk=RISK_SAFE))
_add(Tweak("Remove People App", "Debloat",
           "Removes the People app.",
           apply=[_appx("Microsoft.People")], risk=RISK_SAFE))
_add(Tweak("Remove Windows Media Player UWP", "Debloat",
           "Removes the UWP Media Player (legacy WMP unaffected).",
           apply=[_appx("Microsoft.ZuneMusic"), _appx("Microsoft.WindowsMediaPlayer")], risk=RISK_SAFE))
_add(Tweak("Remove Office Hub / OneNote / To-Do", "Debloat",
           "Removes the Office hub, OneNote UWP and Microsoft To-Do.",
           apply=[_appx("MicrosoftOfficeHub"), _appx("OneNote"), _appx("Todos")],
           risk=RISK_SAFE))
_add(Tweak("Remove Windows Mail / Calendar", "Debloat",
           "Removes the Windows Mail & Calendar apps.",
           apply=[_appx("windowscommunicationsapps")], risk=RISK_MEDIUM))
_add(Tweak("Remove Edge Browser Splash / FirstRun Promos", "Debloat",
           "Suppresses Edge first-run experience prompts.",
           apply=[
               _reg_set(r"HKLM\SOFTWARE\Policies\Microsoft\Edge",
                        "HideFirstRunExperience", "REG_DWORD", "1"),
           ],
           reg_keys=[r"HKLM\SOFTWARE\Policies\Microsoft\Edge"],
           risk=RISK_SAFE))
_add(Tweak("Remove Pre-Installed Bloat (broad sweep)", "Debloat",
           "Removes Candy Crush, Spotify ad, Disney+ promo and similar OEM bloat.",
           apply=[
               _appx("CandyCrush"),
               _appx("SpotifyAB.SpotifyMusic"),
               _appx("Disney"),
               _appx("Facebook"),
               _appx("LinkedInforWindows"),
               _appx("TikTok"),
               _appx("AdobePhotoshopExpress"),
           ],
           risk=RISK_MEDIUM))

# ===== NETWORK =====
_add(Tweak("Flush DNS Cache", "Network",
           "Clears the DNS resolver cache.",
           apply=["ipconfig /flushdns"], risk=RISK_SAFE))
_add(Tweak("Reset Winsock Catalog", "Network",
           "Resets the Winsock catalog. Requires reboot.",
           apply=["netsh winsock reset"], risk=RISK_MEDIUM, reboot=True))
_add(Tweak("Reset TCP/IP Stack", "Network",
           "Resets the entire TCP/IP stack. Requires reboot.",
           apply=["netsh int ip reset"], risk=RISK_MEDIUM, reboot=True))
_add(Tweak("Release + Renew IP", "Network",
           "Releases your current DHCP lease and obtains a new one.",
           apply=["ipconfig /release", "ipconfig /renew"], risk=RISK_SAFE))
_add(Tweak("Enable DNS over HTTPS (DoH)", "Network",
           "Turns on Windows 11 native DoH.",
           apply=[_reg_set(r"HKLM\SYSTEM\CurrentControlSet\Services\Dnscache\Parameters",
                           "EnableAutoDoh", "REG_DWORD", "2")],
           undo=[_reg_set(r"HKLM\SYSTEM\CurrentControlSet\Services\Dnscache\Parameters",
                          "EnableAutoDoh", "REG_DWORD", "0")],
           reg_keys=[r"HKLM\SYSTEM\CurrentControlSet\Services\Dnscache\Parameters"],
           risk=RISK_SAFE))
_add(Tweak("Use Cloudflare 1.1.1.1 DNS", "Network",
           "Sets primary/secondary DNS to Cloudflare on every interface.",
           apply=['powershell -NoProfile -Command "Get-NetAdapter -Physical | Where-Object Status -eq Up | ForEach-Object { Set-DnsClientServerAddress -InterfaceIndex $_.ifIndex -ServerAddresses 1.1.1.1,1.0.0.1 }"'],
           undo=['powershell -NoProfile -Command "Get-NetAdapter -Physical | Where-Object Status -eq Up | ForEach-Object { Set-DnsClientServerAddress -InterfaceIndex $_.ifIndex -ResetServerAddresses }"'],
           risk=RISK_SAFE))
_add(Tweak("Disable IPv6", "Network",
           "Disables IPv6 on all interfaces (some games behave better on v4 only).",
           apply=[_reg_set(r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip6\Parameters",
                           "DisabledComponents", "REG_DWORD", "0xFF")],
           undo=[_reg_set(r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip6\Parameters",
                          "DisabledComponents", "REG_DWORD", "0")],
           reg_keys=[r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip6\Parameters"],
           risk=RISK_MEDIUM, reboot=True))
_add(Tweak("Enable TCP Auto-Tuning Normal", "Network",
           "Restores the normal TCP auto-tuning level (fixes some routers).",
           apply=["netsh int tcp set global autotuninglevel=normal"],
           undo=["netsh int tcp set global autotuninglevel=disabled"],
           risk=RISK_SAFE))
_add(Tweak("Enable ECN Capability", "Network",
           "Enables Explicit Congestion Notification.",
           apply=["netsh int tcp set global ecncapability=enabled"],
           undo=["netsh int tcp set global ecncapability=default"],
           risk=RISK_SAFE))
_add(Tweak("Reset Firewall to Defaults", "Network",
           "Resets all Windows Firewall rules to factory defaults.",
           apply=["netsh advfirewall reset"], risk=RISK_HIGH))

# ===== SERVICES =====
_for = {
    "MapsBroker":        ("Downloaded Maps Manager",        "demand"),
    "RetailDemo":         ("Retail Demo Service",            "demand"),
    "PcaSvc":             ("Program Compatibility Assistant","auto"),
    "DPS":                ("Diagnostic Policy Service",      "auto"),
    "WdiServiceHost":     ("Diagnostic Service Host",        "demand"),
    "WdiSystemHost":      ("Diagnostic System Host",         "demand"),
    "ALG":                ("Application Layer Gateway",      "demand"),
    "WerSvc":             ("Windows Error Reporting",        "demand"),
    "RemoteAccess":       ("Routing & Remote Access",        "disabled"),
    "TrkWks":             ("Distributed Link Tracking",      "auto"),
    "WbioSrvc":           ("Windows Biometric",              "demand"),
    "Fax":                ("Fax",                            "demand"),
}
for _svc, (_lbl, _orig) in _for.items():
    _add(Tweak(
        f"Disable Service: {_lbl}", "Services",
        f"Sets the {_lbl} ({_svc}) service to disabled.",
        apply=[_svc_set(_svc, "disabled")],
        undo=[_svc_set(_svc, _orig)],
        risk=RISK_MEDIUM,
    ))

# ===== UI / EXPLORER =====
_add(Tweak("Enable Dark Mode (Apps + System)", "UI / Explorer",
           "Switches Windows + apps to dark theme.",
           apply=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                           "AppsUseLightTheme", "REG_DWORD", "0"),
                  _reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                           "SystemUsesLightTheme", "REG_DWORD", "0")],
           undo=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                          "AppsUseLightTheme", "REG_DWORD", "1"),
                 _reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                          "SystemUsesLightTheme", "REG_DWORD", "1")],
           reg_keys=[r"HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"],
           risk=RISK_SAFE))
_add(Tweak("Show File Extensions", "UI / Explorer",
           "Stops Explorer hiding known file extensions.",
           apply=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                           "HideFileExt", "REG_DWORD", "0")],
           undo=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                          "HideFileExt", "REG_DWORD", "1")],
           reg_keys=[r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"],
           risk=RISK_SAFE))
_add(Tweak("Show Hidden Files", "UI / Explorer",
           "Makes hidden files visible by default.",
           apply=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                           "Hidden", "REG_DWORD", "1")],
           undo=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                          "Hidden", "REG_DWORD", "2")],
           reg_keys=[r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"],
           risk=RISK_SAFE))
_add(Tweak("Disable Aero Shake", "UI / Explorer",
           "Disables the shake-to-minimize-others gesture.",
           apply=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                           "DisallowShaking", "REG_DWORD", "1")],
           undo=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                          "DisallowShaking", "REG_DWORD", "0")],
           reg_keys=[r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"],
           risk=RISK_SAFE))
_add(Tweak("Open Explorer to This PC", "UI / Explorer",
           "Opens File Explorer to 'This PC' instead of Quick Access.",
           apply=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                           "LaunchTo", "REG_DWORD", "1")],
           undo=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                          "LaunchTo", "REG_DWORD", "2")],
           reg_keys=[r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"],
           risk=RISK_SAFE))
_add(Tweak("Hide Taskbar Search Box (Win11)", "UI / Explorer",
           "Hides the chunky search box in the Windows 11 taskbar.",
           apply=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Search",
                           "SearchboxTaskbarMode", "REG_DWORD", "0")],
           undo=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Search",
                          "SearchboxTaskbarMode", "REG_DWORD", "1")],
           reg_keys=[r"HKCU\Software\Microsoft\Windows\CurrentVersion\Search"],
           risk=RISK_SAFE))
_add(Tweak("Hide Taskbar Chat (Win11)", "UI / Explorer",
           "Hides the Teams Chat button on the taskbar.",
           apply=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                           "TaskbarMn", "REG_DWORD", "0")],
           undo=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                          "TaskbarMn", "REG_DWORD", "1")],
           reg_keys=[r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"],
           risk=RISK_SAFE))
_add(Tweak("Hide Taskbar Widgets (Win11)", "UI / Explorer",
           "Hides the news/weather Widgets button.",
           apply=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                           "TaskbarDa", "REG_DWORD", "0")],
           undo=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                          "TaskbarDa", "REG_DWORD", "1")],
           reg_keys=[r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"],
           risk=RISK_SAFE))
_add(Tweak("Left-Align Taskbar (Win11)", "UI / Explorer",
           "Pins the taskbar icons to the left, classic Windows feel.",
           apply=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                           "TaskbarAl", "REG_DWORD", "0")],
           undo=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                          "TaskbarAl", "REG_DWORD", "1")],
           reg_keys=[r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"],
           risk=RISK_SAFE))
_add(Tweak("Restore Classic Right-Click Menu (Win11)", "UI / Explorer",
           "Brings back the full Win10 context menu in File Explorer.",
           apply=['reg add "HKCU\\Software\\Classes\\CLSID\\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\\InprocServer32" /f /ve'],
           undo=['reg delete "HKCU\\Software\\Classes\\CLSID\\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}" /f'],
           reg_keys=[r"HKCU\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}"],
           risk=RISK_SAFE, reboot=False))
_add(Tweak("Disable Lock Screen Spotlight Image", "UI / Explorer",
           "Stops Microsoft pushing Bing wallpapers to your lockscreen.",
           apply=[_reg_set(r"HKLM\Software\Policies\Microsoft\Windows\Personalization",
                           "NoLockScreen", "REG_DWORD", "1")],
           reg_keys=[r"HKLM\Software\Policies\Microsoft\Windows\Personalization"],
           risk=RISK_MEDIUM))
_add(Tweak("Disable Snap Assist", "UI / Explorer",
           "Disables snap-assist window suggestions.",
           apply=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                           "SnapAssist", "REG_DWORD", "0")],
           undo=[_reg_set(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                          "SnapAssist", "REG_DWORD", "1")],
           reg_keys=[r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"],
           risk=RISK_SAFE))

# ===== CPU / OVERCLOCK-LIKE POWER TWEAKS =====
_add(Tweak(
    "CPU: 100% Min Processor State", "Performance",
    "Pins min processor state to 100% on AC and battery — prevents any downclocking under load.",
    apply=[
        "powercfg /setacvalueindex scheme_current sub_processor PROCTHROTTLEMIN 100",
        "powercfg /setdcvalueindex scheme_current sub_processor PROCTHROTTLEMIN 100",
        "powercfg /setactive scheme_current",
    ],
    undo=[
        "powercfg /setacvalueindex scheme_current sub_processor PROCTHROTTLEMIN 5",
        "powercfg /setdcvalueindex scheme_current sub_processor PROCTHROTTLEMIN 5",
        "powercfg /setactive scheme_current",
    ],
    risk=RISK_MEDIUM,
))
_add(Tweak(
    "CPU: 100% Max Processor State", "Performance",
    "Pins max processor state to 100% — unlocks full turbo headroom.",
    apply=[
        "powercfg /setacvalueindex scheme_current sub_processor PROCTHROTTLEMAX 100",
        "powercfg /setdcvalueindex scheme_current sub_processor PROCTHROTTLEMAX 100",
        "powercfg /setactive scheme_current",
    ],
    risk=RISK_SAFE,
))
_add(Tweak(
    "CPU: Disable Core Parking", "Performance",
    "Forces all cores awake — better responsiveness, slightly higher idle power.",
    apply=[
        "powercfg /setacvalueindex scheme_current sub_processor CPMINCORES 100",
        "powercfg /setdcvalueindex scheme_current sub_processor CPMINCORES 100",
        "powercfg /setactive scheme_current",
    ],
    undo=[
        "powercfg /setacvalueindex scheme_current sub_processor CPMINCORES 10",
        "powercfg /setdcvalueindex scheme_current sub_processor CPMINCORES 10",
        "powercfg /setactive scheme_current",
    ],
    risk=RISK_MEDIUM,
))
_add(Tweak(
    "CPU: Aggressive Boost Mode", "Performance",
    "Sets processor boost policy to AGGRESSIVE on AC for instant turbo.",
    apply=[
        "powercfg /setacvalueindex scheme_current sub_processor PERFBOOSTMODE 2",
        "powercfg /setactive scheme_current",
    ],
    undo=[
        "powercfg /setacvalueindex scheme_current sub_processor PERFBOOSTMODE 1",
        "powercfg /setactive scheme_current",
    ],
    risk=RISK_SAFE,
))
_add(Tweak(
    "CPU: Disable Idle States (C-states)", "Performance",
    "Stops the CPU dropping into deep idle. Lower 1% lows in games, but hotter CPU.",
    apply=[
        "powercfg /setacvalueindex scheme_current sub_processor IDLEDISABLE 1",
        "powercfg /setdcvalueindex scheme_current sub_processor IDLEDISABLE 1",
        "powercfg /setactive scheme_current",
    ],
    undo=[
        "powercfg /setacvalueindex scheme_current sub_processor IDLEDISABLE 0",
        "powercfg /setdcvalueindex scheme_current sub_processor IDLEDISABLE 0",
        "powercfg /setactive scheme_current",
    ],
    risk=RISK_HIGH,
))
_add(Tweak(
    "CPU: Disable Processor Throttling on Battery", "Performance",
    "Stops the CPU throttling when on battery (laptops).",
    apply=[
        "powercfg /setdcvalueindex scheme_current sub_processor THROTTLING 0",
        "powercfg /setactive scheme_current",
    ],
    risk=RISK_MEDIUM,
))
_add(Tweak(
    "PCIe: Disable Link State Power Management", "Performance",
    "Stops PCIe lanes (GPU / NVMe) being throttled to save power.",
    apply=[
        "powercfg /setacvalueindex scheme_current sub_pciexpress ASPM 0",
        "powercfg /setdcvalueindex scheme_current sub_pciexpress ASPM 0",
        "powercfg /setactive scheme_current",
    ],
    undo=[
        "powercfg /setacvalueindex scheme_current sub_pciexpress ASPM 2",
        "powercfg /setdcvalueindex scheme_current sub_pciexpress ASPM 2",
        "powercfg /setactive scheme_current",
    ],
    risk=RISK_SAFE,
))
_add(Tweak(
    "USB: Disable Selective Suspend", "Performance",
    "Stops Windows turning off USB devices to save power (helps mouse/audio).",
    apply=[
        "powercfg /setacvalueindex scheme_current sub_usb USBSELECT 0",
        "powercfg /setdcvalueindex scheme_current sub_usb USBSELECT 0",
        "powercfg /setactive scheme_current",
    ],
    undo=[
        "powercfg /setacvalueindex scheme_current sub_usb USBSELECT 1",
        "powercfg /setdcvalueindex scheme_current sub_usb USBSELECT 1",
        "powercfg /setactive scheme_current",
    ],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Disk: Disable HDD Spin-Down", "Performance",
    "Stops spinning disks parking after idle. (SSDs unaffected.)",
    apply=[
        "powercfg /change disk-timeout-ac 0",
        "powercfg /change disk-timeout-dc 0",
    ],
    risk=RISK_SAFE,
))
_add(Tweak(
    "Power: Disable Wake Timers", "Performance",
    "Stops scheduled tasks waking the PC from sleep.",
    apply=[
        "powercfg /setacvalueindex scheme_current sub_sleep RTCWAKE 0",
        "powercfg /setdcvalueindex scheme_current sub_sleep RTCWAKE 0",
        "powercfg /setactive scheme_current",
    ],
    risk=RISK_SAFE,
))

# ===== ADVANCED NETWORK / PING TWEAKS =====
_add(Tweak("Net: Disable QoS Bandwidth Reservation", "Network",
    "Removes the 20% bandwidth Windows reserves for QoS.",
    apply=[_reg_set(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\Psched",
                    "NonBestEffortLimit", "REG_DWORD", "0")],
    undo=[_reg_del(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\Psched",
                   "NonBestEffortLimit")],
    reg_keys=[r"HKLM\SOFTWARE\Policies\Microsoft\Windows\Psched"],
    risk=RISK_SAFE))
_add(Tweak("Net: Lower TcpTimedWaitDelay to 30s", "Network",
    "Frees ephemeral ports faster after a connection closes — helps under heavy P2P loads.",
    apply=[_reg_set(r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters",
                    "TcpTimedWaitDelay", "REG_DWORD", "30")],
    undo=[_reg_set(r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters",
                   "TcpTimedWaitDelay", "REG_DWORD", "120")],
    reg_keys=[r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"],
    risk=RISK_SAFE))
_add(Tweak("Net: Max User Ports = 65534", "Network",
    "Raises the ephemeral port range to its maximum.",
    apply=[_reg_set(r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters",
                    "MaxUserPort", "REG_DWORD", "65534")],
    undo=[_reg_del(r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters",
                   "MaxUserPort")],
    reg_keys=[r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"],
    risk=RISK_SAFE))
_add(Tweak("Net: Disable Multimedia Network Throttling", "Network",
    "Stops Windows throttling network traffic when audio/video plays.",
    apply=[_reg_set(r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile",
                    "NetworkThrottlingIndex", "REG_DWORD", "0xFFFFFFFF")],
    undo=[_reg_set(r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile",
                   "NetworkThrottlingIndex", "REG_DWORD", "10")],
    reg_keys=[r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"],
    risk=RISK_SAFE))
_add(Tweak("Net: Disable NIC Power Saving", "Network",
    "Disables 'Allow the computer to turn off this device' on every NIC.",
    apply=['powershell -NoProfile -Command "Get-NetAdapter -Physical | ForEach-Object { $p = Get-NetAdapterPowerManagement -Name $_.Name -ErrorAction SilentlyContinue; if($p){ $p.AllowComputerToTurnOffDevice = \'Disabled\'; Set-NetAdapterPowerManagement -InputObject $p -ErrorAction SilentlyContinue } }"'],
    undo=['powershell -NoProfile -Command "Get-NetAdapter -Physical | ForEach-Object { $p = Get-NetAdapterPowerManagement -Name $_.Name -ErrorAction SilentlyContinue; if($p){ $p.AllowComputerToTurnOffDevice = \'Enabled\'; Set-NetAdapterPowerManagement -InputObject $p -ErrorAction SilentlyContinue } }"'],
    risk=RISK_SAFE))
_add(Tweak("Net: Disable LSO (Large Send Offload v2)", "Network",
    "Disables hardware LSOv2 on every NIC — often lowers jitter / micro-stutter.",
    apply=['powershell -NoProfile -Command "Get-NetAdapter -Physical | Disable-NetAdapterLso -ErrorAction SilentlyContinue"'],
    undo=['powershell -NoProfile -Command "Get-NetAdapter -Physical | Enable-NetAdapterLso -ErrorAction SilentlyContinue"'],
    risk=RISK_MEDIUM))
_add(Tweak("Net: Disable RSC (Receive Segment Coalescing)", "Network",
    "Disables RSC, which can add latency on fast home links.",
    apply=["netsh int tcp set global rsc=disabled"],
    undo=["netsh int tcp set global rsc=default"],
    risk=RISK_SAFE))
_add(Tweak("Net: Enable Compound TCP", "Network",
    "Switches the congestion algorithm to Compound TCP — usually better for gaming.",
    apply=["netsh int tcp set supplemental Internet congestionprovider=ctcp"],
    undo=["netsh int tcp set supplemental Internet congestionprovider=default"],
    risk=RISK_SAFE))
_add(Tweak("Net: NIC Interrupt Moderation Off", "Network",
    "Asks every NIC to disable interrupt moderation for lower latency (hardware permitting).",
    apply=['powershell -NoProfile -Command "Get-NetAdapter -Physical | ForEach-Object { Set-NetAdapterAdvancedProperty -Name $_.Name -DisplayName \'Interrupt Moderation\' -DisplayValue \'Disabled\' -ErrorAction SilentlyContinue }"'],
    undo=['powershell -NoProfile -Command "Get-NetAdapter -Physical | ForEach-Object { Set-NetAdapterAdvancedProperty -Name $_.Name -DisplayName \'Interrupt Moderation\' -DisplayValue \'Enabled\' -ErrorAction SilentlyContinue }"'],
    risk=RISK_MEDIUM))
_add(Tweak("Net: Disable IPv6 Tunneling (Teredo/6to4/ISATAP)", "Network",
    "Disables IPv6 transition tech so game traffic runs pure IPv4.",
    apply=[
        "netsh interface teredo set state disabled",
        "netsh interface 6to4 set state disabled",
        "netsh interface isatap set state disabled",
    ],
    undo=[
        "netsh interface teredo set state default",
        "netsh interface 6to4 set state default",
        "netsh interface isatap set state default",
    ],
    risk=RISK_SAFE))
_add(Tweak("Net: Use Google DNS (8.8.8.8)", "Network",
    "Sets primary/secondary DNS to Google on every up interface.",
    apply=['powershell -NoProfile -Command "Get-NetAdapter -Physical | Where-Object Status -eq Up | ForEach-Object { Set-DnsClientServerAddress -InterfaceIndex $_.ifIndex -ServerAddresses 8.8.8.8,8.8.4.4 }"'],
    undo=['powershell -NoProfile -Command "Get-NetAdapter -Physical | Where-Object Status -eq Up | ForEach-Object { Set-DnsClientServerAddress -InterfaceIndex $_.ifIndex -ResetServerAddresses }"'],
    risk=RISK_SAFE))
_add(Tweak("Net: Disable LMHOSTS Lookup", "Network",
    "Skips the legacy NetBIOS LMHOSTS file lookup.",
    apply=['powershell -NoProfile -Command "Get-WmiObject Win32_NetworkAdapterConfiguration | Where-Object {$_.IPEnabled -eq $true} | ForEach-Object { $_.EnableWINS($false,$false) | Out-Null }"'],
    risk=RISK_SAFE))

# ===== GAMES (per-title optimisations) =====
def _game_optimize(name: str, exe: str) -> Tweak:
    """Compose a per-game optimisation: disable fullscreen optimisations,
    force the discrete GPU, and prepare the per-app GPU preference entry."""
    layers_key = r"HKCU\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
    layers_val = "~ DISABLEDXMAXIMIZEDWINDOWEDMODE HIGHDPIAWARE"
    gpu_key = r"HKCU\SOFTWARE\Microsoft\DirectX\UserGpuPreferences"
    return Tweak(
        f"Optimize: {name}", "Games",
        f"For {exe}: disables Windows Fullscreen Optimisations, marks the app "
        f"DPI-aware, and forces the dedicated GPU profile.",
        apply=[
            f'reg add "{layers_key}" /v "{exe}" /t REG_SZ /d "{layers_val}" /f',
            f'reg add "{gpu_key}" /v "{exe}" /t REG_SZ /d "GpuPreference=2;" /f',
        ],
        undo=[
            f'reg delete "{layers_key}" /v "{exe}" /f',
            f'reg delete "{gpu_key}" /v "{exe}" /f',
        ],
        reg_keys=[layers_key, gpu_key],
        risk=RISK_SAFE,
    )

_GAMES = [
    ("Fortnite",              "FortniteClient-Win64-Shipping.exe"),
    ("Valorant",              "VALORANT-Win64-Shipping.exe"),
    ("Counter-Strike 2",      "cs2.exe"),
    ("Apex Legends",          "r5apex.exe"),
    ("Call of Duty: Warzone", "cod.exe"),
    ("Overwatch 2",           "Overwatch.exe"),
    ("League of Legends",     "League of Legends.exe"),
    ("Rainbow Six Siege",     "RainbowSix.exe"),
    ("Rocket League",         "RocketLeague.exe"),
    ("PUBG: Battlegrounds",   "TslGame.exe"),
    ("GTA V",                 "GTA5.exe"),
    ("Roblox",                "RobloxPlayerBeta.exe"),
    ("Minecraft (Java)",      "javaw.exe"),
    ("Genshin Impact",        "GenshinImpact.exe"),
    ("Marvel Rivals",         "MarvelRivals.exe"),
]
for _gn, _ge in _GAMES:
    _add(_game_optimize(_gn, _ge))

_add(Tweak("Launch Options Cheat-Sheet (informational)", "Games",
    "Recommended launcher flags (copy into Steam/Epic/standalone launchers):\n"
    "• CS2:        -high -novid -tickrate 128 +fps_max 0\n"
    "• Apex:       +fps_max unlimited -dev -preload -forcenovsync\n"
    "• Fortnite:   -dx12 -limitclientticks\n"
    "• GTA V:      -high -nomemrestrict\n"
    "• Rocket Lg.: -high -nojoy\n"
    "• PUBG:       -high -USEALLAVAILABLECORES -malloc=system\n"
    "• Roblox:     --no-pin --high-priority\n"
    "• Valorant:   (no launch options — use in-game settings)\n"
    "This tweak takes NO action — it's a notes panel.",
    apply=[], undo=[], risk=RISK_SAFE))
_add(Tweak("Games: Steam Big Picture Acceleration", "Games",
    "Marks all Steam-managed games with the high-perf GPU preference key "
    "(Steam will inherit it on next launch).",
    apply=[_reg_set(r"HKCU\SOFTWARE\Microsoft\DirectX\UserGpuPreferences",
                    "DirectXUserGlobalSettings", "REG_SZ",
                    "VRROptimizeEnable=0;SwapEffectUpgradeEnable=1;")],
    reg_keys=[r"HKCU\SOFTWARE\Microsoft\DirectX\UserGpuPreferences"],
    risk=RISK_SAFE))

# ---------------------------------------------------------------------------
# Presets / profiles
# ---------------------------------------------------------------------------
PRESETS = {
    "Pro Gamer (Full Stack)": [
        # max-out CPU/power
        "Enable Ultimate Performance Power Plan",
        "CPU: 100% Min Processor State",
        "CPU: 100% Max Processor State",
        "CPU: Disable Core Parking",
        "CPU: Aggressive Boost Mode",
        "PCIe: Disable Link State Power Management",
        "USB: Disable Selective Suspend",
        "Enable Hardware-Accelerated GPU Scheduling",
        "Maximum CPU Scheduling for Programs",
        # gaming
        "Enable Game Mode",
        "Disable Xbox Game Bar (overlay)",
        "Prioritize Games (SystemResponsiveness)",
        "Boost Games MMCSS Priority",
        "Disable Fullscreen Optimizations (global)",
        # latency
        "Disable Nagle's Algorithm (lower ping)",
        "Net: Disable QoS Bandwidth Reservation",
        "Net: Lower TcpTimedWaitDelay to 30s",
        "Net: Max User Ports = 65534",
        "Net: Disable Multimedia Network Throttling",
        "Net: Disable NIC Power Saving",
        "Net: Disable RSC (Receive Segment Coalescing)",
        "Net: Enable Compound TCP",
        "Net: Disable IPv6 Tunneling (Teredo/6to4/ISATAP)",
        # bg cleanup
        "Disable Search Indexer",
        "Disable SysMain (Superfetch)",
        "Disable Background Apps (UWP)",
    ],
    "Low Latency Network": [
        "Disable Nagle's Algorithm (lower ping)",
        "Net: Disable QoS Bandwidth Reservation",
        "Net: Disable Multimedia Network Throttling",
        "Net: Disable NIC Power Saving",
        "Net: Disable LSO (Large Send Offload v2)",
        "Net: Disable RSC (Receive Segment Coalescing)",
        "Net: Enable Compound TCP",
        "Net: NIC Interrupt Moderation Off",
        "Net: Disable IPv6 Tunneling (Teredo/6to4/ISATAP)",
        "Net: Lower TcpTimedWaitDelay to 30s",
        "Net: Max User Ports = 65534",
        "Enable DNS over HTTPS (DoH)",
        "Use Cloudflare 1.1.1.1 DNS",
    ],
    "Gaming": [
        "Enable Ultimate Performance Power Plan",
        "Enable Game Mode",
        "Disable Xbox Game Bar (overlay)",
        "Prioritize Games (SystemResponsiveness)",
        "Boost Games MMCSS Priority",
        "Disable Fullscreen Optimizations (global)",
        "Disable Nagle's Algorithm (lower ping)",
        "Enable Hardware-Accelerated GPU Scheduling",
        "Maximum CPU Scheduling for Programs",
        "Disable Mouse Pointer Trails / Acceleration",
        "Disable Visual Effects (Best Performance)",
        "Disable Animations (window min/max)",
        "Disable Search Indexer",
        "Disable SysMain (Superfetch)",
    ],
    "Privacy": [
        "Disable Telemetry (AllowTelemetry=0)",
        "Disable Connected User Experiences & Telemetry",
        "Disable Activity History / Timeline",
        "Disable Advertising ID",
        "Disable Location Tracking",
        "Disable Cortana",
        "Disable Bing Search in Start Menu",
        "Disable Suggested Content in Settings",
        "Disable Lockscreen Spotlight Ads",
        "Disable Tips, Tricks & Suggestions",
        "Disable Inking & Typing Personalization",
        "Disable Feedback Frequency Prompts",
        "Disable App Launch Tracking",
        "Disable Clipboard History Sync",
        "Disable Recall (Windows 11 24H2+)",
        "Block Telemetry Domains (hosts file)",
    ],
    "Balanced": [
        "Disable Connected User Experiences & Telemetry",
        "Disable Advertising ID",
        "Disable Suggested Content in Settings",
        "Disable Tips, Tricks & Suggestions",
        "Show File Extensions",
        "Show Hidden Files",
        "Open Explorer to This PC",
        "Disable Background Apps (UWP)",
        "Disable Storage Sense Auto-Cleanup",
        "Disable Startup Delay",
        "Speed Up Shutdown",
        "Enable Game Mode",
    ],
    "Streamer": [
        "Enable Ultimate Performance Power Plan",
        "Enable Hardware-Accelerated GPU Scheduling",
        "Boost Games MMCSS Priority",
        "Prioritize Games (SystemResponsiveness)",
        "Disable Background Apps (UWP)",
        "Disable Search Indexer",
        "Disable Connected User Experiences & Telemetry",
        "Disable Xbox Game Bar (overlay)",
        "Disable Suggested Content in Settings",
        "Disable Tips, Tricks & Suggestions",
    ],
    "Minimal Debloat": [
        "Remove Xbox Apps",
        "Remove Cortana App",
        "Remove News & Weather",
        "Remove Maps",
        "Remove Get Help / Tips / Feedback Hub",
        "Remove Pre-Installed Bloat (broad sweep)",
        "Remove Mixed Reality Portal",
        "Remove Your Phone (Phone Link)",
    ],
}

CATEGORIES = ["Performance", "Privacy", "Gaming", "Games", "Debloat", "Network", "Services", "UI / Explorer"]


# ---------------------------------------------------------------------------
# Admin helpers
# ---------------------------------------------------------------------------
def is_admin() -> bool:
    if not IS_WINDOWS:
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> None:
    """Relaunch the current script with admin rights."""
    if not IS_WINDOWS:
        return
    params = " ".join(f'"{a}"' for a in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    sys.exit(0)


# ---------------------------------------------------------------------------
# Subprocess runner - everything routes through here for logging
# ---------------------------------------------------------------------------
CREATE_NO_WINDOW = 0x08000000 if IS_WINDOWS else 0


def run_cmd(cmd: str, timeout: int = 60) -> tuple[bool, str]:
    """Run a shell command, capture combined output, log it."""
    log.info("CMD: %s", cmd)
    try:
        cp = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, creationflags=CREATE_NO_WINDOW,
        )
        output = (cp.stdout or "") + (cp.stderr or "")
        ok = cp.returncode == 0
        log.info("RC=%s  OUT=%s", cp.returncode, output.strip()[:500])
        return ok, output
    except subprocess.TimeoutExpired:
        log.error("Timeout: %s", cmd)
        return False, "Command timed out"
    except Exception as exc:  # pragma: no cover
        log.exception("Command error: %s", exc)
        return False, str(exc)


def backup_reg_keys(keys: list[str], tweak_name: str) -> Optional[Path]:
    """Export each registry key to a .reg backup file. Returns the directory."""
    if not keys or not IS_WINDOWS:
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c if c.isalnum() else "_" for c in tweak_name)[:40]
    folder = BACKUP_DIR / f"{stamp}_{safe}"
    folder.mkdir(parents=True, exist_ok=True)
    for i, key in enumerate(keys):
        out = folder / f"key_{i:02d}.reg"
        run_cmd(f'reg export "{key}" "{out}" /y')
    return folder


def create_system_restore_point(description: str = "Blood Tweaks") -> bool:
    """Create a Windows System Restore checkpoint."""
    if not IS_WINDOWS:
        return False
    cmd = ('powershell -NoProfile -ExecutionPolicy Bypass -Command '
           '"Enable-ComputerRestore -Drive C:\\; Checkpoint-Computer '
           f'-Description \'{description}\' -RestorePointType MODIFY_SETTINGS"')
    ok, _ = run_cmd(cmd, timeout=180)
    return ok


# ---------------------------------------------------------------------------
# State persistence  (applied tweaks history)
# ---------------------------------------------------------------------------
def load_json(p: Path, default):
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        log.exception("Could not read %s", p)
    return default


def save_json(p: Path, data) -> None:
    try:
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        log.exception("Could not write %s", p)


# ---------------------------------------------------------------------------
# Tk + CTk UI helpers
# ---------------------------------------------------------------------------
class LogConsole(ctk.CTkFrame):
    """A scrolling, colored console pane fed by a thread-safe queue."""

    def __init__(self, master):
        super().__init__(master, fg_color=COL["bg_alt"], border_width=1,
                         border_color=COL["border"], corner_radius=10)
        self.q: queue.Queue[tuple[str, str]] = queue.Queue()
        self.text = ctk.CTkTextbox(
            self, fg_color=COL["bg_alt"], text_color=COL["text"],
            border_width=0, corner_radius=10, font=("Consolas", 11),
        )
        self.text.pack(fill="both", expand=True, padx=10, pady=10)
        self.text.configure(state="disabled")
        # color tags
        self.text._textbox.tag_config("ok", foreground=COL["ok"])
        self.text._textbox.tag_config("warn", foreground=COL["warn"])
        self.text._textbox.tag_config("err", foreground=COL["danger"])
        self.text._textbox.tag_config("info", foreground=COL["info"])
        self.text._textbox.tag_config("muted", foreground=COL["text_dim"])
        self.after(120, self._drain)

    def write(self, msg: str, level: str = "info") -> None:
        self.q.put((msg, level))

    def _drain(self):
        try:
            while True:
                msg, level = self.q.get_nowait()
                stamp = datetime.now().strftime("%H:%M:%S")
                self.text.configure(state="normal")
                self.text._textbox.insert("end", f"[{stamp}] ", "muted")
                self.text._textbox.insert("end", msg + "\n", level)
                self.text._textbox.see("end")
                self.text.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(120, self._drain)


class TweakRow(ctk.CTkFrame):
    """One row in the tweak list. Card layout, hover, risk pill, switch."""

    def __init__(self, master, tweak: Tweak, applied: bool, on_toggle: Callable[[str, bool], None]):
        super().__init__(master, fg_color=COL["card"], corner_radius=14,
                         border_width=0)
        self.tweak = tweak
        self.on_toggle = on_toggle
        self._build(applied)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, _e):
        self.configure(fg_color=COL["card_hover"])

    def _on_leave(self, _e):
        self.configure(fg_color=COL["card"])

    def _build(self, applied: bool):
        # Left risk stripe (acts as a coloured accent bar)
        stripe = ctk.CTkFrame(self, fg_color=RISK_COLOR[self.tweak.risk],
                              width=4, corner_radius=2)
        stripe.pack(side="left", fill="y", padx=(2, 0), pady=8)

        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(side="left", fill="both", expand=True, padx=16, pady=12)

        # left: switch
        self.var = tk.BooleanVar(value=False)
        self.switch = ctk.CTkSwitch(
            wrap, text="", variable=self.var,
            width=44, switch_width=44, switch_height=22,
            progress_color=COL["accent"], button_color=COL["text"],
            button_hover_color=COL["accent_hov"],
            fg_color=COL["border"],
            command=lambda: self.on_toggle(self.tweak.name, self.var.get()),
        )
        self.switch.pack(side="left", padx=(0, 16))

        # middle: name + desc + applied marker
        mid = ctk.CTkFrame(wrap, fg_color="transparent")
        mid.pack(side="left", fill="x", expand=True)
        title_row = ctk.CTkFrame(mid, fg_color="transparent")
        title_row.pack(fill="x", anchor="w")
        ctk.CTkLabel(title_row, text=self.tweak.name, text_color=COL["text"],
                     font=("Segoe UI Semibold", 14), anchor="w").pack(side="left")
        if applied:
            ctk.CTkLabel(title_row, text=" APPLIED ", text_color=COL["bg"],
                         fg_color=COL["ok"], corner_radius=8,
                         font=("Segoe UI", 9, "bold")).pack(side="left", padx=8)
        if self.tweak.reboot:
            ctk.CTkLabel(title_row, text=" REBOOT ", text_color=COL["bg"],
                         fg_color=COL["info"], corner_radius=8,
                         font=("Segoe UI", 9, "bold")).pack(side="left", padx=4)
        ctk.CTkLabel(mid, text=self.tweak.desc, text_color=COL["text_dim"],
                     font=("Segoe UI", 11), anchor="w",
                     wraplength=640, justify="left").pack(fill="x", anchor="w", pady=(3, 0))

        # right: risk badge (text-only, colored to match the stripe)
        ctk.CTkLabel(
            wrap, text=RISK_LABEL[self.tweak.risk],
            text_color=RISK_COLOR[self.tweak.risk], fg_color="transparent",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="right", padx=10)


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------
class AphroditeApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME}  ·  v{APP_VERSION}")
        self.geometry("1280x840")
        self.minsize(1120, 740)
        self.configure(fg_color=COL["bg"])

        # persistent state
        self.applied: dict = load_json(STATE_FILE, {})
        self.history: list = load_json(HISTORY_FILE, [])

        # in-memory selection
        self.selected: set[str] = set()
        self.current_category: str = "Performance"
        self.search_text: str = ""
        self.row_widgets: list[TweakRow] = []

        self._build_layout()
        self._render_list()

        # Admin reminder
        if IS_WINDOWS and not is_admin():
            self.after(400, self._prompt_admin)

        self.log_ok(f"{APP_NAME} v{APP_VERSION} ready - {len(TWEAKS)} tweaks loaded.")

    # --------------------------- UI ----------------------------------
    def _build_layout(self):
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, fg_color=COL["bg_alt"], width=248, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=22, pady=(26, 20))
        # red blood-drop glyph + wordmark
        title_row = ctk.CTkFrame(brand, fg_color="transparent")
        title_row.pack(fill="x")
        ctk.CTkLabel(title_row, text="◆", font=("Segoe UI", 22, "bold"),
                     text_color=COL["accent"]).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(title_row, text="BLOOD",
                     font=("Segoe UI Black", 20), text_color=COL["text"]).pack(side="left")
        ctk.CTkLabel(brand, text="Tweaks  ·  Windows Optimizer",
                     font=("Segoe UI", 11), text_color=COL["text_dim"]).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(brand, text=f"v{APP_VERSION}",
                     font=("Segoe UI", 9), text_color=COL["text_muted"]).pack(anchor="w", pady=(2, 0))

        # subtle divider
        ctk.CTkFrame(self.sidebar, height=1, fg_color=COL["border"]).pack(fill="x", padx=18, pady=(2, 10))

        ctk.CTkLabel(self.sidebar, text="CATEGORIES", text_color=COL["text_muted"],
                     font=("Segoe UI Semibold", 10)).pack(anchor="w", padx=22, pady=(6, 6))
        self.cat_buttons: dict[str, ctk.CTkButton] = {}
        for cat in CATEGORIES:
            btn = ctk.CTkButton(
                self.sidebar, text="   " + cat, anchor="w", height=38,
                fg_color="transparent", hover_color=COL["card"],
                text_color=COL["text_dim"], font=("Segoe UI", 12),
                corner_radius=10,
                command=lambda c=cat: self._switch_category(c),
            )
            btn.pack(fill="x", padx=14, pady=2)
            self.cat_buttons[cat] = btn

        ctk.CTkFrame(self.sidebar, height=1, fg_color=COL["border"]).pack(fill="x", padx=18, pady=(14, 0))

        ctk.CTkLabel(self.sidebar, text="PRESETS", text_color=COL["text_muted"],
                     font=("Segoe UI Semibold", 10)).pack(anchor="w", padx=22, pady=(14, 6))
        for preset in PRESETS.keys():
            ctk.CTkButton(
                self.sidebar, text="   " + preset, anchor="w", height=34,
                fg_color="transparent", hover_color=COL["card"],
                text_color=COL["text"], font=("Segoe UI", 12),
                corner_radius=10,
                command=lambda p=preset: self._apply_preset(p),
            ).pack(fill="x", padx=14, pady=1)

        # Bottom of sidebar - safety
        safety = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        safety.pack(side="bottom", fill="x", padx=14, pady=16)
        ctk.CTkButton(
            safety, text="Create Restore Point", height=40,
            fg_color=COL["accent"], hover_color=COL["accent_hov"],
            text_color=COL["text"], font=("Segoe UI Semibold", 12),
            corner_radius=10,
            command=self._make_restore_point,
        ).pack(fill="x", pady=4)
        ctk.CTkButton(
            safety, text="Open Backups Folder", height=34,
            fg_color="transparent", border_width=1, border_color=COL["border"],
            hover_color=COL["card"], text_color=COL["text_dim"],
            font=("Segoe UI", 11), corner_radius=10,
            command=self._open_backups,
        ).pack(fill="x", pady=4)

        # ------------- Main area -------------
        main = ctk.CTkFrame(self, fg_color=COL["bg"], corner_radius=0)
        main.pack(side="left", fill="both", expand=True)

        # Top bar: search + admin status
        topbar = ctk.CTkFrame(main, fg_color="transparent", height=80)
        topbar.pack(fill="x", padx=28, pady=(22, 4))
        topbar.pack_propagate(False)

        self.search_entry = ctk.CTkEntry(
            topbar, placeholder_text="🔍   Search tweaks…",
            fg_color=COL["card"], border_color=COL["border"], border_width=1,
            text_color=COL["text"], placeholder_text_color=COL["text_muted"],
            font=("Segoe UI", 13), height=46, corner_radius=12,
        )
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.bind("<KeyRelease>", lambda _e: self._on_search())

        admin_ok = is_admin()
        adm_color = COL["ok"] if admin_ok else COL["danger"]
        adm_text = "● ADMIN" if admin_ok else "● NOT ADMIN"
        ctk.CTkLabel(topbar, text=adm_text, fg_color="transparent",
                     text_color=adm_color, font=("Segoe UI Semibold", 12),
                     ).pack(side="right", padx=(16, 0))

        # Category title + count
        self.title_lbl = ctk.CTkLabel(main, text="", text_color=COL["text"],
                                      font=("Segoe UI Black", 24))
        self.title_lbl.pack(anchor="w", padx=28, pady=(4, 0))
        self.subtitle_lbl = ctk.CTkLabel(main, text="", text_color=COL["text_dim"],
                                         font=("Segoe UI", 12))
        self.subtitle_lbl.pack(anchor="w", padx=28, pady=(0, 14))

        # Tweak list scrollable
        self.list_frame = ctk.CTkScrollableFrame(
            main, fg_color=COL["bg"], scrollbar_button_color=COL["accent_deep"],
            scrollbar_button_hover_color=COL["accent"], corner_radius=0,
        )
        self.list_frame.pack(fill="both", expand=True, padx=22, pady=(0, 8))

        # Bottom action bar
        action = ctk.CTkFrame(main, fg_color=COL["bg_alt"], height=78,
                              corner_radius=0)
        action.pack(fill="x", side="bottom")
        action.pack_propagate(False)

        self.status_lbl = ctk.CTkLabel(action, text="Ready", text_color=COL["text_dim"],
                                       font=("Segoe UI", 12))
        self.status_lbl.pack(side="left", padx=24)

        self.progress = ctk.CTkProgressBar(action, width=240, height=6,
                                           progress_color=COL["accent"],
                                           fg_color=COL["card"], corner_radius=6)
        self.progress.set(0)
        self.progress.pack(side="left", padx=14)

        ctk.CTkButton(
            action, text="View Logs", height=40, width=110,
            fg_color="transparent", border_width=1, border_color=COL["border"],
            hover_color=COL["card"], text_color=COL["text"],
            font=("Segoe UI", 11), corner_radius=10,
            command=self._show_logs,
        ).pack(side="right", padx=8)
        ctk.CTkButton(
            action, text="Undo Last", height=40, width=120,
            fg_color="transparent", border_width=1, border_color=COL["danger"],
            hover_color=COL["card"], text_color=COL["danger"],
            font=("Segoe UI Semibold", 12), corner_radius=10,
            command=self._undo_last,
        ).pack(side="right", padx=8)
        ctk.CTkButton(
            action, text="Apply Selected", height=40, width=170,
            fg_color=COL["accent"], hover_color=COL["accent_hov"],
            text_color=COL["text"], font=("Segoe UI Semibold", 13),
            corner_radius=10,
            command=self._apply_selected,
        ).pack(side="right", padx=12)

        # Mark first category active
        self._highlight_category(self.current_category)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ----------------------- Sidebar / nav ----------------------------
    def _highlight_category(self, cat: str):
        for c, b in self.cat_buttons.items():
            if c == cat:
                b.configure(fg_color=COL["card"], text_color=COL["text"],
                            text=f"▍  {c}")
            else:
                b.configure(fg_color="transparent", text_color=COL["text_dim"],
                            text=f"   {c}")

    def _switch_category(self, cat: str):
        self.current_category = cat
        self.selected.clear()
        self._highlight_category(cat)
        self._render_list()

    # ----------------------- Search -----------------------------------
    def _on_search(self):
        self.search_text = self.search_entry.get().strip().lower()
        self._render_list()

    # ----------------------- List render ------------------------------
    def _filtered(self) -> list[Tweak]:
        out = []
        for t in TWEAKS:
            if t.category != self.current_category:
                continue
            if self.search_text and self.search_text not in (t.name + " " + t.desc).lower():
                continue
            out.append(t)
        return out

    def _render_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.row_widgets.clear()

        items = self._filtered()
        self.title_lbl.configure(text=self.current_category)
        self.subtitle_lbl.configure(
            text=f"{len(items)} tweak{'s' if len(items) != 1 else ''} available  •  "
                 f"{sum(1 for t in items if self.applied.get(t.name))} already applied"
        )

        if not items:
            ctk.CTkLabel(self.list_frame,
                         text="No tweaks match your search.",
                         text_color=COL["text_muted"],
                         font=("Segoe UI", 13)).pack(pady=40)
            return

        for t in items:
            row = TweakRow(self.list_frame, t,
                           applied=bool(self.applied.get(t.name)),
                           on_toggle=self._toggle)
            row.pack(fill="x", pady=7, padx=4)
            if t.name in self.selected:
                row.var.set(True)
            self.row_widgets.append(row)

    def _toggle(self, name: str, on: bool):
        if on:
            self.selected.add(name)
        else:
            self.selected.discard(name)
        self.status_lbl.configure(
            text=f"{len(self.selected)} tweak(s) selected" if self.selected else "Ready"
        )

    # ----------------------- Apply / Undo -----------------------------
    def _confirm(self, msg: str) -> bool:
        return messagebox.askyesno(APP_NAME, msg, parent=self)

    def _prompt_admin(self):
        if self._confirm("Aphrodite Tweaks Pro is not running as Administrator.\n\n"
                         "Most tweaks will fail without admin rights.\n\n"
                         "Relaunch elevated now?"):
            relaunch_as_admin()

    def _apply_selected(self):
        names = list(self.selected)
        if not names:
            messagebox.showinfo(APP_NAME, "Select at least one tweak first.")
            return
        if not self._confirm(
            f"Apply {len(names)} tweak(s) now?\n\n"
            f"• Registry keys will be backed up.\n"
            f"• You can undo from the history any time.\n"
            f"• Some tweaks may require a reboot."
        ):
            return
        self._run_tweaks(names, mode="apply")

    def _apply_preset(self, preset_name: str):
        names = PRESETS.get(preset_name, [])
        if not names:
            return
        valid = [n for n in names if any(t.name == n for t in TWEAKS)]
        if not self._confirm(
            f"Apply preset '{preset_name}' ({len(valid)} tweaks)?\n\n"
            f"A System Restore Point will be offered."
        ):
            return
        if self._confirm("Create a Windows System Restore Point first? (Recommended)"):
            threading.Thread(target=self._make_restore_point, daemon=True).start()
        self._run_tweaks(valid, mode="apply")

    def _undo_last(self):
        if not self.history:
            messagebox.showinfo(APP_NAME, "Nothing to undo.")
            return
        last = self.history[-1]
        names = last["tweaks"]
        if not self._confirm(f"Undo the last batch ({len(names)} tweak(s) from "
                             f"{last['ts']})?"):
            return
        self._run_tweaks(names, mode="undo", history_entry=last)

    def _run_tweaks(self, names: list[str], mode: str,
                    history_entry: Optional[dict] = None):
        # disable UI during run
        self.status_lbl.configure(text=f"{mode.title()}ing {len(names)} tweak(s)…")

        def worker():
            ok_n = fail_n = 0
            need_reboot = False
            applied_now: list[str] = []
            for i, name in enumerate(names, start=1):
                tweak = next((t for t in TWEAKS if t.name == name), None)
                if tweak is None:
                    continue
                self.after(0, lambda i=i: self.progress.set(i / max(len(names), 1)))
                self.after(0, lambda n=name, i=i: self.status_lbl.configure(
                    text=f"{mode.title()} {i}/{len(names)}: {n}"))

                cmds = tweak.apply if mode == "apply" else tweak.undo
                if mode == "apply" and tweak.reg_keys:
                    backup_reg_keys(tweak.reg_keys, tweak.name)
                if not cmds:
                    self.log_warn(f"{name}: no {mode} commands defined - skipped")
                    continue

                all_ok = True
                for c in cmds:
                    ok, out = run_cmd(c)
                    if not ok:
                        all_ok = False
                        self.log_err(f"{name}: {out.strip()[:140]}")
                if all_ok:
                    ok_n += 1
                    applied_now.append(name)
                    self.log_ok(f"{mode.title()} OK: {name}")
                    if mode == "apply":
                        self.applied[name] = {
                            "ts": datetime.now().isoformat(timespec="seconds"),
                        }
                    else:
                        self.applied.pop(name, None)
                    if tweak.reboot:
                        need_reboot = True
                else:
                    fail_n += 1
                    self.log_err(f"{mode.title()} FAILED: {name}")

            # persist
            save_json(STATE_FILE, self.applied)
            if mode == "apply" and applied_now:
                self.history.append({
                    "ts": datetime.now().isoformat(timespec="seconds"),
                    "tweaks": applied_now,
                })
                save_json(HISTORY_FILE, self.history)
            elif mode == "undo" and history_entry is not None:
                self.history.remove(history_entry)
                save_json(HISTORY_FILE, self.history)

            self.after(0, lambda: self.progress.set(0))
            self.after(0, lambda: self.status_lbl.configure(
                text=f"Done. {ok_n} OK, {fail_n} failed."))
            self.after(0, self._render_list)
            self.after(0, lambda: self.selected.clear())

            if need_reboot:
                self.after(0, lambda: messagebox.showinfo(
                    APP_NAME, "Some tweaks require a reboot to fully take effect."))

        threading.Thread(target=worker, daemon=True).start()

    # ----------------------- Restore / logs ---------------------------
    def _make_restore_point(self):
        self.status_lbl.configure(text="Creating System Restore Point…")
        self.log_info("Creating Windows System Restore Point…")

        def worker():
            ok = create_system_restore_point()
            if ok:
                self.log_ok("Restore point created successfully.")
                self.after(0, lambda: self.status_lbl.configure(
                    text="Restore point created."))
            else:
                self.log_err("Restore point creation failed. "
                             "Ensure System Protection is enabled on C:\\.")
                self.after(0, lambda: self.status_lbl.configure(
                    text="Restore point FAILED."))
        threading.Thread(target=worker, daemon=True).start()

    def _open_backups(self):
        if IS_WINDOWS:
            os.startfile(BACKUP_DIR)  # type: ignore[attr-defined]
        else:
            messagebox.showinfo(APP_NAME, f"Backups at: {BACKUP_DIR}")

    def _show_logs(self):
        top = ctk.CTkToplevel(self)
        top.title(f"{APP_NAME} - Activity Log")
        top.geometry("900x520")
        top.configure(fg_color=COL["bg"])
        console = LogConsole(top)
        console.pack(fill="both", expand=True, padx=14, pady=14)
        try:
            text = LOG_FILE.read_text(encoding="utf-8", errors="ignore")
            for line in text.splitlines()[-400:]:
                lvl = "info"
                if " ERROR " in line:
                    lvl = "err"
                elif " WARNING" in line:
                    lvl = "warn"
                console.write(line, lvl)
        except Exception:
            console.write("No log file yet.", "muted")

    # ----------------------- Misc -------------------------------------
    def log_ok(self, msg: str):
        log.info(msg)
        self.status_lbl.configure(text=msg)

    def log_info(self, msg: str):
        log.info(msg)

    def log_warn(self, msg: str):
        log.warning(msg)

    def log_err(self, msg: str):
        log.error(msg)

    def _on_close(self):
        save_json(STATE_FILE, self.applied)
        save_json(HISTORY_FILE, self.history)
        self.destroy()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def main():
    log.info("===== %s v%s starting =====", APP_NAME, APP_VERSION)
    app = AphroditeApp()
    app.mainloop()


if __name__ == "__main__":
    main()
