import sys
import os
from typing import Literal
import subprocess
import shlex

from rich.console import Console

from atomicshop.wrappers import githubw

from . import _base
from .helpers.infra import commands


console = Console()


class PythonUpgrader(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "Python Micro Version Updater"
        self.version: str = "1.0.1"
        # Updated admin permissions.
        self.platforms: list = ["windows"]

        self.admins: dict = {"windows": ["upgrade"]}

    def upgrade(
            self,
    ) -> int:
        return upgrade_function(self.dir_path)

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "upgrade":
            method_help: str = (
                "This method upgrades the current minor version to the latest micro.\n"
                "Example:\n"
                "If your current Python version is 3.14.7, it will upgrade to the latest 3.14.x version where installer is available.\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")


def upgrade_function(target_dir: str):
    print("Starting Python Micro Version Upgrade Process...")

    # Get the current python version.
    current_python_version = sys.version_info
    current_minor_version: str = f"{str(current_python_version.major)}.{current_python_version.minor}"

    print(f"Current Python Version: {current_minor_version}.{current_python_version.micro}")
    print("Downloading python installer script...")
    # Get the latest python installer from git.
    github_wrapper: githubw.GitHubWrapper = githubw.GitHubWrapper(
        user_name="denis-kras",
        repo_name="dkinst",
    )
    cmd_file_path: str = github_wrapper.download_file("prereqs/install_python_as_admin_win.cmd", target_dir)
    if not cmd_file_path:
        console.print("[red]Failed to download the Python installer script.[/red]")
        return 1

    if not os.path.isfile(cmd_file_path):
        console.print(f"[red]The downloaded Python installer script does not exist at path: {cmd_file_path}[/red]")
        return 1

    # Get the latest python version of the current minor version.
    command: list = ["cmd.exe", "/c", cmd_file_path, current_minor_version, '-l']
    print(f"Executing: {shlex.join(command)}")
    result = subprocess.run(command, capture_output=True)
    if result.returncode != 0:
        os.remove(cmd_file_path)
        console.print(f"[red]Failed to run the Python installer script. Error:\n"
                      f"{result.stderr.decode()}[/red]")
        return 1
    else:
        latest_version: str = result.stdout.decode().strip()
        console.print(f"Latest Python Micro Version with Installer: {latest_version}")

        latest_major, latest_minor, latest_micro = map(int, latest_version.split('.'))
        if latest_micro > current_python_version.micro:
            console.print(f"[yellow]A new Python version is available: {latest_version} "
                          f"(current: {current_minor_version}.{current_python_version.micro})[/yellow]")
            command: list = ["cmd.exe", "/c", cmd_file_path, latest_version]
            print(f"Executing: {shlex.join(command)}")
            console.print(f"Running the installer to upgrade Python to version {latest_version}...")

            rc, message = commands.run_package_manager_command(command, "Install")
            if rc != 0:
                console.print(f"[red]Failed to install.[/red]")
                console.print(f"[red]{message}[/red]")
                return rc
            else:
                console.print(f"[green]Python has been successfully upgraded to version {latest_version}.[/green]")
        else:
            console.print(f"[green]You already have the latest Python version: {latest_version}.[/green]")
    os.remove(cmd_file_path)
    return 0