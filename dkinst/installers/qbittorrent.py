from pathlib import Path
from typing import Literal

from rich.console import Console

from . import _base
from .helpers.infra import system, chocos


console = Console()


CHOCO_PACKAGE_NAME: str = "qbittorrent"

DEBIAN_INSTALL_UPGRADE_SCRIPT = [
        """

sudo apt update
sudo apt install -y qbittorrent
"""]


class QBitTorrent(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "qTorrent Installer"
        self.version: str = "1.1.0"
        # Added windows.
        self.platforms: list = ["debian", "windows"]
        self.dependencies: list = ["chocolatey"]

    def install(
            self,
    ):
        return install_function()

    def upgrade(
            self,
    ):
        return upgrade_function()

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
                f"Windows: This method installs {self.name} from Chocolatey repo (choco has the latest version faster).\n"
                f"Debian: This method installs {self.name} from apt repo.\n"
            )
            print(method_help)
        elif method == "upgrade":
            method_help: str = (
                f"Windows: This method upgrades {self.name} from Chocolatey repo (choco has the latest version faster).\n"
                f"Debian: This method upgrades {self.name} from apt repo.\n"
            )
            print(method_help)
        elif method == "uninstall":
            method_help: str = (
                f"Windows: This method uninstalls {self.name} using Chocolatey.\n"
                f"Debian: This method uninstalls {self.name} using apt.\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")


def install_function() -> int:
    current_platform: str = system.get_platform()
    if current_platform == "debian":
        system.execute_bash_script_string(DEBIAN_INSTALL_UPGRADE_SCRIPT)
    elif current_platform == "windows":
        chocos.install_package(CHOCO_PACKAGE_NAME)
    else:
        console.print(f"Platform '{current_platform}' is not supported by this installer.", style="red")
        return 1

    return 0


def upgrade_function() -> int:
    current_platform: str = system.get_platform()
    if current_platform == "debian":
        system.execute_bash_script_string(DEBIAN_INSTALL_UPGRADE_SCRIPT)
    elif current_platform == "windows":
        chocos.upgrade_package(CHOCO_PACKAGE_NAME)
    else:
        console.print(f"Platform '{current_platform}' is not supported by this installer.", style="red")
        return 1

    return 0


def uninstall_function() -> int:
    current_platform: str = system.get_platform()
    if current_platform == "debian":
        system.execute_bash_script_string([
            """
sudo apt remove -y qbittorrent
sudo apt purge qbittorrent
sudo apt autoremove
"""])
    elif current_platform == "windows":
        chocos.uninstall_package(CHOCO_PACKAGE_NAME)
    else:
        console.print(f"Platform '{current_platform}' is not supported by this installer.", style="red")
        return 1

    return 0