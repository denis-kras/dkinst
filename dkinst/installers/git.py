from typing import Literal
import shutil
import subprocess
import os

from rich.console import Console

from . import _base
from .helpers.infra import chocos


console = Console()


CHOCO_PACKAGE_NAME: str = "git"
CHOCO_PACKAGE_DEPENDENCY_NAME: str = "git.install"


class Git(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "Git Installer"
        self.version: str = "1.0.0"
        # Initial.
        self.platforms: list = ["windows"]
        self.dependencies: list = ["chocolatey"]

        self.admins: dict = {
            "windows": ["install", "upgrade", "uninstall"]
        }

    def install(
            self,
    ) -> int:
        rc, message = chocos.install_package(CHOCO_PACKAGE_NAME)
        if rc != 0:
            return rc

        if not shutil.which("refreshenv"):
            console.print(f"[red]Cannot find 'refreshenv' command to refresh environment variables.[/red]")
            return 1

        # Refresh the cmd environment to recognize git command using cmd, or we will get FileNotFound if running from python directly.
        cp = subprocess.run(
            ["cmd", "/c", "refreshenv"],
            check=False,  # if wmic is not found an exception will be raised.
            text=True,
            capture_output=True
        )
        rc = cp.returncode
        if rc != 0:
            console.print(f"[red]Failed to refresh environment variables after Git installation.[/red]")
            console.print(f"[red]STDOUT: {cp.stdout}[/red]")
            console.print(f"[red]STDERR: {cp.stderr}[/red]")
            return rc
        else:
            print(cp.stdout)

        # Add git to python's PATH for the current session.
        candidates = [
            r"C:\ProgramData\chocolatey\bin",  # choco shims (often enough)
            r"C:\Program Files\Git\cmd",  # git.exe entrypoint
            r"C:\Program Files\Git\bin",
        ]

        for p in candidates:
            if os.path.isdir(p) and p not in os.environ["PATH"]:
                os.environ["PATH"] += os.pathsep + p

        if self.is_installed():
            console.print(f"[green]Git found in the current session.[/green]")
        else:
            console.print(f"[red]Git command doesn't exist in the current session after install.[/red]")
            rc = 1

        return rc

    def upgrade(
            self,
    ) -> int:
        rc, message = chocos.upgrade_package(CHOCO_PACKAGE_NAME)
        return rc

    def uninstall(
            self
    ) -> int:
        # Basically it doesn't matter if git uninstall returns error or not,
        # because git.install is the main package that holds the files.
        rc, message = chocos.uninstall_package(CHOCO_PACKAGE_NAME)
        if rc != 0:
            console.print(f"[yellow]Warning: Git uninstall returned non-zero exit code {rc}.[/yellow]")
            return rc

        rc, message = chocos.uninstall_package(CHOCO_PACKAGE_DEPENDENCY_NAME)
        return rc


    def is_installed(self) -> bool:
        return shutil.which("git") is not None

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                f"Windows: This method installs {self.name} from Chocolatey repo (choco has the latest version faster).\n"
            )
            print(method_help)
        elif method == "upgrade":
            method_help: str = (
                f"Windows: This method upgrades {self.name} from Chocolatey repo (choco has the latest version faster).\n"
            )
            print(method_help)
        elif method == "uninstall":
            method_help: str = (
                f"Windows: This method uninstalls {self.name} using Chocolatey.\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")
