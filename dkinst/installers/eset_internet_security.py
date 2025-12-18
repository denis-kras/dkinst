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
            force: bool = False,
            language: str = "english"
    ) -> int:
        return eset_installer.main(install=True, installer_dir=self.dir_path, language=language, force=force)

    def uninstall(
            self,
            force: bool = False
    ) -> int:
        return eset_installer.main(uninstall=True, installer_dir=self.dir_path, force=force)

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "Downloads the latest installer of ESET Internet Security and silently installs it.\n"
                "Available options:\n"
                "  language <language>   Language for the GUI of the installed product. Default is 'english'.\n"
                "  force                 Force re-download the installer even if it already exists in the specified directory.\n"
                "\n"
                "Example:\n"
                "  dkinst i eset_internet_security language french force\n"
            )
            print(method_help)
        elif method == "uninstall":
            method_help: str = (
                "Uninstalls ESET Internet Security using official uninstall method.\n"
                "Available options:\n"
                "  force   Close any open windows before uninstalling.\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")
