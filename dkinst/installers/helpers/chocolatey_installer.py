import sys
import os
import argparse
import shutil
import subprocess
import re
import requests
from pathlib import Path

if os.name == "nt":
    import winreg

from .infra.printing import printc
from .infra import permissions, registrys


VERSION: str = "1.1.0"
"""Added uninstall and fixed install"""


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


def _locate_choco_exe() -> str | None:
    """
    Best-effort locate choco.exe after installation.

    Priority:
      1. %ChocolateyInstall%\\bin
      2. %ProgramData%\\chocolatey\\bin
      3. Last resort: whatever shutil.which("choco") sees
    """
    candidates: list[str] = []

    choco_install = os.environ.get("ChocolateyInstall")
    if choco_install:
        candidates.append(choco_install)

    program_data = os.environ.get("ProgramData")
    if program_data:
        candidates.append(os.path.join(program_data, "chocolatey"))

    # Deduplicate and check bin\choco.exe
    seen: set[str] = set()
    for root in candidates:
        if not root:
            continue
        root_norm = os.path.normpath(root)
        key = root_norm.lower()
        if key in seen:
            continue
        seen.add(key)
        exe = os.path.join(root_norm, "bin", "choco.exe")
        if os.path.isfile(exe):
            return exe

    # Last resort: current process PATH (may already be correct if PATH was set before)
    exe = shutil.which("choco")
    return exe


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

    choco_dir: str = str(Path(_locate_choco_exe()).parent)
    os.environ["PATH"] = choco_dir + os.pathsep + os.environ.get("PATH", "")

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


def uninstall_choco() -> int:
    """
    Uninstall Chocolatey by removing its bin folder and Chocolatey-related
    environment variables/PATH entries.

    This does NOT uninstall or remove applications that were installed via
    Chocolatey; it only removes the CLI and its environment wiring.
    """
    # Safety: only meaningful on Windows with winreg available
    if os.name != "nt" or winreg is None:
        printc("Chocolatey uninstall is only supported on Windows.", color="red")
        return 1

    # Environment variable names commonly used by Chocolatey
    CHOCOLATEY_ENV_VARS = [
        "ChocolateyInstall",
        "ChocolateyToolsLocation",
        "ChocolateyBinRoot",
        "ChocolateyLastPathUpdate",
    ]

    def _clean_path_value(path_value: str | None) -> str | None:
        """
        Remove any PATH segments that reference 'chocolatey' (case-insensitive).
        """
        if not path_value:
            return path_value

        parts = [p for p in path_value.split(";") if p]
        cleaned_parts = [
            p for p in parts
            if "chocolatey" not in p.lower()
        ]
        return ";".join(cleaned_parts)

    def _clean_registry_env(root, subkey: str, scope_name: str) -> bool:
        """
        Remove Chocolatey env vars and PATH entries from a given registry key.

        Returns:
            had_error (bool): True if any permission/registry write error occurred.
        """
        access = winreg.KEY_READ | winreg.KEY_WRITE
        if hasattr(winreg, "KEY_WOW64_64KEY"):
            access |= winreg.KEY_WOW64_64KEY

        try:
            key = winreg.OpenKey(root, subkey, 0, access)
        except FileNotFoundError:
            # No environment key in this hive; nothing to do.
            print(f"[INFO] Registry environment key not found for {scope_name} scope.")
            return False
        except PermissionError as exc:
            printc(
                f"Insufficient permissions to modify {scope_name} environment: {exc}",
                color="yellow",
            )
            return True

        had_error = False

        with key:
            # Remove Chocolatey-specific environment variables
            for name in CHOCOLATEY_ENV_VARS:
                try:
                    winreg.DeleteValue(key, name)
                    printc(
                        f"Removed {scope_name} environment variable: {name}",
                        color="green",
                    )
                except FileNotFoundError:
                    # Not present; ignore
                    pass
                except PermissionError as exc:
                    had_error = True
                    printc(
                        f"Could not remove {scope_name} environment variable {name}: {exc}",
                        color="yellow",
                    )

            # Clean PATH for this scope
            try:
                current_path, value_type = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current_path, value_type = None, None

            if current_path is not None:
                new_path = _clean_path_value(current_path)
                if new_path != current_path:
                    try:
                        winreg.SetValueEx(key, "Path", 0, value_type, new_path)
                        printc(
                            f"Cleaned Chocolatey entries from {scope_name} PATH.",
                            color="green",
                        )
                    except PermissionError as exc:
                        had_error = True
                        printc(
                            f"Could not update {scope_name} PATH: {exc}",
                            color="yellow",
                        )

        return had_error

    printc(
        "Uninstalling Chocolatey: removing bin folder and environment variables "
        "(installed packages will remain).",
        color="blue",
    )

    # 1. Remove the bin folder under %ChocolateyInstall%, if we can resolve it
    choco_root = os.environ.get("ChocolateyInstall", "").strip().strip('"')
    if choco_root and os.path.isdir(choco_root):
        bin_dir = os.path.join(choco_root, "bin")
        # Remove the whole chocolatey directory.
        choco_dir: str = os.path.dirname(bin_dir)
        if os.path.isdir(choco_dir):
            try:
                shutil.rmtree(choco_dir)
                printc(f"Removed Chocolatey bin directory: {choco_dir}", color="green")
            except Exception as exc:
                # Non-fatal; we still proceed with env cleanup
                printc(
                    f"Failed to remove Chocolatey bin directory '{choco_dir}': {exc}",
                    color="yellow",
                )
        else:
            printc(
                f"Chocolatey bin directory does not exist: {choco_dir}",
                color="yellow",
            )
    else:
        printc(
            "Environment variable 'ChocolateyInstall' is not set or does not point to "
            "an existing directory. Skipping bin directory removal.",
            color="yellow",
        )

    # Trying to remove common installation folder if exists
    common_choco_path = r"C:\ProgramData\chocolatey"
    if os.path.isdir(common_choco_path):
        try:
            shutil.rmtree(common_choco_path)
            printc(f"Removed common Chocolatey installation directory: {common_choco_path}", color="green")
        except Exception as exc:
            # Non-fatal; we still proceed with env cleanup
            printc(
                f"Failed to remove common Chocolatey installation directory '{common_choco_path}': {exc}",
                color="yellow",
            )
    else:
        printc(
            f"Common Chocolatey installation directory does not exist: {common_choco_path}",
            color="yellow",
        )

    # 2. Clean system and user environment in the registry
    had_errors = False

    # System-wide env (requires admin to fully succeed)
    had_errors = _clean_registry_env(
        winreg.HKEY_LOCAL_MACHINE,
        r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        "system",
    ) or had_errors

    # User env (no admin required)
    had_errors = _clean_registry_env(
        winreg.HKEY_CURRENT_USER,
        r"Environment",
        "user",
    ) or had_errors

    # 3. Clean current process environment so the running shell reflects changes immediately
    for name in CHOCOLATEY_ENV_VARS:
        if name in os.environ:
            os.environ.pop(name, None)
            printc(f"Removed process environment variable: {name}", color="green")

    process_path = os.environ.get("PATH", "")
    new_process_path = _clean_path_value(process_path)
    if new_process_path is not None and new_process_path != process_path:
        os.environ["PATH"] = new_process_path
        printc(
            "Cleaned Chocolatey entries from current process PATH.",
            color="green",
        )

    # 4. Broadcast environment change using your existing helper
    try:
        if hasattr(registrys, "_broadcast_env_change"):
            # Use the same pattern as inside registrys.py
            registrys._broadcast_env_change(registrys.ctypes)  # type: ignore[attr-defined]
            printc("Broadcasted environment change.", color="green")
        else:
            printc(
                "registrys._broadcast_env_change not available; "
                "environment changes will apply to new logon sessions.",
                color="yellow",
            )
    except Exception as exc:
        had_errors = True
        printc(
            f"Failed to broadcast environment change: {exc}",
            color="yellow",
        )

    if had_errors:
        printc(
            "Chocolatey uninstall completed with some warnings. "
            "You may want to double-check PATH and environment variables manually.",
            color="yellow",
        )
        # Treat as overall success for CLI purposes; warnings are already printed.
        return 0

    printc(
        "Chocolatey uninstall completed successfully. "
        "Open a new shell and run `choco` to confirm it is no longer available.",
        color="green",
    )
    return 0


