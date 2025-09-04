from pathlib import Path
from types import ModuleType
from typing import Literal
import subprocess
import sys

from rich.console import Console

from . import _base


console = Console()


WHEEL = (
    "https://github.com/fireeye/pywintrace/releases/download/v0.3.0/pywintrace-0.3.0-py3-none-any.whl"
)


class PyWintrace(_base.BaseInstaller):
    def __init__(self):
        super().__init__()
        self.name: str = Path(__file__).stem
        self.description: str = "PyWintrace Git Wheel Installer"
        self.version: str = "1.0.0"
        self.platforms: list = ["windows"]
        self.helper: ModuleType | None = None

    def install(
            self,
            force: bool = False
    ):
        subprocess.check_call([sys.executable, "-m", "pip", "install", WHEEL])

    def _show_help(
            self,
            method: Literal["install", "uninstall", "update"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method uses pip and PyWintrace latest wheel on GitHub (because there is a lower version on PyPi:\n"
                "  pip install https://github.com/fireeye/pywintrace/releases/download/v0.3.0/pywintrace-0.3.0-py3-none-any.whl\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")
