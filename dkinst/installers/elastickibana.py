from pathlib import Path
from types import ModuleType
from typing import Literal

from rich.console import Console

from . import _base
from .helpers import elastic_manager


console = Console()


class ElasticKibana(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "Elastic Kibana 8 Installer"
        self.version: str = elastic_manager.VERSION
        self.platforms: list = ["debian"]
        self.helper: ModuleType = elastic_manager

    def install(
            self,
    ) -> int:
        return elastic_manager.main(install_search=True)

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method uses the [elastic_manager.py] with the following arguments:\n"
                "  --install-kibana       - install Kibana version 8.\n"
                "\n"
                "You can also use the 'manual' method to provide custom arguments to the helper script.\n"
                "Example:\n"
                "  dkinst manual elasticsearch help\n"
                "\n"
                "You can also install both Elasticsearch and Kibana with the following command in one execution:\n"
                "  dkinst manual elasticsearch -is -ik\n"
                "\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")
