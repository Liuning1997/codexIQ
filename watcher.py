"""Starts the radar when Codex opens and stops it when Codex exits."""

from __future__ import annotations

import subprocess
import sys
import time
import ctypes
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
RADAR = APP_DIR / "radar.py"
DISMISS_FLAG = APP_DIR / ".dismissed_for_codex_session"
POLL_SECONDS = 2


def codex_running() -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True, text=True, encoding="utf-8", errors="ignore", creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return any(line.lstrip('"').lower().startswith("codex.exe\"") for line in result.stdout.splitlines())
    except Exception:
        return False


def start_radar() -> subprocess.Popen:
    return subprocess.Popen([sys.executable, str(RADAR)], cwd=APP_DIR, creationflags=subprocess.CREATE_NO_WINDOW)


def main() -> None:
    # Startup-folder entries can be invoked more than once by Windows. Keep one
    # watcher so only one dashboard can ever be shown for a Codex session.
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    ctypes.set_last_error(0)
    mutex = kernel32.CreateMutexW(None, False, "Global\\CodexRadarWatcher")
    if not mutex or ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        return
    radar: subprocess.Popen | None = None
    was_running = False
    while True:
        running = codex_running()
        if running and not was_running:
            DISMISS_FLAG.unlink(missing_ok=True)
        if running:
            if radar is None or radar.poll() is not None:
                if not DISMISS_FLAG.exists():
                    radar = start_radar()
        elif radar is not None and radar.poll() is None:
            radar.terminate()
            try:
                radar.wait(timeout=4)
            except subprocess.TimeoutExpired:
                radar.kill()
            radar = None
        was_running = running
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