def _make_parser():
    parser = argparse.ArgumentParser(description="Install Chocolatey.")
    parser.add_argument(
        '-i', '--install',
        action='store_true',
        help=f"Install the latest version of Chocolatey."
    )
    parser.add_argument(
        '-un', '--uninstall',
        action='store_true',
        help=f"Uninstall Chocolatey."
    )
    parser.add_argument(
        '-up', '--upgrade',
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
        uninstall: bool = False,
        upgrade: bool = False,
        version_local: bool = False,
        version_remote: bool = False,
        version_compare: bool = False,
        force: bool = False,
) -> int:
    """
    The function will install Chocolatey on Windows.

    :param install: bool, If True, install Chocolatey.
    :param uninstall: bool, If True, uninstall Chocolatey.
    :param upgrade: bool, If True, upgrade Chocolatey to the latest version.
    :param version_local: bool, If True, print the installed Chocolatey version.
    :param version_remote: bool, If True, print the latest Chocolatey version from the
        repository.
    :param version_compare: bool, If True, compare local and remote Chocolatey versions.
    :param force: bool, If True, force installation even if Chocolatey is already installed.
    :return: int, Return code of the installation process. 0 if successful, non-zero otherwise.
    """

    if (install + uninstall + upgrade + version_local + version_remote + version_compare) == 0:
        printc("At least one argument must be set to True: install, uninstall, upgrade, version_local, version_remote, version_compare.", color="red")
        return 1
    if (install + uninstall + upgrade + version_local + version_remote + version_compare) > 1:
        printc("Only one of the arguments can be set to True: install, uninstall, upgrade, version_local, version_remote, version_compare.", color="red")
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

    if uninstall:
        # No need to check if 'choco' command exists; we can uninstall even if it's broken.
        rc: int = uninstall_choco()
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