from rich.console import Console

from .commands import run_package_manager_command


console = Console()


def install_package(package_id: str) -> tuple[int, str]:
    console.print(f"[blue]Installing Chocolatey package: {package_id}[/blue]")

    return run_package_manager_command(
        [
            "choco",
            "install",
            package_id,
            "-y",            # accept all prompts
            # "--no-progress", # cleaner output (esp. in CI)
        ],
        action="Installation",
    )


def upgrade_package(package_id: str) -> tuple[int, str]:
    console.print(f"[blue]Upgrading Chocolatey package: {package_id}[/blue]")

    return run_package_manager_command(
        [
            "choco",
            "upgrade",
            package_id,
            "-y",
            # "--no-progress",
        ],
        action="Upgrade",
    )


def uninstall_package(package_id: str) -> tuple[int, str]:
    console.print(f"[blue]Uninstalling Chocolatey package: {package_id}[/blue]")

    return run_package_manager_command(
        [
            "choco",
            "uninstall",
            package_id,
            "-y",
            # "--no-progress",
        ],
        action="Uninstallation",
    )
