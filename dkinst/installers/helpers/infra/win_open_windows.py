import ctypes
from ctypes import wintypes
import time
import os

import psutil

from .printing import printc


if os.name == "nt":
    user32 = ctypes.windll.user32

    EnumWindows = user32.EnumWindows
    GetWindowTextLengthW = user32.GetWindowTextLengthW
    GetWindowTextW = user32.GetWindowTextW
    IsWindowVisible = user32.IsWindowVisible
    GetWindowThreadProcessId = user32.GetWindowThreadProcessId
    PostMessageW = user32.PostMessageW

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    WM_CLOSE = 0x0010

    dwmapi = ctypes.windll.dwmapi  # Desktop Window Manager API (Vista+)

    DWMWA_CLOAKED = 14  # DwmGetWindowAttribute attribute for cloaked windows

    # Get our own console window handle so we can skip it
    kernel32 = ctypes.windll.kernel32
    kernel32.GetConsoleWindow.restype = wintypes.HWND
    CURRENT_CONSOLE_HWND = kernel32.GetConsoleWindow()


    class RECT(ctypes.Structure):
        _fields_ = [
            ("left",   wintypes.LONG),
            ("top",    wintypes.LONG),
            ("right",  wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]


"""
==============================================
Open Windows Enumeration and Closing Functions.

Usage example:
# inspect/handle currently open windows
open_windows = get_open_windows()
if force:
    if open_windows:
        printc("[!] --force specified. Closing all currently open windows before uninstall.", "yellow")
        print_open_windows(open_windows)
        close_windows(open_windows)
    else:
        print("[+] No windows to close in force mode.")
else:
    # Just show them and tell the user they must close them
    print_open_windows(open_windows)
    if open_windows:
        printc(
            "[!] Please save your work and close these windows, then run uninstall again or use the '--force' argument for script to close the windows for you.\n",
            "yellow",
        )
        return 1
"""


# noinspection PyUnresolvedReferences
def get_open_windows() -> list[dict]:
    """
    Enumerate all *actually visible* top-level windows and return a list of
    dicts: {"hwnd", "title", "pid", "exe"}.

    "Actually visible" here means:
      - Window has WS_VISIBLE
      - Not minimized (IsIconic == False)
      - Not DWM-cloaked (e.g. on another virtual desktop / UWP background)
      - Has a non-empty title
      - Has a reasonable on-screen size
      - Not obvious shell surfaces like the desktop ("Program Manager")
    """
    windows: list[dict] = []

    # noinspection PyArgumentList,PyUnresolvedReferences
    @EnumWindowsProc
    def _enum_proc(hwnd, lparam):
        # Skip the console window that is running this script
        if CURRENT_CONSOLE_HWND and hwnd == CURRENT_CONSOLE_HWND:
            return True

        # 1) Basic visibility
        if not user32.IsWindowVisible(hwnd):
            return True

        # 2) Skip minimized windows – user can't see them
        if user32.IsIconic(hwnd):  # SW_SHOWMINIMIZED
            return True

        # 3) Skip cloaked (off-desktop / UWP / other virtual desktop) windows
        if dwmapi is not None:
            cloaked = wintypes.DWORD()
            hr = dwmapi.DwmGetWindowAttribute(
                hwnd,
                DWMWA_CLOAKED,
                ctypes.byref(cloaked),
                ctypes.sizeof(cloaked),
            )
            if hr == 0 and cloaked.value != 0:
                # 0 == S_OK
                return True

        # 4) Size filter – ignore tiny helper/tool windows
        rect = RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        width = rect.right - rect.left
        height = rect.bottom - rect.top

        # tune thresholds if you like
        if width < 80 or height < 40:
            return True

        # 5) Title filter
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True

        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        if not title:
            return True

        # Skip the desktop / Program Manager explicitly
        if title == "Program Manager":
            return True

        # 6) Class filter – skip well-known shell surfaces
        class_buf = ctypes.create_unicode_buffer(256)
        if user32.GetClassNameW(hwnd, class_buf, 256):
            classname = class_buf.value
            if classname in ("Progman", "WorkerW", "Shell_TrayWnd"):
                return True

        # 7) Process info
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        pid_val = pid.value

        # Skip our own console window (the script that is running)
        if pid_val == os.getpid():
            return True

        try:
            proc = psutil.Process(pid_val)
            exe = proc.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            exe = "unknown"

        windows.append(
            {
                "hwnd": hwnd,
                "title": title,
                "pid": pid_val,
                "exe": exe,
            }
        )
        return True  # continue enumeration

    user32.EnumWindows(_enum_proc, 0)
    return windows


def print_open_windows(windows: list[dict]) -> None:
    if not windows:
        print("[+] No visible top-level windows detected.")
        return

    printc("[!] The following windows are currently open:", "yellow")
    for w in windows:
        print(f"    PID {w['pid']:>6}  ({w['exe']})  -  {w['title']}")


# noinspection PyUnresolvedReferences
def close_windows(windows: list[dict]) -> None:
    """
    Politely ask windows to close using WM_CLOSE.
    (Does not force-kill the processes; less risk of data loss.)
    """
    if not windows:
        return

    print(f"[+] Attempting to close {len(windows)} windows...")
    for w in windows:
        hwnd = w["hwnd"]
        # PostMessage, do not block; WM_CLOSE is the normal "close window" request
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)

    # Small delay to give apps a chance to close cleanly
    time.sleep(3.0)


