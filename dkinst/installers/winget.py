from pathlib import Path
from types import ModuleType
from typing import Literal

from rich.console import Console

from . import _base
from . helpers import winget_installer

console = Console()


class PyCharm(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "Winget Installer"
        self.version: str = winget_installer.VERSION
        self.platforms: list = ["windows"]
        self.helper: ModuleType = winget_installer

    def install(
            self,
            force: bool = False
    ) -> int:
        rc: int = winget_installer.main(install_ps_module=True, force=force)
        if rc != 0:
            console.print('=============================', style='red')
            console.print("Try other installation methods with: dkinst manual winget", style='yellow')
            return rc

        winget_installer.ensure_winget_available_in_this_process()

        # Check if winget is available now
        if not winget_installer.is_winget_installed():
            console.print("Winget is not installed, could be it is not supported by your version of Windows.", style='red')
            return 1
        else:
            console.print("Winget installer installed successfully", style='green')

        return 0

    def upgrade(self) -> int:
        print("Currently, Windows should handle Winget upgrades, but you can run the install command again to ensure you have the latest version.")
        return 0

    def is_installed(self) -> bool:
        return winget_installer.is_winget_installed()

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method installs Nuget powershell module, WinGet powershell module from NuGet repo, and then the latest version of Winget for all users'.\n"
            )
            print(method_help)
        if method == "upgrade":
            method_help: str = (
                "Currently, Windows should handle Winget upgrades, but you can run the install command again to ensure you have the latest version.\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")
