import os
from typing import Literal

from rich.console import Console

from atomicshop.wrappers import githubw

from . import _base


console = Console()


class Rufus(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "Rufus Installer"
        self.version: str = "1.0.0"
        # Initial.
        self.platforms: list = ["windows"]

    def install(
            self,
    ) -> int:
        return install_function(self.dir_path)

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method Downloads the Rufus portable exe from the official GitHub repo\n"
                "\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")


def install_function(
        target_dir: str,
) -> int:
    os.makedirs(target_dir, exist_ok=True)

    github_wrapper: githubw.GitHubWrapper = githubw.GitHubWrapper(
        user_name="pbatard",
        repo_name="rufus"
    )
    rufus_exe_path: str = github_wrapper.download_latest_release(
        target_directory=target_dir,
        asset_pattern="*rufus*p.exe"
    )

    console.print(f"[green]Rufus portable exe has been downloaded to: {rufus_exe_path}[/green]")

    return 0