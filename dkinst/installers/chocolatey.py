from pathlib import Path
from typing import Literal
from types import ModuleType

from . import _base

from .helpers import chocolatey_installer


class Chocolatey(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "Chocolatey for Windows"
        self.version: str = chocolatey_installer.VERSION
        self.platforms: list = ["windows"]
        self.helper: ModuleType = chocolatey_installer

        self.admins: dict = {
            "windows": ["install", "upgrade", "uninstall"]
        }

    def install(
            self,
    ) -> int:
        return chocolatey_installer.main(install=True)

    def upgrade(
            self,
    ) -> int:
        return chocolatey_installer.main(upgrade=True)

    def uninstall(
            self
    ) -> int:
        return chocolatey_installer.main(uninstall=True)

    def is_installed(self) -> bool:
        return chocolatey_installer.is_choco_installed()

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method uses Chocolatey official installation script.\n"
            )
            print(method_help)
        elif method == "upgrade":
            print("Uses Chocolatey to upgrade itself.")
        elif method == "uninstall":
            method_help: str = (
                "This method uninstalls Chocolatey by removing its installation folder and environment variables.\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")
