import argparse
import ctypes
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import winreg


VERSION: str = "1.0.0"
# Using both py and modifying PATH now.


@dataclass(frozen=True)
class PyInstall:
    tag: str        # e.g. "3.13" or "3.13-64"
    version: str    # e.g. "3.13"
    exe: str        # full path to python.exe


# ----------------------------
# Admin / UAC helpers
# ----------------------------

def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin(argv: List[str]) -> int:
    """
    Relaunch this script elevated (UAC prompt).
    Returns 0 if ShellExecute was invoked; does not mean the elevated process succeeded.
    """
    # Use the current interpreter to run the script elevated
    python_exe = sys.executable
    script = os.path.abspath(__file__)
    # Build command line: "<script>" <args...>
    params = " ".join([f'"{script}"'] + [f'"{a}"' for a in argv])
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", python_exe, params, None, 1)
    return 0 if rc > 32 else 1


def broadcast_env_change() -> None:
    """
    Notify the system that environment variables changed.
    This helps new processes pick it up, but does not magically update already-running shells.
    """
    HWND_BROADCAST = 0xFFFF
    WM_SETTINGCHANGE = 0x001A
    SMTO_ABORTIFHUNG = 0x0002
    SendMessageTimeoutW = ctypes.windll.user32.SendMessageTimeoutW  # type: ignore[attr-defined]
    res = ctypes.c_ulong()
    SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", SMTO_ABORTIFHUNG, 2000, ctypes.byref(res))


# ----------------------------
# PATH / Registry helpers
# ----------------------------

def norm_path(p: str) -> str:
    p = (p or "").strip().strip('"').rstrip("\\/")
    return os.path.expandvars(p).casefold()


def split_path(p: str) -> List[str]:
    return [seg for seg in (p or "").split(";") if seg.strip()]


def dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in items:
        nx = norm_path(x)
        if not nx or nx in seen:
            continue
        seen.add(nx)
        out.append(x)
    return out


def get_user_path() -> str:
    if winreg is None:
        return ""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as k:
            val, _typ = winreg.QueryValueEx(k, "Path")
            return val if isinstance(val, str) else ""
    except OSError:
        return ""


def set_user_path(new_user_path: str) -> None:
    if winreg is None:
        return
    reg_type = winreg.REG_EXPAND_SZ if "%" in new_user_path else winreg.REG_SZ
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, "Path", 0, reg_type, new_user_path)


def set_user_env_var(name: str, value: str) -> None:
    """Persist a user-level environment variable in HKCU\\Environment."""
    if winreg is None:
        return
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)


def get_system_path() -> str:
    if winreg is None:
        return ""
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ) as k:
            val, _typ = winreg.QueryValueEx(k, "Path")
            return val if isinstance(val, str) else ""
    except OSError:
        return ""


def set_system_path(new_system_path: str) -> None:
    if winreg is None:
        return
    reg_type = winreg.REG_EXPAND_SZ if "%" in new_system_path else winreg.REG_SZ
    with winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE,
        r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        0,
        winreg.KEY_SET_VALUE,
    ) as k:
        winreg.SetValueEx(k, "Path", 0, reg_type, new_system_path)


def reorder_path(original: str, installs: List[PyInstall], chosen: PyInstall) -> str:
    """
    Remove any discovered Python roots/scripts from PATH, then prepend chosen root + Scripts.
    """
    chosen_root = os.path.dirname(chosen.exe)
    chosen_scripts = os.path.join(chosen_root, "Scripts")

    strip_set = set()
    for inst in installs:
        root = os.path.dirname(inst.exe)
        strip_set.add(norm_path(root))
        strip_set.add(norm_path(os.path.join(root, "Scripts")))

    entries = split_path(original)
    entries = [e for e in entries if norm_path(e) not in strip_set]

    return ";".join(dedupe_keep_order([chosen_root, chosen_scripts] + entries))


# ----------------------------
# Discovery via py.exe
# ----------------------------

