from pathlib import Path
from types import ModuleType
from typing import Literal

from . import _base
from .helpers import pycharm_installer


class PyCharm(_base.BaseInstaller):
    def __init__(self):
        super().__init__()
        self.name: str = Path(__file__).stem
        self.description: str = "PyCharm Installer"
        self.version: str = pycharm_installer.VERSION
        self.platforms: list = ["windows", "debian"]
        self.helper: ModuleType | None = pycharm_installer

    def install(
            self,
    ):
        return pycharm_installer.main()

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method installs the latest version of PyCharm unified:\n"
                "Windows: Downloads and installs PyCharm using the official installer from the Downloads section.\n"
                "Debian: Installs using the snap package manager.\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")