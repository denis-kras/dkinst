from pathlib import Path
from types import ModuleType
from typing import Literal

from rich.console import Console

from . import _base
from .helpers.infra import system


console = Console()


class Krusader(_base.BaseInstaller):
    def __init__(self):
        super().__init__()
        self.name: str = Path(__file__).stem
        self.description: str = "Krusader Installer"
        self.version: str = "1.0.0"
        self.platforms: list = ["debian"]
        self.helper: ModuleType | None = None

    def install(
            self,
            force: bool = False
    ):
        return install_krusader()

    def _show_help(
            self,
            method: Literal["install", "uninstall", "update"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method installs krusader and its prerequisites from apt repositories\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")


def install_krusader():
    script_lines = [
        """

# Update the package list
echo "Updating package list..."
sudo apt update

# Install Krusader
echo "Installing Krusader..."
sudo apt install -y krusader

# Install Kate to use text editor as F4
echo "Installing Kate..."
sudo apt install -y kate

# Install Konsole to use terminal through Krusader
echo "Installing Konsole..."
sudo apt install -y konsole

# Install Breeze Icon Theme so there will be isons inside Krusader on ubuntu
echo "Installing Breeze Icon Theme..."
sudo apt install -y breeze-icon-theme

# Check if Krusader is installed successfully
if command -v krusader >/dev/null 2>&1; then
    echo "Krusader installed successfully!"
else
    echo "Failed to install Krusader." >&2
fi

# Check if Kate is installed successfully
if command -v kate >/dev/null 2>&1; then
    echo "Kate installed successfully!"
else
    echo "Failed to install Kate." >&2
fi

# Check if Konsole is installed successfully
if command -v konsole >/dev/null 2>&1; then
    echo "Konsole installed successfully!"
else
    echo "Failed to install Konsole." >&2
fi

# Check if Breeze Icon Theme is installed successfully
if dpkg -l | grep breeze-icon-theme >/dev/null; then
    echo "Breeze Icon Theme installed successfully!"
else
    echo "Failed to install Breeze Icon Theme." >&2
fi

# Install multirename tool KRename.
sudo apt install krename -y
"""]

    system.execute_bash_script_string(script_lines)

    return 0