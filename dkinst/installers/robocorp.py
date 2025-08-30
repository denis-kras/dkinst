from pathlib import Path
from types import ModuleType
from typing import Literal
import subprocess
from rich.console import Console

from . import _base, tesseract_ocr, nodejs
from .helpers.infra import permissions


console = Console()


TESSERACT_BIN_EXE_PATH: str = str(Path(__file__).parent.parent / "tesseract_bin" / "tesseract.exe")


class Robocorp(_base.BaseInstaller):
    def __init__(self):
        super().__init__()
        self.name: str = Path(__file__).stem
        self.description: str = "Robocorp Installer"
        self.version: str = "1.0.2"
        self.platforms: list = ["windows"]
        self.helper: ModuleType | None = None

    def install(self):
        if not permissions.is_admin():
            console.print("Please run this script as an Administrator.", style="red")
            return 1

        console.print(f"Installing Tesseract OCR", style="blue")
        tesseract_ocr_wrapper = tesseract_ocr.TesseractOCR()
        tesseract_ocr_wrapper.install()

        console.print("Installing NodeJS.", style="blue")
        nodejs_wrapper = nodejs.NodeJS()
        nodejs_wrapper.install(force=True)

        console.print("PIP Installing Robocorp.", style="blue")
        subprocess.check_call(["pip", "install", "--upgrade", "rpaframework"])

        console.print("PIP Installing Robocorp-Browser.", style="blue")
        subprocess.check_call(["pip", "install", "--upgrade", "robotframework-browser"])

        console.print("PIP Installing Robocorp-Recognition.", style="blue")
        subprocess.check_call(["pip", "install", "--upgrade", "rpaframework-recognition"])

        console.print("Initializing Robocorp Browser.", style="blue")
        subprocess.check_call(["rfbrowser", "init"])

        # Robocorp browser init already installs the browsers.
        # console.print("Installing Playwright browsers.", style="blue")
        # subprocess.check_call(["playwright", "install"])

        console.print("Installing Additional modules.", style="blue")
        subprocess.check_call(["pip", "install", "--upgrade", "matplotlib", "imagehash", "pynput"])

        # Patch robocorp: Remove mouse to the center of the screen on control command.
        # Import the library to find its path.
        console.print(r"Patching: .\RPA\Windows\keywords\window.py", style="blue")
        import RPA.Windows.keywords.window as window
        window_file_path = window.__file__

        # Patch the file.
        with open(window_file_path, "r") as file:
            file_content = file.read()
        file_content = file_content.replace(
            "window.item.MoveCursorToMyCenter(simulateMove=self.ctx.simulate_move)",
            "# window.item.MoveCursorToMyCenter(simulateMove=self.ctx.simulate_move)    # Patched to remove center placement during foreground window control."
        )
        with open(window_file_path, "w") as file:
            file.write(file_content)

        console.print("Robocorp Framework installation/update finished.", style="green")

        return 0

    def update(
            self,
            force: bool = False
    ):
        self.install()

    def _show_help(
            self,
            method: Literal["install", "uninstall", "update"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method will install the following:\n"
                "  tesseract OCR binaries (dkinst).\n"
                "  NodeJS (dkinst).\n"
                "  Robocorp Framework (rpaframework - pip)\n"
                "  Robocorp-Browser Addon (robotframework-browser - pip)\n"
                "  Robocorp-Recognition Addon (rpaframework-recognition - pip).\n"
                "  Playwright Browsers\n"
                "  More pip packages: pynput, matplotlib, imagehash\n"
                "\n"
            )
            print(method_help)
        elif method == "update":
            print("In this installer 'update()' is the same as 'install()'.")
        else:
            raise ValueError(f"Unknown method '{method}'.")