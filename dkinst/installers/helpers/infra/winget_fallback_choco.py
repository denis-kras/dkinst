from typing import Literal

from rich.console import Console

from . import wingets, chocos
from .printing import printc
from ... import chocolatey


console = Console()


"""
This module will try to use winget to install, upgrade, and uninstall packages.
But if winget fails, the caller will check if chocolatey is installed and if so, will use it as a fallback.
"""


def method_package(
        method: Literal["install", "uninstall", "upgrade"],
        winget_package_id: str,
        choco_package_name: str
) -> int:
    # Get method from wingets.
    callable_wingets = getattr(wingets, f'{method}_package')
    rc: int = callable_wingets(winget_package_id)
    if rc != 0:
        printc(f"Failed to {method} with WinGet, trying Chocolatey...", color="yellow")
    else:
        return 0

    choco_installer = chocolatey.Chocolatey()
    rc: int = choco_installer.install()
    if rc != 0:
        printc("Failed to install Chocolatey.", color="red")
        return rc

    # Get method from chocos.
    callable_chocos = getattr(chocos, f'{method}_package')
    rc: int = callable_chocos(choco_package_name)
    if rc != 0:
        printc(f"Failed to {method} with Chocolatey.", color="red")
        return rc

    return 0
