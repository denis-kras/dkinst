from pathlib import Path
from typing import Literal

from . import _base
from .helpers.infra import wingets
from .helpers.infra.printing import printc


WINGET_PACKAGE_ID: str = "Ghisler.TotalCommander"


class FFMPEG(_base.BaseInstaller):
    def __init__(self):
        super().__init__()
        self.name: str = Path(__file__).stem
        self.description: str = "TotalCommander for Windows"
        self.version: str = "1.0.0"
        self.platforms: list = ["windows"]

        self.dependencies: list[str] = ['winget']

    def install(
            self,
    ):
        return install_function()

    def update(
            self,
    ):
        return update_function()

    def uninstall(
            self,
    ):
        return uninstall_function()

    def _show_help(
            self,
            method: Literal["install", "uninstall", "update"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method uses WinGet to install Ghisler.TotalCommander.\n"
            )
            print(method_help)
        elif method == "update":
            print("Uses WinGet to update Ghisler.TotalCommander.")
        elif method == "uninstall":
            print("Uses WinGet to uninstall Ghisler.TotalCommander.")
        else:
            raise ValueError(f"Unknown method '{method}'.")


def install_function() -> int:
    rc: int = wingets.install_package(WINGET_PACKAGE_ID)
    if rc != 0:
        printc("Failed to install TotalCommander.", color="red")
        return rc

    return 0


def update_function() -> int:
    rc: int = wingets.upgrade_package(WINGET_PACKAGE_ID)
    if rc != 0:
        printc("Failed to update TotalCommander.", color="red")
        return rc

    return 0


def uninstall_function() -> int:
    rc: int = wingets.uninstall_package(WINGET_PACKAGE_ID)
    if rc != 0:
        printc("Failed to uninstall TotalCommander.", color="red")
        return rc

    return 0