"""
========================================================================================================================
Specialized msedge.exe Process and Window Handling Functions.
These can be used to detect and close any Edge windows/processes that
were spawned as part of an uninstall that opens Edge to show a web page.

Usage example:
# --- Take snapshot of msedge.exe BEFORE uninstall ---
# --- Snapshots before uninstall ---
old_msedge_procs = get_msedge_snapshot()
old_msedge_windows = get_msedge_window_handles()

if old_msedge_procs:
    print(f"[+] Existing msedge.exe PIDs before uninstall: {sorted(old_msedge_procs.keys())}")
else:
    print("[+] No msedge.exe processes running before uninstall.")

rc: int = msis.run_msi(
    uninstall=True,
    guid=guid,
    silent_progress_bar=True,
    log_file_path=f"{installer_dir}{os.sep}uninstall.log",
    terminate_required_processes=True,
    disable_msi_restart_manager=True,
)

# --- After uninstall, kill only NEW msedge.exe processes ---
kill_new_msedge_processes(old_msedge_procs, wait_seconds=5.0)
close_new_msedge_windows(old_msedge_windows, wait_seconds=5.0)
"""

def get_msedge_snapshot() -> dict[int, float]:
    """Return {pid: create_time} for all msedge.exe processes."""
    snapshot: dict[int, float] = {}
    for proc in psutil.process_iter(attrs=["pid", "name", "create_time"]):
        try:
            if (proc.info.get("name") or "").lower() == "msedge.exe":
                snapshot[proc.info["pid"]] = float(proc.info["create_time"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return snapshot


def kill_new_msedge_processes(old_snapshot: dict[int, float], wait_seconds: float = 5.0) -> None:
    """
    Kill msedge.exe processes that weren't in old_snapshot.

    We also wait a short period to catch Edge processes spawned a bit *after*
    the MSI finishes.
    """
    deadline = time.time() + wait_seconds

    while True:
        current_snapshot: dict[int, float] = {}
        procs_by_pid: dict[int, psutil.Process] = {}

        for proc in psutil.process_iter(attrs=["pid", "name", "create_time"]):
            try:
                if (proc.info.get("name") or "").lower() == "msedge.exe":
                    pid = proc.info["pid"]
                    ctime = float(proc.info["create_time"])
                    current_snapshot[pid] = ctime
                    procs_by_pid[pid] = proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        new_pids: list[int] = []
        for pid, ctime in current_snapshot.items():
            old_ctime = old_snapshot.get(pid)
            # New if PID wasn't there before, or create_time changed (PID reuse)
            if old_ctime is None or abs(old_ctime - ctime) > 1e-3:
                new_pids.append(pid)

        if not new_pids:
            print("[+] No new msedge.exe processes to kill.")
            return

        print(f"[+] Killing new msedge.exe processes: {sorted(new_pids)}")
        for pid in new_pids:
            proc = procs_by_pid.get(pid)
            if not proc:
                continue
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except psutil.TimeoutExpired:
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # If we still have time, loop again in case more appear.
        if time.time() >= deadline:
            return

        time.sleep(0.5)


def get_msedge_window_handles() -> set[int]:
    """
    Return a set of HWNDs for visible top-level msedge.exe windows.
    """

    handles: set[int] = set()

    # noinspection PyArgumentList
    @EnumWindowsProc
    def callback(hwnd, lParam):
        # Ignore invisible / empty-title windows
        if not IsWindowVisible(hwnd):
            return True

        length = GetWindowTextLengthW(hwnd)
        if length == 0:
            return True

        # Get owning process ID
        pid = wintypes.DWORD()
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        try:
            proc = psutil.Process(pid.value)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return True

        if proc.name().lower() != "msedge.exe":
            return True

        handles.add(int(hwnd))
        return True

    EnumWindows(callback, 0)
    return handles


def close_new_msedge_windows(old_handles: set[int], wait_seconds: float = 5.0) -> None:
    """
    Close new Edge top-level windows (HWNDs not present in old_handles).
    """
    deadline = time.time() + wait_seconds

    while True:
        current_handles = get_msedge_window_handles()
        new_handles = current_handles - old_handles

        if not new_handles:
            print("[+] No new msedge windows to close.")
            return

        print(f"[+] Closing new msedge windows: {list(new_handles)}")
        for hwnd in new_handles:
            # Equivalent to clicking the [X] button
            PostMessageW(hwnd, WM_CLOSE, 0, 0)

        if time.time() >= deadline:
            return

        time.sleep(0.5)


"""
========================================================================================================================
Top-Level Uninstall Handling with Process and Window Cleanup.
Ensure that any windows/processes spawned during some process execution are properly closed/killed.
Usage example:


# --- Take snapshot of processes + windows BEFORE uninstall ---
old_proc_snapshot = win_open_windows.get_process_snapshot()
old_window_handles = win_open_windows.get_window_handles_snapshot()

if old_proc_snapshot:
    print(f"[+] Existing PIDs before uninstall: {sorted(old_proc_snapshot.keys())}")
else:
    print("[+] No processes running before uninstall.")

# Uninstallation with no intervention works only with /qb.
# For some reason, /qn does asks for password, but even providing 'PASSWORD=""' does not work, and it returns 1603.
rc: int = msis.run_msi(
    uninstall=True,
    guid=guid,
    silent_progress_bar=True,
    log_file_path=f"{installer_dir}{os.sep}uninstall.log",
    terminate_required_processes=True,
    disable_msi_restart_manager=True,
)

# --- After uninstall, close any NEW windows and kill only NEW processes ---
new_windows = win_open_windows.close_new_windows(old_window_handles, wait_seconds=5.0)

new_pids = {int(w["pid"]) for w in new_windows if w.get("pid") is not None}
new_exes = {
    str(w.get("exe") or "").lower()
    for w in new_windows
    if str(w.get("exe") or "").strip().lower() not in ("", "unknown")
}

win_open_windows.kill_new_processes(
    old_proc_snapshot,
    wait_seconds=5.0,
    include_pids=new_pids if new_pids else None,
    include_names=new_exes if new_exes else None,
)
"""


def get_window_handles_snapshot() -> set[int]:
    """Return a set of HWNDs for currently visible top-level windows."""
    return {int(w["hwnd"]) for w in get_open_windows()}


def get_process_snapshot() -> dict[int, float]:
    """Return {pid: create_time} for all processes visible to the current user."""
    snapshot: dict[int, float] = {}
    for proc in psutil.process_iter(attrs=["pid", "create_time"]):
        try:
            pid = int(proc.info["pid"])
            ctime = float(proc.info.get("create_time") or 0.0)
            snapshot[pid] = ctime
        except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError, TypeError, ValueError):
            continue
    return snapshot


def close_new_windows(old_handles: set[int], wait_seconds: float = 5.0) -> list[dict]:
    """
    Close newly opened visible top-level windows (HWNDs not present in old_handles)
    by posting WM_CLOSE.

    Returns a list of the new window dicts ("hwnd", "title", "pid", "exe") that
    were detected during the close attempts.
    """
    deadline = time.time() + wait_seconds
    seen_hwnds: set[int] = set()
    new_windows_all: list[dict] = []

    while True:
        current = get_open_windows()
        new_windows = [w for w in current if int(w["hwnd"]) not in old_handles]

        if not new_windows:
            return new_windows_all

        to_close = []
        for w in new_windows:
            hwnd = int(w["hwnd"])
            if hwnd in seen_hwnds:
                continue
            seen_hwnds.add(hwnd)
            new_windows_all.append(w)
            to_close.append(hwnd)

        for hwnd in to_close:
            PostMessageW(hwnd, WM_CLOSE, 0, 0)

        if time.time() >= deadline:
            return new_windows_all

        time.sleep(0.5)


def kill_new_processes(
        old_snapshot: dict[int, float],
        wait_seconds: float = 5.0,
        include_names: set[str] | None = None,
        include_pids: set[int] | None = None,
) -> None:
    """
    Terminate *new* processes (not present in old_snapshot, or with changed create_time).

    If include_names/include_pids are provided, only processes matching:
      (name in include_names) OR (pid in include_pids)
    are targeted.
    """
    deadline = time.time() + wait_seconds
    include_names_lc = {n.lower() for n in include_names} if include_names else None

    while True:
        current_snapshot: dict[int, float] = {}
        procs_by_pid: dict[int, psutil.Process] = {}
        names_by_pid: dict[int, str] = {}

        for proc in psutil.process_iter(attrs=["pid", "name", "create_time"]):
            try:
                pid = int(proc.info.get("pid"))
                ctime = float(proc.info.get("create_time") or 0.0)
                name = (proc.info.get("name") or "").lower()
                current_snapshot[pid] = ctime
                procs_by_pid[pid] = proc
                names_by_pid[pid] = name
            except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError, ValueError):
                continue

        # New if PID wasn't there before, or create_time changed (PID reuse)
        new_pids_all = [
            pid for pid, ctime in current_snapshot.items()
            if old_snapshot.get(pid) is None or abs(old_snapshot[pid] - ctime) > 1e-3
        ]

        candidates: list[int] = []
        for pid in new_pids_all:
            name = names_by_pid.get(pid, "")
            if include_names_lc is None and include_pids is None:
                candidates.append(pid)
                continue
            if (include_pids is not None and pid in include_pids) or (include_names_lc is not None and name in include_names_lc):
                candidates.append(pid)

        if not candidates:
            return

        for pid in candidates:
            proc = procs_by_pid.get(pid)
            if not proc:
                continue
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except psutil.TimeoutExpired:
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if time.time() >= deadline:
            return

        time.sleep(0.5)
