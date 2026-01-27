from types import ModuleType
from typing import Literal

from rich.console import Console

from . import _base
from .helpers import clamav_installer


console = Console()


class ClamAV(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "ClamAV Installer"
        self.version: str = clamav_installer.VERSION
        self.platforms: list = ["debian"]
        self.helper: ModuleType = clamav_installer

        self.admins: dict = {"debian": ["install", "uninstall"]}

    def install(
            self,
    ) -> int:
        return clamav_installer.main(install=True, enable_all=True)

    def uninstall(self) -> int:
        return clamav_installer.main(uninstall=True, disable_all=True)

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method uses the [clamav_installer.py] with the following arguments:\n"
                "  --install --enable-all\n"
                "\n"
                "You can also use the 'manual' method to provide custom arguments to the helper script.\n"
                "Example:\n"
                "  dkinst manual clamav help\n"
                "\n"
            )
            print(method_help)
        elif method == "uninstall":
            method_help: str = (
                "This method uses the [clamav_installer.py] with the following arguments:\n"
                "  --uninstall --disable-all\n"
                "\n"
                "You can also use the 'manual' method to provide custom arguments to the helper script.\n"
                "Example:\n"
                "  dkinst manual clamav help\n"
                "\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")
