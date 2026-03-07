from types import ModuleType
from typing import Literal

from . import _base
from .helpers import python_manager


class PythonUpgrader(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "Python Micro Version Updater"
        self.version: str = python_manager.VERSION
        self.platforms: list = ["windows"]
        self.helper: ModuleType = python_manager

        self.admins: dict = {"windows": ["install", "upgrade"]}

    def install(
            self,
            version: str = "3.13",
    ) -> int:
        return python_manager.install(version)

    def upgrade(
            self,
    ) -> int:
        return python_manager.upgrade()

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method installs a specific Python minor version.\n"
                "The latest micro version with an available installer will be resolved automatically.\n"
                "Example:\n"
                "  dkinst install python 3.13\n"
                "\n"
                "You can also use the 'manual' method to provide custom arguments to the helper script.\n"
                "Example:\n"
                "  dkinst manual python help\n"
                "  dkinst manual python -i 3.13\n"
            )
            print(method_help)
        elif method == "upgrade":
            method_help: str = (
                "This method upgrades the current minor version to the latest micro.\n"
                "Example:\n"
                "If your current Python version is 3.14.7, it will upgrade to the latest 3.14.x version where installer is available.\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")