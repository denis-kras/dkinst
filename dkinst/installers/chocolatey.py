from pathlib import Path
from typing import Literal
from types import ModuleType

from . import _base

from .helpers import chocolatey_installer


class Chocolatey(_base.BaseInstaller):
    def __init__(self):
        super().__init__()
        self.name: str = Path(__file__).stem
        self.description: str = "Chocolatey for Windows"
        self.version: str = chocolatey_installer.VERSION
        self.platforms: list = ["windows"]
        self.helper: ModuleType = chocolatey_installer

        self.admins: dict = {
            "windows": ["install", "upgrade"]
        }

    def install(
            self,
    ):
        return chocolatey_installer.main(install=True)

    def upgrade(
            self,
    ):
        return chocolatey_installer.main(upgrade=True)

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
        else:
            raise ValueError(f"Unknown method '{method}'.")
