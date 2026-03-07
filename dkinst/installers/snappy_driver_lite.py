import os
from types import ModuleType
from typing import Literal

from . import _base
from .helpers import snappy_driver_lite_installer


class SnappyDriverLite(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "Snappy Driver Installer Lite (Portable)"
        self.version: str = snappy_driver_lite_installer.VERSION
        self.platforms: list = ["windows"]
        self.helper: ModuleType = snappy_driver_lite_installer

    def install(self) -> int:
        return snappy_driver_lite_installer.install(self.dir_path)

    def upgrade(self) -> int:
        return snappy_driver_lite_installer.upgrade(self.dir_path)

    def is_installed(self) -> bool:
        return os.path.isdir(self.dir_path) and bool(os.listdir(self.dir_path))

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            print(
                f"Downloads SDI Lite from sdi-tool.org and extracts to: {self.dir_path}\n"
                "\n"
                "You can also use the 'manual' method:\n"
                "  dkinst manual snappy_driver_lite help\n"
                "  dkinst manual snappy_driver_lite -i\n"
            )
        elif method == "upgrade":
            print(
                "Checks for a newer version on sdi-tool.org.\n"
                "If available, removes the current installation and installs the new version.\n"
            )
        else:
            raise ValueError(f"Unknown method '{method}'.")
