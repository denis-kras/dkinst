from pathlib import Path
from types import ModuleType
from typing import Literal

from . import _base
from . helpers import ffmpeg_manager


class FFMPEG(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "FFMPEG Portable for Windows"
        self.version: str = ffmpeg_manager.VERSION
        self.platforms: list = ["windows"]
        self.helper: ModuleType = ffmpeg_manager

        self.dependencies: list[str] = ['winget']

        # These are currently not in use since we're using winget, but in the future we might need them.
        # self.exe_path: str = str(Path(self.dir_path) / "ffmpeg.exe")

    def install(
            self,
    ):
        return ffmpeg_manager.main(install_full_winget=True)

    def uninstall(
            self,
    ):
        return ffmpeg_manager.main(uninstall_full_winget=True)

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method uses WinGet to install Gyan FFMPEG Full latest version.\n"
                "YOu can also install/uninstall other versions using manual:\n"
                "Example:\n"
                "  dkinst manual ffmpeg help\n"
                "  dkinst manual ffmpeg --install-full-winget\n"
                "  dkinst manual ffmpeg --install-essential-winget\n"
                "  dkinst manual ffmpeg --uninstall-essential-winget\n"
                "\n"
            )
            print(method_help)
        elif method == "uninstall":
            print("Uses WinGet to uninstall the Gyan FFMPEG Full latest version.")
        else:
            raise ValueError(f"Unknown method '{method}'.")