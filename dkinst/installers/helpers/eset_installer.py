"""
Automate install/uninstall of ESET Internet Security on Windows.

- --install   Download and silently install the latest ESET Internet Security
- --uninstall Silently uninstall ESET Internet Security

Run this script from an elevated (administrator) command prompt.
"""

import argparse
import os
import struct
import subprocess
import sys
import re
import shutil
import ctypes
from ctypes import wintypes
import time

import psutil

from .infra import registrys, msis
from .infra.printing import printc

from atomicshop import web


VERSION: str = "1.0.0"
RELEASE_COMMENT: str = "Initial"


# Official "latest" offline installer URLs for ESET Internet Security (home product) :contentReference[oaicite:2]{index=2}
ESET_DOWNLOAD_URL_64 = "https://download.eset.com/com/eset/apps/home/eis/windows/latest/eis_nt64.exe"
ESET_DOWNLOAD_URL_32 = "https://download.eset.com/com/eset/apps/home/eis/windows/latest/eis_nt32.exe"

_GUID_RE = re.compile(r"{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}}")


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


# noinspection PyUnresolvedReferences
def _get_open_windows() -> list[dict]:
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


def _print_open_windows(windows: list[dict]) -> None:
    if not windows:
        print("[+] No visible top-level windows detected.")
        return

    printc("[!] The following windows are currently open:", "yellow")
    for w in windows:
        print(f"    PID {w['pid']:>6}  ({w['exe']})  -  {w['title']}")


# noinspection PyUnresolvedReferences
def _close_windows(windows: list[dict]) -> None:
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


def _get_system_architecture_bits() -> int:
    # 64-bit Python on 64-bit Windows -> 64, 32-bit -> 32
    return struct.calcsize("P") * 8


def install_eset_internet_security(
        installer_dir: str,
        force_download: bool = False,
) -> int:
    """Download and silently install ESET Internet Security."""

    bits = _get_system_architecture_bits()

    # Auto-select installer based on OS architecture
    download_url = ESET_DOWNLOAD_URL_64 if bits == 64 else ESET_DOWNLOAD_URL_32

    if installer_dir:
        os.makedirs(installer_dir, exist_ok=True)

    installer_path = web.download(download_url, target_directory=installer_dir, overwrite=force_download)

    # Silent install switches documented for ESET Internet Security :contentReference[oaicite:3]{index=3}
    cmd = [
        installer_path,
        "--silent",
        "--accepteula",
        "--msi-property-ehs",
        "PRODUCTTYPE=eis",
    ]

    print(f"[+] Running installer: {' '.join(cmd)}")
    completed = subprocess.run(cmd, check=False)

    if completed.returncode != 0:
        printc(f"[!] Error installing ESET Internet Security. Exited with code {completed.returncode}\n"
               f"Installer is in: {installer_path}", "red")

        return completed.returncode

    # Removing only on success.
    print(f"[+] Removing installer file: {installer_path}")
    os.remove(installer_path)
    shutil.rmtree(installer_dir)

    printc("[+] ESET Internet Security installation completed.", "green")

    return 0


def _find_eset_uninstall_string():
    """
    Locate ESET Internet Security / ESET Security uninstall string in registry.

    Returns the uninstall command line (string) or None if not found.
    """

    return registrys.find_uninstall_string(["ESET Internet Security", "ESET Security"])


def _get_guid(uninstall_string: str) -> str | None:
    """
    Find the product GUID in the uninstall string.
    """
    s = uninstall_string.strip()

    # Try to pull out a product GUID from the uninstall string
    m = _GUID_RE.search(s)
    if m:
        guid = m.group(0)
        return guid
    else:
        return None


