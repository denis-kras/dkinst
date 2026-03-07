import os
import shutil
from typing import Literal

from rich.console import Console

from . import _base
from .helpers.infra import chocos
from .helpers.infra import shortcuts


console = Console()


CHOCO_PACKAGE_NAME: str = "SDIO"
SDIO_BAT_PATH: str = os.path.join(
    os.environ.get("ChocolateyInstall", r"C:\ProgramData\chocolatey"),
    "lib", "SDIO", "tools", "SDIO_auto.bat"
)


class SnappyDriverOrigin(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "Snappy Driver Installer Origin (Chocolatey)"
        self.version: str = "1.0.0"
        self.platforms: list = ["windows"]
        self.dependencies: list = ["chocolatey"]

        self.admins: dict = {
            "windows": ["install", "upgrade", "uninstall"]
        }

    def install(self) -> int:
        rc, message = chocos.install_package(CHOCO_PACKAGE_NAME)
        if rc == 0:
            try:
                shortcuts.create_desktop_shortcut(SDIO_BAT_PATH, "SDI Origin")
                console.print("[green]Desktop shortcut created: SDI Origin[/green]")
            except Exception as e:
                console.print(
                    f"[yellow]Could not create desktop shortcut: {e}\n"
                    f"You can run SDI Origin manually from: {SDIO_BAT_PATH}[/yellow]"
                )
        return rc

    def upgrade(self) -> int:
        rc, message = chocos.upgrade_package(CHOCO_PACKAGE_NAME)
        return rc

    def uninstall(self) -> int:
        rc, message = chocos.uninstall_package(CHOCO_PACKAGE_NAME)
        return rc

    def is_installed(self) -> bool:
        return shutil.which("SDIO") is not None

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            print(f"Windows: Installs {CHOCO_PACKAGE_NAME} from Chocolatey.\n")
        elif method == "upgrade":
            print(f"Windows: Upgrades {CHOCO_PACKAGE_NAME} via Chocolatey.\n")
        elif method == "uninstall":
            print(f"Windows: Uninstalls {CHOCO_PACKAGE_NAME} via Chocolatey.\n")
        else:
            raise ValueError(f"Unknown method '{method}'.")
