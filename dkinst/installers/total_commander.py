from pathlib import Path
from typing import Literal

from . import _base
from .helpers.infra import winget_fallback_choco


WINGET_PACKAGE_ID: str = "Ghisler.TotalCommander"
CHOCO_PACKAGE: str = "totalcommander"


class TotalCommander(_base.BaseInstaller):
    def __init__(self):
        super().__init__()
        self.name: str = Path(__file__).stem
        self.description: str = "TotalCommander for Windows"
        self.version: str = "1.0.2"
        # Using winget as main and choco as fallback.
        self.platforms: list = ["windows"]

        self.dependencies: list[str] = ['winget']

    def install(
            self,
            force: bool = False
    ):
        return winget_fallback_choco.method_package(
            method="install",
            winget_package_id=WINGET_PACKAGE_ID,
            choco_package_name=CHOCO_PACKAGE,
            force=force
        )

    def upgrade(
            self,
            force: bool = False
    ):
        return winget_fallback_choco.method_package(
            method="upgrade",
            winget_package_id=WINGET_PACKAGE_ID,
            choco_package_name=CHOCO_PACKAGE,
            force=force
        )

    def uninstall(
            self,
            force: bool = False
    ):
        return winget_fallback_choco.method_package(
            method="upgrade",
            winget_package_id=WINGET_PACKAGE_ID,
            choco_package_name=CHOCO_PACKAGE,
            force=force
        )

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method uses Winget or falls back to Chocolatey to install TotalCommander.\n"
            )
            print(method_help)
        elif method == "upgrade":
            print("Uses Winget or falls back to Chocolatey to upgrade TotalCommander.")
        elif method == "uninstall":
            print("Uses Winget or falls back to Chocolatey to uninstall TotalCommander.")
        else:
            raise ValueError(f"Unknown method '{method}'.")
