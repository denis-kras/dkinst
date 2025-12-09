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

from .infra import registrys, msis, win_open_windows
from .infra.printing import printc

from atomicshop import web


VERSION: str = "1.0.0"
RELEASE_COMMENT: str = "Initial"


# Official "latest" offline installer URLs for ESET Internet Security (home product) :contentReference[oaicite:2]{index=2}
ESET_DOWNLOAD_URL_64 = "https://download.eset.com/com/eset/apps/home/eis/windows/latest/eis_nt64.exe"
ESET_DOWNLOAD_URL_32 = "https://download.eset.com/com/eset/apps/home/eis/windows/latest/eis_nt32.exe"

_GUID_RE = re.compile(r"{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}}")


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
    open_windows = win_open_windows.get_open_windows()
    if force:
        if open_windows:
            printc("[!] --force specified. Closing all currently open windows before uninstall.", "yellow")
            win_open_windows.print_open_windows(open_windows)
            win_open_windows.close_windows(open_windows)
        else:
            print("[+] No windows to close in force mode.")
    else:
        # Just show them and tell the user they must close them
        win_open_windows.print_open_windows(open_windows)
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
    old_msedge_procs = win_open_windows.get_msedge_snapshot()
    old_msedge_windows = win_open_windows.get_msedge_window_handles()

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
    win_open_windows.kill_new_msedge_processes(old_msedge_procs, wait_seconds=5.0)
    win_open_windows.close_new_msedge_windows(old_msedge_windows, wait_seconds=5.0)

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