from pathlib import Path
from typing import Literal
from types import ModuleType

from rich.console import Console

from . import _base
from .helpers import eset_installer


console = Console()


class QTorrent(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "ESET Internet Security Installer"
        self.version: str = eset_installer.VERSION
        # Initial.
        self.platforms: list = ["windows"]
        self.helper: ModuleType = eset_installer
        self.admins: dict = {"windows": ["install", "uninstall"]}

    def install(
            self,
            force: bool = False
    ):
        return eset_installer.main(install=True, installer_dir=self.dir_path, force=force)

    def uninstall(
            self,
            force: bool = False
    ):
        return eset_installer.main(uninstall=True, installer_dir=self.dir_path, force=force)

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "Downloads the latest installer of ESET Internet Security and silently installs it.\n"
            )
            print(method_help)
        elif method == "uninstall":
            method_help: str = (
                "Uninstalls ESET Internet Security using official uninstall method.\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")
