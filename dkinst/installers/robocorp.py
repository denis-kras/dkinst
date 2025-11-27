from pathlib import Path
from types import ModuleType
from typing import Literal
import subprocess
from rich.console import Console

from . import _base


console = Console()


class Robocorp(_base.BaseInstaller):
    def __init__(self):
        super().__init__()
        self.name: str = Path(__file__).stem
        self.description: str = "Robocorp Installer"
        self.version: str = "1.0.2"
        self.platforms: list = ["windows"]

        self.dependencies: list[str] = ['tesseract_ocr', 'nodejs']
        self.admins: dict = {
            "windows": ["install", "upgrade"]
        }

    def install(self):
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

        console.print("Robocorp Framework installation/upgrade finished.", style="green")

        return 0

    def upgrade(
            self,
            force: bool = False
    ):
        self.install()

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
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
        elif method == "upgrade":
            print("In this installer 'upgrade()' is the same as 'install()'.")
        else:
            raise ValueError(f"Unknown method '{method}'.")