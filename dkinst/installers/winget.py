from pathlib import Path
from types import ModuleType
from typing import Literal

from rich.console import Console

from . import _base
from . helpers import winget_installer

console = Console()


class PyCharm(_base.BaseInstaller):
    def __init__(self):
        super().__init__()
        self.name: str = Path(__file__).stem
        self.description: str = "Winget Installer"
        self.version: str = winget_installer.VERSION
        self.platforms: list = ["windows"]
        self.helper: ModuleType = winget_installer

    def install(
            self,
            force: bool = False
    ):
        rc: int = winget_installer.main(install_ps_module=True, force=force)
        if rc != 0:
            return rc

        winget_installer.ensure_winget_available_in_this_process()

        return 0

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method installs Nuget powershell module, WinGet powershell module from NuGet repo, and then the latest version of Winget for all users'.\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")
