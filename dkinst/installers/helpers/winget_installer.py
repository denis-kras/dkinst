import sys
import argparse
import shutil
import os
import tempfile

from rich.console import Console

from atomicshop.wrappers import githubw

from .infra import system, appxs, powershells, permissions
from .infra.printing import printc


console = Console()


VERSION: str = "1.0.0"
"""Initial"""


AKA_MS_GETWINGET_URL: str = "https://aka.ms/getwinget"
APPX_PACKAGE_NAME: str = "Microsoft.DesktopAppInstaller_8wekyb3d8bbwe"


def is_winget_installed() -> bool:
    """
    Check if winget command exists.
    """
    print("Checking if winget is installed...")
    winget_path: str = shutil.which("winget")
    if winget_path:
        print(f"winget is installed at: {winget_path}")
        return True
    else:
        print("winget is not installed.")
        return False


def install_winget_and_dependencies_from_akams() -> int:
    """
    Install winget and its dependencies from "https://aka.ms/getwinget" with 'Add-AppxPackage'.
    """

    console.print(f"Installing winget and its dependencies from {AKA_MS_GETWINGET_URL}...", style="cyan")
    rc, stdout, stderr = appxs.add_appx_by_file(AKA_MS_GETWINGET_URL)
    if rc != 0:
        if "HRESULT: 0x80073D06, The package could not be installed because a higher version of this package is already installed" in stderr:
            console.print(f'Appx {AKA_MS_GETWINGET_URL} is already installed with a higher version. Skipping.',
                          style='yellow')
        else:
            console.print(f'Failed to add Appx: {AKA_MS_GETWINGET_URL}', style='red')
            console.print(stderr, style='red')
            return rc

    return 0


def install_dependencies_from_github() -> int:
    github_wrapper: githubw.GitHubWrapper = githubw.GitHubWrapper(
        user_name="microsoft",
        repo_name="winget-cli"
    )

    winget_temp_directory: str = tempfile.mkdtemp()

    github_wrapper.download_and_extract_latest_release(
        target_directory=winget_temp_directory,
        asset_pattern='*Dependencies.zip')

    # Get current CPU architecture.
    current_arch: str = system.get_architecture()
    arch_folder_path: str = os.path.join(winget_temp_directory, current_arch)

    # Get all the appx files in the architecture folder.
    appx_files: list[str] = [f for f in os.listdir(arch_folder_path) if f.endswith('.appx')]

    # Install all the dependencies appx files.
    for appx_file in appx_files:
        appx_file_path: str = os.path.join(arch_folder_path, appx_file)
        printc(f'Adding Appx: {appx_file_path}', color='blue')

        rc, stdout, stderr = appxs.add_appx_by_file(appx_file_path)
        if rc != 0:
            if "HRESULT: 0x80073D06, The package could not be installed because a higher version of this package is already installed" in stderr:
                printc(f'Appx {appx_file_path} is already installed with a higher version. Skipping.', color='yellow')
            else:
                printc(f'Failed to add Appx: {appx_file_path}', color='red')
                printc(stderr, color='red')
                return rc

    # Remove the temp directory.
    shutil.rmtree(winget_temp_directory)

    return 0


def install_winget_ps_module() -> int:
    if not permissions.is_admin():
        console.print("This operation requires administrative privileges. Please run as administrator.", style="red")
        return 1

    console.print("Installing the NuGet PowerShell module and the Winget PowerShell module...", style="cyan")

    # Install NuGet provider.
    command: str = "Install-PackageProvider -Name NuGet -Force"
    rc, stdout, stderr = powershells.run_command(command)
    if rc != 0:
        console.print("Failed to install NuGet package provider.", style="red")
        console.print(stderr, style="red")
        return rc

    # Install Winget PowerShell module.
    command = "Install-Module Microsoft.WinGet.Client -Force -Repository PSGallery"
    rc, stdout, stderr = powershells.run_command(command)
    if rc != 0:
        console.print("Failed to install Microsoft.WinGet.Client PowerShell module.", style="red")
        console.print(stderr, style="red")
        return rc

    # Install Winget itself using the PowerShell module.
    command = "Repair-WinGetPackageManager -AllUsers"
    rc, stdout, stderr = powershells.run_command(command)
    if rc != 0:
        console.print("Failed to install/repair Winget using the PowerShell module.", style="red")
        console.print(stderr, style="red")
        return rc

    return 0


