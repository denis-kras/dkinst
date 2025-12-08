from pathlib import Path
from typing import Literal
from types import ModuleType

from rich.console import Console

from . import _base
from .helpers import rdp_gpu_manager


console = Console()


class QTorrent(_base.BaseInstaller):
    def __init__(self):
        super().__init__()
        self.name: str = Path(__file__).stem
        self.description: str = "Windows RDP GPU Setting Installer"
        self.version: str = rdp_gpu_manager.VERSION
        # Added windows.
        self.platforms: list = ["windows"]
        self.helper: ModuleType = rdp_gpu_manager

    def install(
            self,
    ):
        return install_function()

    def uninstall(
            self
    ):
        return uninstall_function()

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "Sets 3 RDP Policies to True, through the registry, to enable GPU acceleration over RDP:.\n"
                "1. Enable GPU for RDP sessions.\n"
                "2. Enable Hardware Encoding for RDP sessions.\n"
                "3. Enable AVC444 mode for RDP sessions.\n"
                "\n"
                "Restarts RDP service to apply changes immediately.\n"
            )
            print(method_help)
        elif method == "upgrade":
            method_help: str = (
                "Windows: This method upgrades qTorrent from Chocolatey repo (choco has the latest version faster).\n"
                "Debian: This method upgrades qTorrent from apt repo.\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")


def install_function() -> int:
    return rdp_gpu_manager.main(
        enable=True,
        gpu=True,
        hw_encode=True,
        avc444=True,
        restart_rdp_service=True
    )


def uninstall_function() -> int:
    return rdp_gpu_manager.main(
        default_state=True,
        gpu=True,
        hw_encode=True,
        avc444=True,
        restart_rdp_service=True
    )