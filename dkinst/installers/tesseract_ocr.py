import shutil
from pathlib import Path
from types import ModuleType
from typing import Literal
import os

from rich.console import Console

from . import _base
from .helpers import tesseract_ocr_manager


console = Console()


class TesseractOCR(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "Tesseract OCR Installer"
        self.version: str = tesseract_ocr_manager.VERSION
        self.platforms: list = ["windows"]
        self.helper: ModuleType = tesseract_ocr_manager
        self.admins: dict = {"windows": ["install", "upgrade"]}

        self.dependencies: list[str] = ['vs_build_tools_2022', 'git']

        self.exe_path: str = str(Path(self.dir_path) / "tesseract.exe")

    def install(
            self,
            force: bool = False
    ) -> int:
        return install_function(exe_path=self.exe_path, force=force)

    def upgrade(
            self,
            force: bool = False
    ) -> int:
        return self.install(force=force)

    def is_installed(self) -> bool:
        command_available: bool =  shutil.which("tesseract") is not None
        path_available: bool = os.path.isfile(self.exe_path)

        if command_available and path_available:
            return True
        else:
            if not command_available:
                console.print("[yellow]tesseract command not found in system PATH.[/yellow]")
            if not path_available:
                console.print(f"[yellow]tesseract executable not found at '{self.exe_path}'.[/yellow]")
            return False

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method uses the [tesseract_ocr_manager.py] with the following arguments:\n"
                "  --compile-portable               - compile the latest tesseract executable.\n"
                "  --set-path                       - set system PATH variable to provided executable.\n"
                f'  --exe-path "{self.exe_path}"                      - Specify the target executable\n'
                "\n"
                "  --force                          - force reinstallation/recompilation of the latest version even if executable is already present.\n"
                "  This one is used only if you provide it explicitly to the 'install' command. Example:\n"
                "    dkinst install tesseract_ocr force\n"
                "  --languages f                    - Specify language packs branch. 'f' is for 'fast'.\n"
                "  --download eng,osd               - Specify language packs to download.\n"
                "  --download-configs               - Download config files.\n"
                "Note: the specific languages and configs arguments, mimic the EXE installer behavior.\n"
                "\n"
                "You can also use the 'manual' method to provide custom arguments to the helper script.\n"
                "Example:\n"
                "  dkinst manual tesseract_ocr help\n"
                "  dkinst manual tesseract_ocr --compile-portable --set-path\n"
                "\n"
            )
            print(method_help)
        elif method == "upgrade":
            print("In this installer 'upgrade()' is the same as 'install()'.")
        else:
            raise ValueError(f"Unknown method '{method}'.")


def install_function(
        exe_path: str,
        force: bool = False
) -> int:
    rc: int = tesseract_ocr_manager.main(
        compile_portable=True,
        set_path=True,
        exe_path=exe_path,
        force=force
    )
    if rc != 0:
        return rc

    rc: int = tesseract_ocr_manager.main(
        languages='f',
        lang_download=['eng', 'osd'],
        download_configs=True
    )
    if rc != 0:
        return rc

    # Remove duplicate config files from tessdata folder.
    files_list: list[str] = [
        'batch',
        'batch.nochop',
        'eng.user-patterns',
        'eng.user-words',
        'LICENSE',
        'Makefile.am',
        'matdemo',
        'msdemo',
        'nobatch',
        'README.md',
        'segdemo'
    ]

    # Get tessdata environment variable
    tessdata_path: str | None = os.environ.get("TESSDATA_PREFIX", None)
    if tessdata_path is not None:
        for file_name in files_list:
            file_path: str = str(Path(tessdata_path) / file_name)
            if os.path.isfile(file_path):
                os.remove(file_path)

    return 0