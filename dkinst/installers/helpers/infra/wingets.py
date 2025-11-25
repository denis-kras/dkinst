import subprocess

from rich.console import Console


console = Console()


def install_package(package_id: str) -> int:
    console.print(f"[blue]Installing WinGet package ID: {package_id}[/blue]")

    result = subprocess.run(
        # ["winget", "install", f"--id={package_id}", "--silent"],
        ["winget", "install", f"--id={package_id}", "-e", "--accept-source-agreements", "--accept-package-agreements"],
        check=True,
        # capture_output=True,
        # text=True
    )

    if result.returncode != 0:
        console.print(f"[red]Installation failed with error:[/red] {result.stderr}")
        return result.returncode

    console.print(f"[green]Installation completed successfully.[/green]")
    return 0


def upgrade_package(package_id: str) -> int:
    console.print(f"[blue]Upgrading WinGet package ID: {package_id}[/blue]")

    result = subprocess.run(
        ["winget", "upgrade", f"--id={package_id}", "-e", "--accept-source-agreements", "--accept-package-agreements"],
        check=True,
    )

    if result.returncode != 0:
        console.print(f"[red]Upgrade failed with error:[/red] {result.stderr}")
        return result.returncode

    console.print(f"[green]Upgrade completed successfully.[/green]")
    return 0


def uninstall_package(package_id: str) -> int:
    console.print(f"[blue]Uninstalling WinGet package ID: {package_id}[/blue]")

    result = subprocess.run(
        ["winget", "uninstall", f"--id={package_id}", "-e"],
        check=True,
    )

    if result.returncode != 0:
        console.print(f"[red]Uninstallation failed with error:[/red] {result.stderr}")
        return result.returncode

    console.print(f"[green]Uninstallation completed successfully.[/green]")
    return 0