def run_py_launcher() -> List[PyInstall]:
    r"""
    Parses output like:
      -V:3.13 *        C:\Python313\python.exe
      -V:3.12          C:\Python312\python.exe
    and also older formats like:
      -3.13-64         C:\...\python.exe *
    """
    try:
        cp = subprocess.run(["py", "-0p"], capture_output=True, text=True, check=False)
    except Exception:
        return []
    if cp.returncode != 0:
        return []

    installs: List[PyInstall] = []
    for line in cp.stdout.splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        raw_tag = parts[0].lstrip("-")
        if raw_tag.startswith("V:"):
            raw_tag = raw_tag[2:]  # "V:3.13" -> "3.13"

        # Path is usually last; '*' can appear before or after it
        exe = parts[-1]
        if exe == "*" and len(parts) >= 2:
            exe = parts[-2]

        if not exe.lower().endswith("python.exe"):
            continue
        if not os.path.isfile(exe):
            continue

        version = raw_tag.split("-", 1)[0]
        installs.append(PyInstall(tag=raw_tag, version=version, exe=exe))

    # De-dupe by exe
    uniq = {norm_path(i.exe): i for i in installs}
    installs = list(uniq.values())

    def vkey(v: str) -> Tuple[int, int, str]:
        m = re.match(r"^(\d+)\.(\d+)$", v)
        return (int(m.group(1)), int(m.group(2)), v) if m else (0, 0, v)

    installs.sort(key=lambda x: (vkey(x.version), x.exe.casefold()))
    return installs


# ----------------------------
# Determining current defaults
# ----------------------------

def get_default_python_from_path(env: Optional[Dict[str, str]] = None) -> Tuple[Optional[str], List[str]]:
    """Return (first_hit, all_hits) for `python.exe` as resolved by PATH."""
    try:
        cp = subprocess.run(["where", "python"], capture_output=True, text=True, check=False, env=env)
    except Exception:
        return None, []

    hits = [ln.strip() for ln in (cp.stdout or "").splitlines() if ln.strip()]

    # Prefer an actual python.exe over wrappers (python.bat, etc.) when present.
    first = next((h for h in hits if h.casefold().endswith("python.exe")), None)
    if first is None and hits:
        first = hits[0]
    return first, hits


