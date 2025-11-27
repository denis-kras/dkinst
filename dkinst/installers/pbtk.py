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
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method downloads the master branch of the pbtk github repo to the default dkinst portable forlder in config file.\n"
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