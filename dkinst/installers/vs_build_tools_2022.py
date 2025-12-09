from pathlib import Path
from types import ModuleType
from typing import Literal

from . import _base
from .helpers import vs_build_tools_installer


class VLC(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "MS VS Build Tools 2022 Installer"
        self.version: str = vs_build_tools_installer.VERSION
        self.platforms: list = ["windows"]
        self.helper: ModuleType = vs_build_tools_installer

    def install(
            self,
            force: bool = False
    ):
        return vs_build_tools_installer.main(install=True, force=force)

    def is_installed(self) -> bool:
        return vs_build_tools_installer.is_msvc_installed()

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method installs Microsoft Visual Studio Build Tools 2022 from 'aka.ms'.\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")