from pathlib import Path
from typing import Literal

from . import _base
from .helpers.infra import winget_fallback_choco


WINGET_PACKAGE_ID: str = "Notepad++.Notepad++"
CHOCO_PACKAGE: str = "notepadplusplus"


class NotepadPP(_base.BaseInstaller):
    def __init__(self):
        super().__init__()
        self.name: str = Path(__file__).stem
        self.description: str = "Notepad++ for Windows"
        self.version: str = "1.0.0"
        # initial.
        self.platforms: list = ["windows"]

        self.dependencies: list[str] = ['winget']

    def install(
            self,
    ):
        return winget_fallback_choco.method_package(
            method="install",
            winget_package_id=WINGET_PACKAGE_ID,
            choco_package_name=CHOCO_PACKAGE
        )

    def upgrade(
            self,
    ):
        return winget_fallback_choco.method_package(
            method="upgrade",
            winget_package_id=WINGET_PACKAGE_ID,
            choco_package_name=CHOCO_PACKAGE
        )

    def uninstall(
            self,
    ):
        return winget_fallback_choco.method_package(
            method="upgrade",
            winget_package_id=WINGET_PACKAGE_ID,
            choco_package_name=CHOCO_PACKAGE
        )

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method uses Winget or falls back to Chocolatey to install Notepad++.\n"
            )
            print(method_help)
        elif method == "upgrade":
            print("Uses Winget or falls back to Chocolatey to upgrade Notepad++.")
        elif method == "uninstall":
            print("Uses Winget or falls back to Chocolatey to uninstall Notepad++.")
        else:
            raise ValueError(f"Unknown method '{method}'.")
