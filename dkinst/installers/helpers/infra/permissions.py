import os
import ctypes
import shutil
import sys
import subprocess

from rich.console import Console


console = Console()


def is_admin() -> bool:
    """
    Function checks on Windows or POSIX OSes if the script is executed under Administrative Privileges.
    :return: True / False.
    """

    if os.name == 'nt':
        if ctypes.windll.shell32.IsUserAnAdmin() == 0:
            result = False
        else:
            result = True
    else:
        if 'SUDO_USER' in os.environ and os.geteuid() == 0:
            result = True
        else:
            result = False

    return result


def ensure_root_or_reexec_debian() -> None:
    """If not root, re-exec this command under sudo, preserving args."""
    if os.geteuid() == 0:
        return  # already root
    exe = shutil.which("dkinst") or sys.argv[0]
    # make it absolute in case it was found via PATH
    exe = os.path.abspath(exe)
    # Replace the current process with: sudo <same dkinst> <same args>
    os.execvp("sudo", ["sudo", "-E", exe] + sys.argv[1:])


def ensure_admin_or_reexec_windows() -> None:
    """
    On Windows, relaunch this command with elevation (UAC),
    preserving the original arguments, and end with a 'pause'
    so the new console window doesn't close immediately.
    """
    if os.name != "nt":
        return

    # Original dkinst entry point (same logic as before)
    orig_exe = shutil.which("dkinst") or sys.argv[0]
    orig_exe = os.path.abspath(orig_exe)

    # Build the argument string for dkinst
    orig_params = subprocess.list2cmdline(sys.argv[1:])

    # Build the inner command:
    #   dkinst <args> & pause
    if orig_params:
        inner_cmd = f'"{orig_exe}" {orig_params} & pause'
    else:
        inner_cmd = f'"{orig_exe}" & pause'

    # Run it via the command interpreter so & pause works
    cmd_exe = os.environ.get("COMSPEC", "cmd.exe")
    cmd_params = f'/c {inner_cmd}'

    try:
        ShellExecuteW = ctypes.windll.shell32.ShellExecuteW
    except AttributeError:
        console.print(
            "Cannot request elevation via ShellExecuteW on this system. "
            "Please rerun this command from an elevated terminal.",
            style="red",
        )
        return

    # lpVerb="runas" => UAC prompt
    rc = ShellExecuteW(
        None,           # hwnd
        "runas",        # lpVerb
        cmd_exe,        # lpFile (cmd.exe)
        cmd_params,     # lpParameters: /c "dkinst ..." & pause
        None,           # lpDirectory
        1,              # nShowCmd (normal window)
    )

    if rc <= 32:
        console.print(
            f"Elevation request was rejected or failed (code {rc}). "
            "Please rerun this command from an elevated PowerShell or CMD.",
            style="red",
        )
        return

    # Elevated process has been started; exit the current one
    sys.exit(0)