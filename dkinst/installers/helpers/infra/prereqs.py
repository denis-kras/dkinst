import os
import shutil
import subprocess
from pathlib import Path
import platform
import sys
import sysconfig

from rich.console import Console


console = Console()


def _cmd_prereqs() -> int:
    """
    Register tab-completion for dkinst in the user's shell.
    Supports bash, zsh, fish, powershell. Explains cmd.exe limitations.
    """

    exe_name = "dkinst"

    # Ensure argcomplete is installed in a cross-platform way
    reg = _ensure_argcomplete()
    if not reg:
        console.print("  Reinstall argcomplete or ensure your Python scripts dir is on PATH.", style="yellow")
        return 1

    act = shutil.which("activate-global-python-argcomplete")  # optional; per-exe is fine

    # Decide which shell(s) to target
    targets = [_detect_shell()]
    for sh in targets:
        if sh == "unknown":
            # On Windows cmd.exe we can't provide programmable completion
            if os.name == "nt":
                console.print(
                    "[yellow]cmd.exe does not support programmable completions.[/]\n"
                    "Use PowerShell (recommended) or Git Bash/WSL and run:\n"
                    "  register-python-argcomplete --shell powershell dkinst | powershell -NoProfile -Command -\n",
                    markup=True
                )
                # Still try to set up PowerShell profile for future use:
                _register_powershell(reg, exe_name)
                continue
            # POSIX but couldn't detect shell: do a best-effort bash setup
            sh = "bash"

        if sh == "bash":
            _register_bash(reg, act, exe_name)
        elif sh == "zsh":
            _register_zsh(reg, act, exe_name)
        elif sh == "fish":
            _register_fish(reg, exe_name)
        elif sh == "powershell":
            _register_powershell(reg, exe_name)
        else:
            console.print(f"[red]Unsupported shell:[/] {sh}", markup=True)
            return 1

    console.print("[green]Tab-completion is set up. Open a new shell and try:[/] dkinst install v<Tab>", markup=True)
    return 0


def _ensure_argcomplete() -> str | None:
    """
    Make sure argcomplete is available and return the path to
    register-python-argcomplete. Uses apt on Debian/Ubuntu if present,
    otherwise falls back to pip (user install).
    """
    # already there?
    reg = shutil.which("register-python-argcomplete")
    if reg:
        return reg

    # Prefer apt on Linux if available (covers Debian/Ubuntu and WSL)
    if platform.system() == "Linux" and shutil.which("apt"):
        try:
            subprocess.check_call(["sudo", "apt", "update"])
            subprocess.check_call(["sudo", "apt", "install", "-y", "python3-argcomplete"])
            reg = shutil.which("register-python-argcomplete")
            if reg:
                return reg
        except Exception as e:
            console.print(f"[yellow]apt install failed ({e}); falling back to pip --user[/]", markup=True)

    # Fallback: pip in the current interpreter (no sudo; safe on Windows)
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "argcomplete"])
    except Exception as e:
        console.print(f"[red]Could not install argcomplete via pip:[/] {e}", markup=True)
        return None

    # Try again via PATH, then common script locations even if not on PATH
    reg = shutil.which("register-python-argcomplete")
    if reg:
        return reg

    scripts_dir = sysconfig.get_path("scripts") or ""
    candidates = [os.path.join(scripts_dir, "register-python-argcomplete")]
    if os.name == "nt":
        candidates.append(os.path.join(scripts_dir, "register-python-argcomplete.exe"))
    for c in candidates:
        if os.path.exists(c):
            return c

    console.print("[red]register-python-argcomplete not found even after install.[/]", markup=True)
    return None


def _detect_shell() -> str:
    """Best-effort shell detection."""
    if os.name == "nt":
        # Heuristic: prefer PowerShell if present
        # Detect typical PS env var; cmd.exe has neither $SHELL nor $PSModulePath normally
        if os.environ.get("PSModulePath"):
            return "powershell"
        return "unknown"  # likely cmd.exe
    shell = os.environ.get("SHELL", "")
    for sh in ("bash", "zsh", "fish"):
        if shell.endswith(sh):
            return sh
    return "bash" if shell else "unknown"


def _append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if line.strip() not in existing:
        with path.open("a", encoding="utf-8") as fh:
            fh.write("\n" + line.rstrip() + "\n")


def _register_bash(reg_cmd: str, act_cmd: str | None, exe: str) -> None:
    # Per-executable registration (safe & local)
    rc = Path.home() / ".bashrc"
    eval_line = f'eval "$({os.path.basename(reg_cmd)} {exe})"'

    _append_line(rc, eval_line)
    console.print(f"Updated [bold]{rc}[/] for bash.", markup=True)


def _register_zsh(reg_cmd: str, act_cmd: str | None, exe: str) -> None:
    rc = Path.home() / ".zshrc"
    lines = [
        "autoload -U bashcompinit && bashcompinit",
        f'eval "$({os.path.basename(reg_cmd)} --shell zsh {exe})"',
    ]

    for ln in lines:
        _append_line(rc, ln)
    console.print(f"Updated [bold]{rc}[/] for zsh.", markup=True)


def _register_fish(reg_cmd: str, exe: str) -> None:
    comp_dir = Path.home() / ".config" / "fish" / "completions"
    comp_dir.mkdir(parents=True, exist_ok=True)
    out_file = comp_dir / f"{exe}.fish"
    # Write generated fish completion script
    completed = subprocess.check_output([reg_cmd, "--shell", "fish", exe], text=True)
    out_file.write_text(completed, encoding="utf-8")
    console.print(f"Wrote fish completions to [bold]{out_file}[/].", markup=True)


def _register_powershell(reg_cmd: str, exe: str) -> None:
    """
    Register a PowerShell ArgumentCompleter by appending to the user's PS profile.
    """
    # Determine the profile path by asking PowerShell
    try:
        profile = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", "$PROFILE"],
            text=True
        ).strip()
    except Exception as e:
        console.print(f"[red]Failed to determine PowerShell profile path:[/] {e}", markup=True)
        print("Falling back to default locations.")
        # Fallback locations (PS 7+ and Windows PowerShell 5.1)
        docs = Path.home() / "Documents"
        profile = str(docs / "PowerShell" / "Microsoft.PowerShell_profile.ps1")
        legacy = docs / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1"
        # Prefer modern path but create legacy too if it exists already
        if legacy.exists():
            profile = str(legacy)

    prof_path = Path(profile)
    prof_path.parent.mkdir(parents=True, exist_ok=True)
    # Generate the completer code and append
    ps_code = subprocess.check_output(
        [reg_cmd, "--shell", "powershell", exe],
        text=True
    )
    line = ps_code.strip()

    _append_line(prof_path, line)
    console.print(f"Updated PowerShell profile [bold]{prof_path}[/].", markup=True)
