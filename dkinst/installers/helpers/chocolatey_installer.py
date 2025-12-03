import sys
import os
import argparse
import shutil
import subprocess
import re
import requests

from .infra.printing import printc
from .infra import permissions


VERSION: str = "1.0.0"
"""Initial"""


API_URL = "https://community.chocolatey.org/api/v2/package/chocolatey"


def is_choco_installed() -> bool:
    """
    Check if choco command exists.
    """
    print("Checking if chocolatey is installed...")
    file_path: str = shutil.which("choco")
    if file_path:
        print(f"chocolatey is installed at: {file_path}")
        return True
    else:
        print("chocolatey is not installed.")
        return False


def is_choco_folder_exists() -> bool:
    """
    Check if Chocolatey installation folder exists.
    """
    choco_path = r"C:\ProgramData\chocolatey"
    exists = os.path.isdir(choco_path)
    if exists:
        print(f"Chocolatey installation folder exists at: {choco_path}")
    else:
        print("Chocolatey installation folder does not exist.")
    return exists


def get_choco_version_local() -> str | None:
    """Return the installed Chocolatey version as a string, or None if not installed."""
    if not is_choco_installed():
        return None

    result = subprocess.run(
        ["choco", "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        print("Failed to run `choco --version`:", file=sys.stderr)
        print(result.stderr.strip(), file=sys.stderr)
        return None

    return result.stdout.strip()


def get_choco_version_remote() -> str:
    """
    Query Chocolatey's community repository OData feed for the latest
    'chocolatey' package version and return it as a string.
    """

    # Don't auto-follow redirects so we can inspect the Location header
    resp = requests.get(API_URL, allow_redirects=False)
    resp.raise_for_status()

    location = resp.headers.get("Location", "")

    # If it didn't redirect, fall back to Content-Disposition filename
    if not location:
        cd = resp.headers.get("Content-Disposition", "")
        m = re.search(r'filename="?([^";]+)"?', cd)
        if not m:
            raise RuntimeError("Couldn't determine package filename from response")
        location = m.group(1)

    # Expect something like .../chocolatey.2.5.1.nupkg
    m = re.search(r"chocolatey\.([\w\.-]+)\.nupkg", location)
    if not m:
        raise RuntimeError(f"Couldn't parse version from: {location}")

    return m.group(1)


def install_choco() -> int:
    """
    Install chocolatey using the official installation script.
    """

    printc(f"Installing chocolatey by official script...", color="blue")
    # Official one-line install command from chocolatey.org
    install_cmd = (
        "Set-ExecutionPolicy Bypass -Scope Process -Force; "
        "[System.Net.ServicePointManager]::SecurityProtocol = "
        "[System.Net.ServicePointManager]::SecurityProtocol -bor 3072; "
        "iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))"
    )

    # Markers we care about (lowercased)
    reboot_markers = [
        "but a reboot is required",
        "a reboot is required before using chocolatey cli",
        "you need to restart this machine prior to using choco",
    ]

    needs_reboot = False

    # Start process and stream output
    proc = subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-InputFormat", "None",
            "-ExecutionPolicy", "Bypass",
            "-Command", install_cmd,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,  # line-buffered
    )

    # Read output line by line, print immediately, and check for markers
    if proc.stdout is not None:
        for line in proc.stdout:
            print(line, end="")  # stream to console as-is
            l = line.lower()
            if any(marker in l for marker in reboot_markers):
                needs_reboot = True

    proc.wait()

    if proc.returncode != 0:
        printc(
            f"Chocolatey installer failed with exit code {proc.returncode}",
            color="red",
        )
        return proc.returncode

    if needs_reboot:
        printc(
            "Chocolatey installation completed, but "
            "a reboot is required before you can use choco.\n"
            "Please restart this machine."
            "If it was part of dependency installation, run the installer again after reboot.",
            color="yellow",
        )
        # return a special reboot-required code
        return 3010

    printc(
        "Chocolatey installation script finished. "
        "Open a new shell and run `choco --version` to confirm.",
        color="green",
    )
    return 0


def upgrade_choco() -> int:
    """Run 'choco upgrade chocolatey -y' to upgrade Chocolatey in-place."""

    printc("Upgrading Chocolatey with `choco upgrade chocolatey -y`...", color='blue')
    completed = subprocess.run(
        ["choco", "upgrade", "chocolatey", "-y", "--accept-license"],
        text=True,
    )
    if completed.returncode != 0:
        print(f"Upgrade failed with exit code {completed.returncode}", file=sys.stderr)
        return completed.returncode
    printc("Chocolatey upgrade command completed.", color='green')
    return 0


def compare_local_and_remote_versions() -> int:
    """
    Compare the local and remote Chocolatey versions and print the result.
    Return 0 if up to date, 1 if an upgrade is available, or 2 on error.
    """
    local_version = get_choco_version_local()
    if local_version is None:
        printc("Chocolatey is not installed locally.", color='red')
        return 2

    try:
        remote_version = get_choco_version_remote()
    except RuntimeError as e:
        printc(str(e), color='red')
        return 2

    printc(f"Local Chocolatey version: {local_version}", color='blue')
    printc(f"Latest Chocolatey version: {remote_version}", color='blue')

    if local_version == remote_version:
        printc("Chocolatey is up to date.", color='green')
        return 0
    else:
        printc("A newer version of Chocolatey is available.", color='yellow')
        return 1


def _make_parser():
    parser = argparse.ArgumentParser(description="Install Chocolatey.")
    parser.add_argument(
        '-i', '--install',
        action='store_true',
        help=f"Install the latest version of Chocolatey."
    )
    parser.add_argument(
        '-u', '--upgrade',
        action='store_true',
        help=f"Update Chocolatey to the latest version."
    )

    parser.add_argument(
        '-vl', '--version-local',
        action='store_true',
        help="Get the installed Chocolatey version."
    )
    parser.add_argument(
        '-vr', '--version-remote',
        action='store_true',
        help="Get the latest Chocolatey version from the repository."
    )
    parser.add_argument(
        '-vc', '--version-compare',
        action='store_true',
        help="Compare local and remote Chocolatey versions."
    )

    parser.add_argument(
        '-f', '--force',
        action='store_true',
        help="Force installation, even if winget is already installed."
    )

    return parser


def main(
    install: bool = False,
    upgrade: bool = False,
    version_local: bool = False,
    version_remote: bool = False,
    version_compare: bool = False,
    force: bool = False,
) -> int:
    """
    The function will install Chocolatey on Windows.

    :param install: bool, If True, install Chocolatey.
    :param upgrade: bool, If True, upgrade Chocolatey to the latest version.
    :param version_local: bool, If True, print the installed Chocolatey version.
    :param version_remote: bool, If True, print the latest Chocolatey version from the
        repository.
    :param version_compare: bool, If True, compare local and remote Chocolatey versions.
    :param force: bool, If True, force installation even if Chocolatey is already installed.
    :return: int, Return code of the installation process. 0 if successful, non-zero otherwise.
    """

    if (install + upgrade + version_local + version_remote + version_compare) == 0:
        printc("At least one argument must be set to True: install, upgrade, version_local, version_remote, version_compare.", color="red")
        return 1
    if (install + upgrade + version_local + version_remote + version_compare) > 1:
        printc("Only one of the arguments can be set to True: install, upgrade, version_local, version_remote, version_compare.", color="red")
        return 1

    if version_local:
        local_version = get_choco_version_local()
        if local_version:
            printc(f"Installed Chocolatey version: {local_version}", color="blue")
        else:
            printc("Chocolatey is not installed.", color="red")
        return 0
    if version_remote:
        try:
            remote_version = get_choco_version_remote()
            printc(f"Latest Chocolatey version: {remote_version}", color="blue")
            return 0
        except RuntimeError as e:
            printc(str(e), color='red')
            return 1
    if version_compare:
        rc = compare_local_and_remote_versions()
        return rc

    if install:
        if is_choco_installed() and not force:
            printc("Chocolatey is already installed. Use --force to reinstall.", color="yellow")
            return 0
        if is_choco_folder_exists():
            printc("Chocolatey installation folder already exists, but command 'choco' is not registered. The official installation script will not run. Try removing the folder and installing again.", color="red")
            return 1

        rc: int = install_choco()
        if rc != 0:
            return rc
        return 0

    if upgrade:
        if not permissions.is_admin():
            printc("Administrator privileges are required to upgrade Chocolatey.", color='red')
            return 1

        if not is_choco_installed():
            printc("Chocolatey is not installed. Cannot upgrade.", color="red")
            return 1

        compare_result = compare_local_and_remote_versions()
        if compare_result == 0:
            printc("Chocolatey is already up to date.", color="green")
            return 0
        elif compare_result == 1:
            printc("Updating Chocolatey to the latest version...", color="blue")
        elif compare_result == 2:
            return 1  # Error occurred during version comparison

        rc: int = upgrade_choco()
        if rc != 0:
            return rc

    return 0


if __name__ == '__main__':
    ready_parser = _make_parser()
    args = ready_parser.parse_args()
    sys.exit(main(**vars(args)))