from rich.console import Console

from .commands import run_package_manager_command


console = Console()


def install_package(package_id: str) -> tuple[int, str]:
    console.print(f"[blue]Installing WinGet package ID: {package_id}[/blue]")

    return run_package_manager_command(
        [
            "winget",
            "install",
            f"--id={package_id}",
            "-e",
            "--accept-source-agreements",
            "--accept-package-agreements",
        ],
        action="Installation",
    )


def upgrade_package(package_id: str) -> tuple[int, str]:
    console.print(f"[blue]Upgrading WinGet package ID: {package_id}[/blue]")

    return run_package_manager_command(
        [
            "winget",
            "upgrade",
            f"--id={package_id}",
            "-e",
            "--accept-source-agreements",
            "--accept-package-agreements",
        ],
        action="Upgrade",
    )


def uninstall_package(package_id: str) -> tuple[int, str]:
    console.print(f"[blue]Uninstalling WinGet package ID: {package_id}[/blue]")

    return run_package_manager_command(
        [
            "winget",
            "uninstall",
            f"--id={package_id}",
            "-e",
        ],
        action="Uninstallation",
    )
