from pathlib import Path
from types import ModuleType
from typing import Literal

from rich.console import Console

from . import _base
from .helpers.infra import system


console = Console()


class QTorrent(_base.BaseInstaller):
    def __init__(self):
        super().__init__()
        self.name: str = Path(__file__).stem
        self.description: str = "qTorrent Installer"
        self.version: str = "1.0.0"
        self.platforms: list = ["debian"]
        self.helper: ModuleType | None = None

    def install(
            self,
    ):
        return install_function()

    def _show_help(
            self,
            method: Literal["install", "uninstall", "update"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method installs qTorrent from apt repo.\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")


def install_function():
    script_lines = [
        """

sudo apt update
sudo apt install -y qbittorrent
"""]

    system.execute_bash_script_string(script_lines)

    return 0