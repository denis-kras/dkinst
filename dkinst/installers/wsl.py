from pathlib import Path
from types import ModuleType
from typing import Literal

from . import _base
from . helpers import wsl_manager


class WSL(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "Windows Subsystem for Linux (WSL) manager."
        self.version: str = wsl_manager.VERSION
        self.platforms: list = ["windows"]
        self.helper: ModuleType = wsl_manager

    def install(
            self,
    ) -> int:
        return wsl_manager.main(
            install=True
        )

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method uses the [wsl_manager.py] with the following arguments:\n"
                "  --install                        - Install using the default installation method.\n"
                "\n"
                "You can also use the 'manual' method to provide custom arguments to the helper script.\n"
                "\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")