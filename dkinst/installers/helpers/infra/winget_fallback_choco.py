from typing import Literal

from rich.console import Console

from . import wingets, chocos
from .printing import printc
from ..import winget_installer
from ... import chocolatey


console = Console()


"""
This module will try to use winget to install, upgrade, and uninstall packages.
But if winget fails, the caller will check if chocolatey is installed and if so, will use it as a fallback.
"""


def method_package(
        method: Literal["install", "uninstall", "upgrade"],
        winget_package_id: str,
        choco_package_name: str,
        force: bool = False
) -> int:
    """
    Try to use winget to install/upgrade/uninstall a package, and if it fails, use chocolatey as a fallback.

    :param method: any of "install", "uninstall", "upgrade".
    :param winget_package_id: The package ID for winget.
    :param choco_package_name: The package name for chocolatey.
    :param force: bool,
        True: if winget is installed and failed, force install with chocolatey.
        False: only use chocolatey if winget is not installed.
    :return: int: return code, 0 if success, non-zero if failure.
    """

    # Check if winget is available.
    is_winget_available: bool = winget_installer.is_winget_installed()

    # Get method from wingets.
    callable_wingets = getattr(wingets, f'{method}_package')
    rc, output = callable_wingets(winget_package_id)
    if rc == 0:
        return 0

    # if rc != 0 and 'No newer package versions are available' in output:
    #     printc(f"No newer package versions are available for {winget_package_id}.", color="yellow")
    #     return 0

    if rc != 0 and is_winget_available and not force:
        printc(f"Failed to {method} with WinGet.\n"
               f"You can use 'force=True' in order to try to install with Chocolatey.", color="red")
        return rc
    else:
        printc(f"Failed to {method} with WinGet, trying Chocolatey...", color="yellow")

    choco_installer = chocolatey.Chocolatey()
    rc: int = choco_installer.install()
    if rc != 0:
        printc("Failed to install Chocolatey.", color="red")
        return rc

    # Get method from chocos.
    callable_chocos = getattr(chocos, f'{method}_package')
    rc, output = callable_chocos(choco_package_name)
    if rc != 0:
        printc(f"Failed to {method} with Chocolatey.", color="red")
        return rc

    return 0