def get_default_python_from_py_launcher() -> Optional[str]:
    """Return the `sys.executable` path that `py` runs by default."""
    try:
        cp = subprocess.run(
            ["py", "-c", "import sys; print(sys.executable)"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None

    out = (cp.stdout or "").strip()
    return out or None


# ----------------------------
# Spawning a new shell with updated PATH
# ----------------------------

def spawn_shell(shell: str, env: dict) -> None:
    """
    Spawn a new interactive shell process with the updated environment.
    This is the only way to get "immediate effect" without wrappers.
    """
    shell = shell.lower()
    if shell == "cmd":
        subprocess.Popen(["cmd.exe", "/k", "python --version"], env=env)
        return

    if shell in ("pwsh", "powershell"):
        exe = "pwsh.exe" if shell == "pwsh" else "powershell.exe"
        # -NoExit to keep it open; show python --version immediately
        subprocess.Popen([exe, "-NoExit", "-Command", "python --version"], env=env)
        return

    raise ValueError("Unsupported shell. Use: cmd, powershell, or pwsh.")


# ----------------------------
# Main
# ----------------------------

def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("version", nargs="?", help='Version/tag to activate, e.g. "3.13"')
    ap.add_argument("--no-system", action="store_true", help="Do not modify System PATH (HKLM).")
    ap.add_argument(
        "--no-py-default",
        action="store_true",
        help="Do not set PY_PYTHON (Windows Python Launcher default).",
    )
    ap.add_argument("--spawn", action="store_true", help="Spawn a new shell with the updated PATH.")
    ap.add_argument("--shell", default="cmd", help=(
        "Shell to spawn: cmd | powershell | pwsh (used with --spawn).\n"
        "Example Switch and immediately open a new console that is guaranteed to use the new default:\n"
        "    python pyswitch.py 3.13 --spawn --shell cmd\n"
        "    python pyswitch.py 3.12 --spawn --shell powershell\n"
        "Example without updated shell (you'll need to restart your consoles to pick up the new PATH):\n"
        "    python pyswitch.py 3.13\n"
    ))
    ap.add_argument("--elevated", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    installs = run_py_launcher()
    if not installs:
        print("No Python installs discovered via 'py -0p'. Ensure Python Launcher is installed.")
        return 2

    if not args.version:
        # Show current defaults before printing the available installs.
        exe_to_install = {norm_path(i.exe): i for i in installs}

        python_default_exe, python_hits = get_default_python_from_path()
        py_default_exe = get_default_python_from_py_launcher()

        def fmt_default(exe: Optional[str]) -> str:
            if not exe:
                return "(not found)"
            inst = exe_to_install.get(norm_path(exe))
            return f"{inst.tag} -> {exe}" if inst else f"{exe} (not in py -0p list)"

        print("Current defaults:")
        print(f"  python (PATH): {fmt_default(python_default_exe)}")
        print(f"  py (launcher): {fmt_default(py_default_exe)}")
        print("\nAvailable installs (py -0p):")

        python_key = norm_path(python_default_exe) if python_default_exe else ""
        py_key = norm_path(py_default_exe) if py_default_exe else ""

        for inst in installs:
            flags: List[str] = []
            if python_key and norm_path(inst.exe) == python_key:
                flags.append("python")
            if py_key and norm_path(inst.exe) == py_key:
                flags.append("py")
            marker = f"  <== default for {', '.join(flags)}" if flags else ""
            print(f"  {inst.tag:<8} {inst.exe}{marker}")

        # If multiple python.exe are in PATH, show them explicitly (helps spot WindowsApps/store aliases).
        if len(python_hits) > 1:
            print("\nOther python.exe found in PATH (resolution order):")
            for hit in python_hits[1:]:
                print(f"  {hit}")

        return 0

    want = args.version.strip()
    matches = [i for i in installs if i.version == want or i.tag == want]
    if not matches:
        print(f'No match for "{want}". Installed:')
        for inst in installs:
            print(f"{inst.version} - {inst.exe}")
        return 1

    chosen = matches[0]

    # If user wants System PATH and we're not admin, self-elevate.
    if not args.no_system and not is_admin() and not args.elevated:
        # Relaunch elevated to apply System PATH; keep same arguments and mark elevated
        new_argv = argv + ["--elevated"]
        return relaunch_as_admin(new_argv)

    # Compute new PATH values
    new_user_path = reorder_path(get_user_path(), installs, chosen)
    set_user_path(new_user_path)

    if not args.no_system:
        new_system_path = reorder_path(get_system_path(), installs, chosen)
        set_system_path(new_system_path)

    if not args.no_py_default:
        # Make `py` default follow the selected install (persists for new processes).
        set_user_env_var("PY_PYTHON", chosen.tag)

        # Best-effort for processes we spawn from this run.
        os.environ["PY_PYTHON"] = chosen.tag

    broadcast_env_change()

    # Also compute a "best effort" current-process PATH, for spawning a shell immediately
    # (Windows Terminal may not refresh PATH for new tabs; this guarantees the spawned shell uses it.)
    merged_current = os.environ.get("PATH", "")
    new_current = reorder_path(merged_current, installs, chosen)
    os.environ["PATH"] = new_current

    print(f"Activated {chosen.version} -> {chosen.exe}")

    if not args.no_py_default:
        print(f"Set PY_PYTHON={chosen.tag} (py launcher default).")

    if args.no_system:
        print("User PATH updated (persisted).")
    else:
        print("User + System PATH updated (persisted).")

    if args.spawn:
        print(f"Launching new {args.shell} with updated PATH...")
        spawn_shell(args.shell, env=os.environ.copy())

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
