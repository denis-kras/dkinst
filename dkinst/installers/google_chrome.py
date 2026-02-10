from typing import Literal

from rich.console import Console

from . import _base
from .helpers.infra import system


console = Console()


class GoogleChrome(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "Google Chrome Installer"
        self.version: str = "1.0.0"
        self.platforms: list = ["debian"]
        self.admins: dict = {"debian": ["install"]}

    def install(
            self,
    ) -> int:
        return install_function()

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method installs Google Chrome deb file from its official URL.\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")


def install_function():
    script_lines = [
        """

wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && sudo apt install -y ./google-chrome-stable_current_amd64.deb
"""]

    system.execute_bash_script_string(script_lines)

    return 0