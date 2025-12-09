from pathlib import Path
from types import ModuleType
import os
import subprocess
import time
from typing import Literal

from atomicshop.wrappers import githubw
from atomicshop import filesystem

from . import _base
from .helpers.infra import msis
from .helpers.infra.printing import printc


DEFAULT_INSTALLATION_EXE_PATH = r"C:\Program Files\Fibratus\Bin\fibratus.exe"
WAIT_SECONDS_FOR_EXECUTABLE_TO_APPEAR_AFTER_INSTALLATION: float = 10


class Fibratus(_base.BaseInstaller):
    def __init__(self):
        super().__init__(__file__)
        self.description: str = "Fibratus Installer"
        self.version: str = "1.0.0"
        self.platforms: list = ["windows"]

    def install(
            self
    ):
        return install_function()

    def _show_help(
            self,
            method: Literal["install", "uninstall", "upgrade"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "The latest MSI installer is downloaded from the GitHub releases page and installed silently.\n"
                "\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")


def install_function(
        installation_file_download_directory: str = None,
        place_to_download_file: Literal['working', 'temp', 'script'] = 'temp',
        remove_file_after_installation: bool = True
) -> int:
    """
    Download latest release from GitHub and install Fibratus.
    :param installation_file_download_directory: Directory to download the installation file. If None, the download
        directory will be automatically determined, by the 'place_to_download_file' parameter.
    :param place_to_download_file: Where to download the installation file.
        'working' is the working directory of the script.
        'temp' is the temporary directory.
        'script' is the directory of the script.
    :param remove_file_after_installation: Whether to remove the installation file after installation.
    :return:
    """

    if not installation_file_download_directory:
        installation_file_download_directory = filesystem.get_download_directory(
            place=place_to_download_file, script_path=__file__)

    github_wrapper = githubw.GitHubWrapper(user_name='rabbitstack', repo_name='fibratus')
    fibratus_setup_file_path: str = github_wrapper.download_latest_release(
        target_directory=installation_file_download_directory,
        asset_pattern='*fibratus-*-amd64.msi',
        exclude_string='slim')

    # Install the MSI file
    msis.install_msi(msi_path=fibratus_setup_file_path, silent_progress_bar=True)

    count = 0
    while count != WAIT_SECONDS_FOR_EXECUTABLE_TO_APPEAR_AFTER_INSTALLATION:
        if os.path.isfile(DEFAULT_INSTALLATION_EXE_PATH):
            break
        count += 1
        time.sleep(1)

    if count == WAIT_SECONDS_FOR_EXECUTABLE_TO_APPEAR_AFTER_INSTALLATION:
        message = \
            (f"Fibratus installation failed. The executable was not found after "
             f"{str(WAIT_SECONDS_FOR_EXECUTABLE_TO_APPEAR_AFTER_INSTALLATION)} seconds.\n"
             f"{DEFAULT_INSTALLATION_EXE_PATH}")
        printc(message, color="red")
        return 1

    # Check if the installation was successful
    try:
        result = subprocess.run([DEFAULT_INSTALLATION_EXE_PATH], capture_output=True, text=True)
    except FileNotFoundError:
        printc("Fibratus executable not found.", color="red")
        return 1

    if result.returncode == 0:
        printc("Fibratus installed successfully. Please restart.", color="green")
    else:
        printc("Fibratus installation failed.", color="red")
        printc(result.stderr, color='red')
        return 1

    # Wait for the installation to finish before removing the file.
    time.sleep(5)

    if remove_file_after_installation:
        filesystem.remove_file(fibratus_setup_file_path)

    return 0
