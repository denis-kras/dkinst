import subprocess

from rich.console import Console


console = Console()


def _run_choco(cmd: list[str], action: str) -> int:
    """Run a choco command and handle output and errors nicely."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        console.print("[red]choco was not found on PATH. Is Chocolatey installed?[/red]")
        return 1

    if result.returncode != 0:
        console.print(f"[red]{action} failed with exit code {result.returncode}[/red]")

        if result.stderr:
            console.print(result.stderr)
        elif result.stdout:
            console.print(result.stdout)

        return result.returncode

    console.print(f"[green]{action} completed successfully.[/green]")
    return 0


def install_package(package_id: str) -> int:
    console.print(f"[blue]Installing Chocolatey package: {package_id}[/blue]")

    return _run_choco(
        [
            "choco",
            "install",
            package_id,
            "-y",            # accept all prompts
            # "--no-progress", # cleaner output (esp. in CI)
        ],
        action="Installation",
    )


def upgrade_package(package_id: str) -> int:
    console.print(f"[blue]Upgrading Chocolatey package: {package_id}[/blue]")

    return _run_choco(
        [
            "choco",
            "upgrade",
            package_id,
            "-y",
            # "--no-progress",
        ],
        action="Upgrade",
    )


def uninstall_package(package_id: str) -> int:
    console.print(f"[blue]Uninstalling Chocolatey package: {package_id}[/blue]")

    return _run_choco(
        [
            "choco",
            "uninstall",
            package_id,
            "-y",
            # "--no-progress",
        ],
        action="Uninstallation",
    )
