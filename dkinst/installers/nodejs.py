from pathlib import Path
from types import ModuleType
from typing import Literal

from rich.console import Console

from . import _base
from .helpers import nodejs_installer


console = Console()


class NodeJS(_base.BaseInstaller):
    def __init__(self):
        super().__init__()
        self.name: str = Path(__file__).stem
        self.description: str = "NodeJS Installer"
        self.version: str = nodejs_installer.VERSION
        self.platforms: list = ["windows", "debian"]
        self.helper: ModuleType | None = nodejs_installer

    def install(
            self,
            force: bool = False
    ):
        nodejs_installer.main(
            latest=True,
            force=force
        )

    def _show_help(
            self,
            method: Literal["install", "uninstall", "update"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method uses the [nodejs_installer.py] with the following arguments:\n"
                "  --latest               - install the latest stable version.\n"
                "\n"
                "  --force                - force install on ubuntu.\n"
                "  This one is used only if you provide it explicitly to the 'install' command. Example:\n"
                "    dkinst install nodejs force\n"
                "\n"
                "You can also use the 'manual' method to provide custom arguments to the helper script.\n"
                "Example:\n"
                "  dkinst manual nodejs help\n"
                "  dkinst manual nodejs --lts --force\n"
                "\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")