def _get_msedge_snapshot() -> dict[int, float]:
    """Return {pid: create_time} for all msedge.exe processes."""
    snapshot: dict[int, float] = {}
    for proc in psutil.process_iter(attrs=["pid", "name", "create_time"]):
        try:
            if (proc.info.get("name") or "").lower() == "msedge.exe":
                snapshot[proc.info["pid"]] = float(proc.info["create_time"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return snapshot


def _kill_new_msedge_processes(old_snapshot: dict[int, float], wait_seconds: float = 5.0) -> None:
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


def _get_msedge_window_handles() -> set[int]:
    """
    Return a set of HWNDs for visible top-level msedge.exe windows.
    """

    handles: set[int] = set()

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


def _close_new_msedge_windows(old_handles: set[int], wait_seconds: float = 5.0) -> None:
    """
    Close new Edge top-level windows (HWNDs not present in old_handles).
    """
    deadline = time.time() + wait_seconds

    while True:
        current_handles = _get_msedge_window_handles()
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


def uninstall_eset_internet_security(
        installer_dir: str,
        force: bool = False
) -> int:
    """
    Silently uninstall ESET Internet Security.

    Also: "%ProgramFiles%\ESET\ESET Security\callmsi.exe" /x {GUID} /qb! REBOOT=ReallySuppress

    :param installer_dir: Directory will be used to save the uninstallation log.
    :param force: If True, will close any open windows before uninstalling.
    :return: Exit code from uninstall process.
    """

    # inspect/handle currently open windows
    open_windows = _get_open_windows()
    if force:
        if open_windows:
            printc("[!] --force specified. Closing all currently open windows before uninstall.", "yellow")
            _print_open_windows(open_windows)
            _close_windows(open_windows)
        else:
            print("[+] No windows to close in force mode.")
    else:
        # Just show them and tell the user they must close them
        _print_open_windows(open_windows)
        if open_windows:
            printc(
                "[!] Please save your work and close these windows, then run uninstall again or use the '--force' argument for script to close the windows for you.\n",
                "yellow",
            )
            return 1

    uninstall_string = _find_eset_uninstall_string()
    if not uninstall_string:
        printc("Could not find an installed ESET Internet Security / ESET Security instance.", "red")
        return 1

    guid: str = _get_guid(uninstall_string)
    print(f"[+] Extracted GUID: {guid}")

    os.makedirs(installer_dir, exist_ok=True)

    # --- Take snapshot of msedge.exe BEFORE uninstall ---
    # --- Snapshots before uninstall ---
    old_msedge_procs = _get_msedge_snapshot()
    old_msedge_windows = _get_msedge_window_handles()

    if old_msedge_procs:
        print(f"[+] Existing msedge.exe PIDs before uninstall: {sorted(old_msedge_procs.keys())}")
    else:
        print("[+] No msedge.exe processes running before uninstall.")

    # Uninstallation with no intervention works only with /qb.
    # For some reason, /qn does asks for password, but even providing 'PASSWORD=""' does not work, and it returns 1603.
    rc: int = msis.run_msi(
        uninstall=True,
        guid=guid,
        silent_progress_bar=True,
        log_file_path=f"{installer_dir}{os.sep}uninstall.log",
        terminate_required_processes=True,
        disable_msi_restart_manager=True,
        additional_args='PASSWORD=""',
    )

    # --- After uninstall, kill only NEW msedge.exe processes ---
    _kill_new_msedge_processes(old_msedge_procs, wait_seconds=5.0)
    _close_new_msedge_windows(old_msedge_windows, wait_seconds=5.0)

    # 0    = success
    # 3010 = success, reboot required
    # 1641 = success, reboot initiated
    # if completed.returncode not in (0, 3010, 1641):
    #     printc(f"[!] Error uninstalling ESET Internet Security. Exit code: {completed.returncode}", "red")
    #     return completed.returncode
    #
    # if completed.returncode in (3010, 1641):
    #     printc("[+] ESET Internet Security uninstall completed. A reboot is required.", "yellow")
    # else:
    #     printc("[+] ESET Internet Security uninstall completed.", "green")

    return rc


def _make_parser():
    parser = argparse.ArgumentParser(
        description="Download, install or uninstall ESET Internet Security on Windows."
    )

    # One of --install / --uninstall is required
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--install",
        action="store_true",
        help="Download and install the latest ESET Internet Security.",
    )
    group.add_argument(
        "--installer-dir",
        type=str,
        default=None,
        help="The path where to download the installer. Need only the directory, no need for file name.\n"
             "If not provided, %TEMP% directory will be used.",
    )
    group.add_argument(
        "--uninstall",
        action="store_true",
        help="Uninstall ESET Internet Security.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Install: Force re-download the installer even if it already exists in the specified directory.\n"
             "Uninstall: Close any open windows before uninstalling.",
    )

    return parser


def main(
        install: bool = False,
        installer_dir: str = None,
        uninstall: bool = False,
        force: bool = False,
) -> int:
    if not install and not uninstall:
        printc("[!] You must specify either --install or --uninstall.", "red")
        return 1
    if install and uninstall:
        printc("[!] You cannot specify both --install and --uninstall at the same time.", "red")
        return 1

    if install:
        return install_eset_internet_security(installer_dir, force)
    if uninstall:
        return uninstall_eset_internet_security(installer_dir, force)

    return 0


if __name__ == '__main__':
    exec_parser = _make_parser()
    args = exec_parser.parse_args()
    sys.exit(main(**vars(args)))