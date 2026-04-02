"""Self-update logic for dkinst."""
import os
import shutil
import stat
import sys
import tempfile

from rich.console import Console

from . import __version__
from .installers.helpers.infra import system
from .installers.helpers.infra import pips

console = Console()


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _parse_version(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def _get_asset_pattern() -> str:
    platform = system.get_platform()
    if platform == "windows":
        return "dkinst-*-windows.zip"
    return "dkinst-*-ubuntu.zip"


def _update_frozen_executable(github_wrapper) -> int:
    asset_pattern = _get_asset_pattern()
    tmp_dir = tempfile.mkdtemp(prefix="dkinst_update_")

    try:
        console.print("Downloading latest release...", style="cyan")
        github_wrapper.download_and_extract_latest_release(
            target_directory=tmp_dir,
            asset_pattern=asset_pattern,
        )

        current_exe = sys.executable
        platform = system.get_platform()

        if platform == "windows":
            new_exe_name = "dkinst.exe"
        else:
            new_exe_name = "dkinst"

        new_exe = os.path.join(tmp_dir, new_exe_name)
        if not os.path.isfile(new_exe):
            console.print(
                f"Expected file [{new_exe_name}] not found in downloaded release.",
                style="red", markup=False,
            )
            return 1

        if platform == "windows":
            old_path = current_exe + ".old"
            try:
                os.rename(current_exe, old_path)
            except OSError as exc:
                console.print(
                    f"Failed to rename current executable: {exc}",
                    style="red", markup=False,
                )
                return 1

            shutil.copy2(new_exe, current_exe)

            try:
                os.remove(old_path)
            except OSError:
                pass
        else:
            shutil.copy2(new_exe, current_exe)
            st = os.stat(current_exe)
            os.chmod(current_exe, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

        console.print("Executable updated successfully.", style="green")
        return 0

    except Exception as exc:
        console.print(f"Update failed: {exc}", style="red", markup=False)
        return 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _update_pip_package() -> int:
    console.print("Upgrading dkinst via pip...", style="cyan")
    return pips.pip_install("dkinst")


def _get_latest_pypi_version() -> str | None:
    import json
    import urllib.request
    import urllib.error

    url = "https://pypi.org/pypi/dkinst/json"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        return data["info"]["version"]
    except Exception as exc:
        console.print(f"Failed to check PyPI for updates: {exc}", style="red", markup=False)
        return None


def cmd_update_version(force: bool = False) -> int:
    if _is_frozen():
        from dkwebmod.githubw import GitHubWrapper

        gw = GitHubWrapper(user_name="denis-kras", repo_name="dkinst")
        try:
            latest_version_str = gw.get_latest_release_version()
        except Exception as exc:
            console.print(
                f"Failed to check for updates: {exc}",
                style="red", markup=False,
            )
            return 1
    else:
        latest_version_str = _get_latest_pypi_version()
        if latest_version_str is None:
            return 1

    current = _parse_version(__version__)
    latest = _parse_version(latest_version_str)

    console.print(f"Current version: {__version__}", markup=False)
    console.print(f"Latest version:  {latest_version_str}", markup=False)

    if latest <= current:
        console.print("Already up to date.", style="green")
        return 0

    console.print(
        f"New version available: {latest_version_str}",
        style="yellow", markup=False,
    )

    if not force:
        answer = console.input("Do you want to update? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            console.print("Update cancelled.")
            return 0

    if _is_frozen():
        return _update_frozen_executable(gw)
    else:
        return _update_pip_package()