def install_winget_from_github() -> int:
    github_wrapper: githubw.GitHubWrapper = githubw.GitHubWrapper(
        user_name="microsoft",
        repo_name="winget-cli"
    )

    winget_temp_directory: str = tempfile.mkdtemp()

    # Download the main msixbundle file.
    winget_msix_path: str = github_wrapper.download_latest_release(
        target_directory=winget_temp_directory,
        asset_pattern='*Microsoft.DesktopAppInstaller*.msixbundle')

    printc(f'Installing Winget with: {winget_msix_path}', color='blue')
    appxs.add_appx_by_file(winget_msix_path)

    # Remove the temp directory.
    shutil.rmtree(winget_temp_directory)

    return 0


def register_winget_package() -> int:
    console.print("Registering the 'WinGet' package...", style="cyan")
    rc, stdout, stderr = appxs.register_appx_by_family_name(APPX_PACKAGE_NAME)

    if rc != 0:
        console.print(f'Failed to register the WinGet package.', style='red')
        console.print(stderr, style='red')
        return rc

    return 0


def _make_parser():
    parser = argparse.ArgumentParser(description="Install WinGet.")
    parser.add_argument(
        '-ip', '--install-ps-module',
        action='store_true',
        help=f"Install the NuGet powershell module, winget ps module and winget itself.\n"
             f"This is the easiest method."
    )
    parser.add_argument(
        '-ia', '--install-aka-ms',
        action='store_true',
        help=f"Install the latest version from: {AKA_MS_GETWINGET_URL}"
    )
    parser.add_argument(
        '-ig', '--install-github',
        action='store_true',
        help="Install the latest version from GitHub."
    )
    parser.add_argument(
        '-id', '--install-dependencies',
        action='store_true',
        help="Install Dependencies from GitHub."
    )

    parser.add_argument(
        '-r', '--register',
        action='store_true',
        help="Register the 'WinGet' package if the command is still not recognized after first login."
    )

    parser.add_argument(
        '-f', '--force',
        action='store_true',
        help="Force installation, even if winget is already installed."
    )

    return parser


def main(
        install_ps_module: bool = False,
        install_aka_ms: bool = False,
        install_github: bool = False,
        force: bool = False,
        install_dependencies: bool = False,
        register: bool = False
) -> int:
    """
    The function will install/repair WinGet on Windows.

    :param install_ps_module: bool, If True, install the NuGet powershell module, winget ps module and winget itself.
    :param install_aka_ms: bool, If True, install winget from aka.ms/getwinget.
    :param install_github: bool, If True, install winget from GitHub.
    :param force: bool, If True, force installation even if winget is already installed.
    :param install_dependencies: bool, If True, install winget dependencies from GitHub.
    :param register: bool, If True, register the 'WinGet' package if the command is still not recognized after first login.

    :return: int, Return code of the installation process. 0 if successful, non-zero otherwise.
    """

    if install_ps_module and install_aka_ms and install_github:
        console.print("Only one of the arguments can be set to True: install_aka_ms, install_github.", style="red")
        return 1

    if install_ps_module or install_aka_ms or install_github:
        if is_winget_installed() and not force:
            console.print("Winget is already installed. Exiting.", style="green")
            return 0

    if install_dependencies:
        rc: int = install_dependencies_from_github()
        if rc != 0:
            return rc
    if install_ps_module:
        rc: int = install_winget_ps_module()
        if rc != 0:
            return rc
    if install_aka_ms:
        rc: int = install_winget_and_dependencies_from_akams()
        if rc != 0:
            return rc
    if install_github:
        rc: int = install_winget_from_github()
        if rc != 0:
            return rc

    if register:
        rc: int = register_winget_package()
        if rc != 0:
            return rc

    return 0


if __name__ == '__main__':
    nodejs_parser = _make_parser()
    args = nodejs_parser.parse_args()
    sys.exit(main(**vars(args)))