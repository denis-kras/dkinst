from pathlib import Path
from types import ModuleType
from typing import Literal

from . import _base
from .helpers.modules import docker_installer


class PyCharm(_base.BaseInstaller):
    def __init__(self):
        super().__init__()
        self.name: str = Path(__file__).stem
        self.description: str = "Docker Installer"
        self.version: str = docker_installer.VERSION
        self.platforms: list = ["debian"]
        self.helper: ModuleType | None = docker_installer

    def install(
            self,
    ):
        return docker_installer.main(install=True, add_user_to_docker_group=True)

    def _show_help(
            self,
            method: Literal["install", "uninstall", "update"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method uses the [docker_installer.py] with the following arguments:\n"
                "  --install                        - installs using docker installer (https://get.docker.com/).\n"
                "  --add-user-to-docker-group       - adds the current user to the 'docker' group to allow running docker commands without 'sudo'.\n"
                "\n"
                "You can also use the 'manual' method to provide custom arguments to the helper script.\n"
                "Example:\n"
                "  dkinst manual docker help\n"
                "  dkinst manual docker --install-rootless\n"
                "\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")