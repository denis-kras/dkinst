from types import ModuleType
from typing import Literal

from rich.console import Console

from . import _base
from .helpers import crowdsec_installer


console = Console()


class ElasticKibana(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "Crowdsec Installer"
        self.version: str = crowdsec_installer.VERSION
        self.platforms: list = ["debian"]
        self.helper: ModuleType = crowdsec_installer

        self.admins: dict = {"debian": ["install", "uninstall"]}

    def install(
            self,
    ) -> int:
        return crowdsec_installer.main(install=True, enable_all=True)

    def uninstall(
            self
    ) -> int:
        return crowdsec_installer.main(uninstall=True)

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method uses the [crowdsec_installer.py] with the following arguments:\n"
                "  --install --enable-all\n"
                "\n"
                "You can also use the 'manual' method to provide custom arguments to the helper script.\n"
                "Example:\n"
                "  dkinst manual crowdsec help\n"
                "\n"
            )
            print(method_help)
        elif method == "uninstall":
            method_help: str = (
                "This method uses the [crowdsec_installer.py] with the following arguments:\n"
                "  --uninstall\n"
                "\n"
                "You can also use the 'manual' method to provide custom arguments to the helper script.\n"
                "Example:\n"
                "  dkinst manual crowdsec help\n"
                "\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")
