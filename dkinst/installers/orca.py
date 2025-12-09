from pathlib import Path
from typing import Literal

from rich.console import Console

from . import _base
from .helpers.infra import system, chocos


console = Console()


CHOCO_PACKAGE_NAME: str = "orca"


class Orca(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "MS Orca MSI Editor Installer"
        self.version: str = "1.0.0"
        # Initial.
        self.platforms: list = ["windows"]
        self.dependencies: list = ["chocolatey"]

    def install(
            self,
    ):
        return chocos.install_package(CHOCO_PACKAGE_NAME)

    def upgrade(
            self,
    ):
        return chocos.upgrade_package(CHOCO_PACKAGE_NAME)

    def uninstall(
            self
    ):
        return chocos.uninstall_package(CHOCO_PACKAGE_NAME)

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
