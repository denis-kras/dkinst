from pathlib import Path
from types import ModuleType
from typing import Literal
import os

from rich.console import Console

from . import _base
from .helpers.infra import system


console = Console()


class BashDB(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "bashdb Installer"
        self.version: str = "1.0.0"
        self.platforms: list = ["debian"]

        self.dependencies: list[str] = ["brew"]

    def install(
            self,
    ) -> int:
        return install_bashdb()

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method installs bashdb with help of brew: brew install bashdb\n"
                "If brew is not installed, it will be installed first.\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")


def _brew_eval_line():
    for p in ("/home/linuxbrew/.linuxbrew/bin/brew",
              "/opt/homebrew/bin/brew",
              "/usr/local/bin/brew"):
        if os.path.exists(p):
            return f'eval "$({p} shellenv)"'
    return 'eval "$(brew shellenv)"'


def install_bashdb():
    script_lines = [
        """

brew install bashdb
"""]

    system.execute_bash_script_string(script_lines)

    print("To use bashdb in the same session run:")
    print(_brew_eval_line())

    return 0