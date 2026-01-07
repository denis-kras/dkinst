from typing import Literal
from types import ModuleType

from rich.console import Console

from atomicshop import web

from . import _base
from .helpers import npcap_installer


console = Console()


DIST_URL = "https://npcap.com/dist/"
USER_AGENT = web.USER_AGENTS['Chrome 142.0.0 Windows 10/11 x64']

WINDOW_TITLE: str = "Npcap"


class Npcap(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "Npcap Installer"
        self.version: str = npcap_installer.VERSION
        # Initial.
        self.helper: ModuleType = npcap_installer
        self.platforms: list = ["windows"]
        self.admins: dict = {"windows": ["install"]}

    def install(
            self,
    ) -> int:
        return npcap_installer.main()

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method Downloads the the latest version of Npcap from the official Npcap website and runs the installer GUI.\n"
                "The public installer doesn't support silent installation (only the OEM version does), so the installer GUI will be displayed.\n"
                "\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")
