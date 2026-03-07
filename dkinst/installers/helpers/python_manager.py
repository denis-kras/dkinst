import sys
import os
import subprocess
import shlex

from rich.console import Console

from .infra import commands


console = Console()


SCRIPT_NAME: str = "Python Manager"
AUTHOR: str = "Denis Kras"
VERSION: str = "1.0.3"
RELEASE_COMMENT: str = "Initial version."


def _get_cmd_script_path() -> str:
    """Resolve the path to the bundled install_python_as_admin_win.cmd script."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "prereqs", "install_python_as_admin_win.cmd")


def install(version: str) -> int:
    """
    Install a specific Python minor version (e.g. '3.13').
    The bundled CMD script resolves the latest micro and installs it.
    """
    print(f"Starting Python {version} installation...")

    cmd_file_path: str = _get_cmd_script_path()
    if not os.path.isfile(cmd_file_path):
        console.print(f"[red]The Python installer script does not exist at path: {cmd_file_path}[/red]")
        return 1

    command: list = ["cmd.exe", "/c", cmd_file_path, version]
    print(f"Executing: {shlex.join(command)}")

    rc, message = commands.run_package_manager_command(command, "Install")
    if rc != 0:
        console.print(f"[red]Failed to install.[/red]")
        console.print(f"[red]{message}[/red]")
        return rc

    console.print(f"[green]Python {version} has been successfully installed.[/green]")
    return 0


def upgrade() -> int:
    """Upgrade current Python minor version to its latest micro release."""
    print("Starting Python Micro Version Upgrade Process...")

    current_python_version = sys.version_info
    current_minor_version: str = f"{current_python_version.major}.{current_python_version.minor}"

    print(f"Current Python Version: {current_minor_version}.{current_python_version.micro}")

    cmd_file_path: str = _get_cmd_script_path()
    if not os.path.isfile(cmd_file_path):
        console.print(f"[red]The Python installer script does not exist at path: {cmd_file_path}[/red]")
        return 1

    # Get the latest python version of the current minor version.
    command: list = ["cmd.exe", "/c", cmd_file_path, current_minor_version, '-l']
    print(f"Executing: {shlex.join(command)}")
    result = subprocess.run(command, capture_output=True)
    if result.returncode != 0:
        console.print(f"[red]Failed to run the Python installer script. Error:\n"
                      f"{result.stderr.decode()}[/red]")
        return 1

    latest_version: str = result.stdout.decode().strip()
    console.print(f"Latest Python Micro Version with Installer: {latest_version}")

    latest_major, latest_minor, latest_micro = map(int, latest_version.split('.'))
    if latest_micro > current_python_version.micro:
        console.print(f"[yellow]A new Python version is available: {latest_version} "
                      f"(current: {current_minor_version}.{current_python_version.micro})[/yellow]")
        command: list = ["cmd.exe", "/c", cmd_file_path, latest_version]
        print(f"Executing: {shlex.join(command)}")
        console.print(f"Running the installer to upgrade Python to version {latest_version}...")

        rc, message = commands.run_package_manager_command(command, "Install")
        if rc != 0:
            console.print(f"[red]Failed to install.[/red]")
            console.print(f"[red]{message}[/red]")
            return rc
        else:
            console.print(f"[green]Python has been successfully upgraded to version {latest_version}.[/green]")
    else:
        console.print(f"[green]You already have the latest Python version: {latest_version}.[/green]")

    return 0


def _make_parser():
    import argparse
    parser = argparse.ArgumentParser(description="Python Manager for Windows.")
    parser.add_argument(
        "-i", "--install", type=str, default=None, metavar="VERSION",
        help="Install a specific Python minor version. Example: -i 3.13"
    )
    parser.add_argument(
        "-u", "--upgrade", action="store_true",
        help="Upgrade the current Python minor version to the latest micro release."
    )
    return parser


def main(
        install: str = None,
        upgrade: bool = False,
) -> int:
    if not install and not upgrade:
        console.print("[red]No method specified. Use --help for more information.[/red]")
        return 1

    if install and upgrade:
        console.print("[red]Please specify only one method at a time.[/red]")
        return 1

    if install:
        return install_function(install)

    if upgrade:
        return upgrade_function()

    return 0


# Aliases so main() can reference them without shadowing the parameter names.
install_function = install
upgrade_function = upgrade


if __name__ == '__main__':
    exec_parser = _make_parser()
    args = exec_parser.parse_args()
    sys.exit(main(**vars(args)))
