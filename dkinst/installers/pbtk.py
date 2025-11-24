from pathlib import Path
from types import ModuleType
from typing import Literal
import os

from atomicshop.wrappers import githubw

from . import _base
from .helpers.infra.printing import printc


class PBTK(_base.BaseInstaller):
    def __init__(self):
        super().__init__()
        self.name: str = Path(__file__).stem
        self.description: str = "pbtk script Installer"
        self.version: str = "1.0.0"
        self.platforms: list = ["windows", "debian"]
        self.helper: ModuleType | None = None

        self.dir_path: str = str(Path(self.base_path) / self.name)

    def install(
            self,
            force: bool = False
    ):
        return install_function(target_directory=self.dir_path)

    def _show_help(
            self,
            method: Literal["install", "uninstall", "update"]
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
        else:
            raise ValueError(f"Unknown method '{method}'.")


def install_function(
        target_directory: str | None,
) -> int:
    printc("Downloading pbtk from GitHub...", color="blue")

    os.makedirs(target_directory, exist_ok=True)

    github_wrapper: githubw.GitHubWrapper = githubw.GitHubWrapper(
        user_name="marin-m",
        repo_name="pbtk",
        branch="master"
    )

    github_wrapper.download_and_extract_branch(
        target_directory=target_directory,
        archive_remove_first_directory=True
    )

    printc(f"pbtk instaled to: {target_directory}", color="green")

    return 0