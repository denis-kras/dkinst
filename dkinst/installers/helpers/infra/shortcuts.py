import os
import subprocess


def create_desktop_shortcut(target_path: str, shortcut_name: str) -> None:
    """Create a .lnk shortcut on the user's Desktop.

    Args:
        target_path: Absolute path to the target executable/script.
        shortcut_name: Name for the shortcut (without .lnk extension).
    """

    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
    shortcut_path = os.path.join(desktop, f"{shortcut_name}.lnk")
    working_dir = os.path.dirname(target_path)

    ps_script = (
        f'$ws = New-Object -ComObject WScript.Shell; '
        f'$s = $ws.CreateShortcut("{shortcut_path}"); '
        f'$s.TargetPath = "{target_path}"; '
        f'$s.WorkingDirectory = "{working_dir}"; '
        f'$s.Save()'
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], check=True)
