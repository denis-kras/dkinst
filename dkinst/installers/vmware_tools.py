from pathlib import Path
from types import ModuleType
from typing import Literal

from rich.console import Console

from . import _base
from .helpers.infra import system

from atomicshop.wrappers import ubuntu_terminal


console = Console()


class VMWareTools(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "VMWare Tools Installer"
        self.version: str = "1.0.0"
        self.platforms: list = ["debian"]

    def install(
            self,
    ):
        return install_function()

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method installs open-vm-tools and open-vm-tools-desktop from apt repo.\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")


def install_function():
    script_lines = [
        """

sudo apt update
sudo apt install -y open-vm-tools open-vm-tools-desktop
"""]

    system.execute_bash_script_string(script_lines)

    result_code: int = ubuntu_terminal.start_enable_service_check_availability(
        "open-vm-tools",
        enable_service_bool=False, start_service_bool=False, check_service_running=True)
    if result_code != 0:
        return result_code

    return 0