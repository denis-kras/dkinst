from pathlib import Path
from types import ModuleType
from typing import Literal
import subprocess

from rich.console import Console

from . import _base
from .helpers.infra import system


console = Console()


# GIT_REPO_URL: str = "https://github.com/Vishram1123/gjs-osk"
UUID: str = "gjsosk@vishram1123.com"


class VirtualKeyboard(_base.BaseInstaller):
    def __init__(self):
        super().__init__()
        self.name: str = Path(__file__).stem
        self.description: str = "VLC Installer"
        self.version: str = "1.0.0"
        self.platforms: list = ["debian"]
        self.helper: ModuleType | None = None

    def install(
            self,
    ):
        return install_function()

    def _show_help(
            self,
            method: Literal["install", "uninstall", "update"]
    ) -> None:
        if method == "install":
            method_help: str = (
                "This method installs gnome-extensions from apt repo and then the GJS OSK extension (virtual keyboard).\n"
                "You will be prompted to click 'Install' in the GUI Extension Manager.\n"
            )
            print(method_help)
        else:
            raise ValueError(f"Unknown method '{method}'.")


def install_function():
    # Get Gnome version.
    gnome_version: str = subprocess.check_output(
        ["gnome-shell", "--version"],
        text=True
    ).strip().split(" ")[2]
    print(f"Detected Gnome version: {gnome_version}")

    # if int(gnome_version.split(".")[0]) > 45:
    #     channel: str = "main"
    # else:
    #     channel = "pre-45"
    #
    # with tempfile.TemporaryDirectory() as tmpdir:
    #     temp_dir: str = str(Path(tmpdir))
    # os.makedirs(temp_dir, exist_ok=True)
    #
    # github_wrapper: GitHubWrapper = GitHubWrapper(
    #     repo_url=GIT_REPO_URL
    # )
    #
    # downloaded_release_path: Path = github_wrapper.download_latest_release(
    #     target_directory=temp_dir,
    #     asset_pattern=f"*{channel}*"
    # )

    script_lines = [
        f"""

if [[ "${{XDG_SESSION_TYPE:-}}" != "wayland" ]]; then
  echo "NOTE: GJS OSK works best on Wayland (X11 is not supported well)."
fi

sudo apt update
sudo apt install -y gnome-shell-extension-manager curl

# gnome-extensions install --force "downloaded_release_path"
# gnome-extensions enable "$UUID" || true

gdbus call --session --dest org.gnome.Shell.Extensions --object-path /org/gnome/Shell/Extensions --method org.gnome.Shell.Extensions.InstallRemoteExtension "{UUID}"

# --- (Optional) Disable built-in GNOME OSK to avoid conflicts ---------------
# Comment out the next line if you want to keep GNOME's default OSK enabled.
# gsettings set org.gnome.desktop.a11y.applications screen-keyboard-enabled false || true
"""]

    system.execute_bash_script_string(script_lines)

    # Cleanup
    # shutil.rmtree(temp_dir)

    return 0
