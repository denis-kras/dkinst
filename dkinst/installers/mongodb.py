from pathlib import Path
from types import ModuleType
from typing import Literal

from rich.console import Console

from . import _base
from .helpers import mongodb_installer


console = Console()


class MongoDB(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "MongoDB + Compass Installer"
        self.version: str = mongodb_installer.VERSION
        self.platforms: list = ["windows", "debian"]
        self.helper: ModuleType = mongodb_installer

        self.admins: dict = {
            "debian": ["install"]
        }

    def install(
            self,
            force: bool = False
    ):
        mongodb_installer.main(
            latest=True,
            compass=True,
            force=force
        )

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method uses the [mongodb_installer.py] with the following arguments:\n"
                "  --latest               - install the latest stable version.\n"
                "  --compass              - install MongoDB Compass (GUI for MongoDB).\n"
                "\n"
                "  --force                - force install on ubuntu.\n"
                "  This one is used only if you provide it explicitly to the 'install' command. Example:\n"
                "    dkinst install mongodb force\n"
                "\n"
                "You can also use the 'manual' method to provide custom arguments to the helper script.\n"
                "Example:\n"
                "  dkinst manual mongodb help\n"
                "  dkinst manual mongodb --latest --force\n"
                "\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")
