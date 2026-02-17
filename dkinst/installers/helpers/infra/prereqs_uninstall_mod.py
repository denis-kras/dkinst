import re
import os
import subprocess
from pathlib import Path
import shutil


from rich.console import Console

from . import prereqs_mod, pips


console = Console()


def _cmd_uninstall_prereqs() -> int:
    """
    Unregister tab-completion for dkinst from the user's shell.
    Mirrors _cmd_prereqs targets and behavior (bash, zsh, fish, powershell).
    """
    exe_name = "dkinst"

    targets = [prereqs_mod._detect_shell()]
    for sh in targets:
        if sh == "unknown":
            if os.name == "nt":
                # Likely cmd.exe; we set up PowerShell during install, so remove there.
                _unregister_powershell(exe_name)
                continue
            # POSIX but unknown -> best-effort bash cleanup
            sh = "bash"

        if sh == "bash":
            _unregister_bash(exe_name)
        elif sh == "zsh":
            _unregister_zsh(exe_name)
        elif sh == "fish":
            _unregister_fish(exe_name)
        elif sh == "powershell":
            _unregister_powershell(exe_name)
        else:
            console.print(f"[red]Unsupported shell:[/] {sh}", markup=True)
            return 1

    rc = pips.pip_uninstall(prereqs_mod.PIP_ARGCOMPLETE)
    if rc != 0:
        console.print(f"[yellow]Failed to uninstall argcomplete (pip exit {rc}).[/]", markup=True)
        return rc

    console.print("[green]Tab-completion for dkinst has been removed.[/]", markup=True)
    return 0


# Helpers for safe line/file removal

def _remove_lines_containing(path: Path, *needles: str) -> bool:
    """
    Remove any line from 'path' that contains ALL 'needles' substrings.
    Returns True if the file was modified.
    """
    if not path.exists():
        return False
    changed = False
    with path.open("r", encoding="utf-8") as fh:
        lines = fh.readlines()
    kept = []
    for ln in lines:
        if all(n in ln for n in needles):
            changed = True
            continue
        kept.append(ln)
    if changed:
        with path.open("w", encoding="utf-8") as fh:
            fh.writelines(kept)
    return changed


def _remove_line_equal(path: Path, exact_line: str) -> bool:
    """
    Remove a line that exactly matches 'exact_line' (ignoring trailing whitespace).
    Returns True if the file was modified.
    """
    if not path.exists():
        return False
    changed = False
    with path.open("r", encoding="utf-8") as fh:
        lines = fh.readlines()
    kept = []
    tgt = exact_line.rstrip()
    for ln in lines:
        if ln.rstrip() == tgt:
            changed = True
            continue
        kept.append(ln)
    if changed:
        with path.open("w", encoding="utf-8") as fh:
            fh.writelines(kept)
    return changed


# Per-shell uninstallers

def _unregister_bash(exe: str) -> None:
    rc = Path.home() / ".bashrc"
    changed = _remove_lines_containing(rc, "register-python-argcomplete", exe)
    if changed:
        console.print(f"Reverted [bold]{rc}[/] for bash.", markup=True)
    else:
        console.print(f"No dkinst completion lines found in [bold]{rc}[/].", markup=True)


def _unregister_zsh(exe: str) -> None:
    rc = Path.home() / ".zshrc"
    # Only remove the line we added for dkinst; leave generic bashcompinit alone.
    changed = _remove_lines_containing(rc, "register-python-argcomplete", exe)
    if changed:
        console.print(f"Reverted [bold]{rc}[/] for zsh.", markup=True)
    else:
        console.print(f"No dkinst completion lines found in [bold]{rc}[/].", markup=True)


def _unregister_fish(exe: str) -> None:
    comp_file = Path.home() / ".config" / "fish" / "completions" / f"{exe}.fish"
    if comp_file.exists():
        try:
            comp_file.unlink()
            console.print(f"Removed fish completions [bold]{comp_file}[/].", markup=True)
        except Exception as e:
            console.print(f"[red]Failed to remove fish completions:[/] {e}", markup=True)
    else:
        console.print(f"Fish completions file not found: [bold]{comp_file}[/].", markup=True)


def _unregister_powershell(exe: str) -> None:
    """
    Remove the Register-ArgumentCompleter block for `exe` from all detected PS hosts:
    - PowerShell 7+ (pwsh)
    - Windows PowerShell 5.1 (powershell)

    Deletes the whole -ScriptBlock {...} including nested braces.
    """
    hosts = []
    if shutil.which("pwsh"):
        hosts.append("pwsh")
    if shutil.which("powershell"):
        hosts.append("powershell")

    if not hosts:
        console.print("[yellow]No PowerShell hosts found on PATH (pwsh/powershell). Skipping.[/]", markup=True)
        return

    any_changed = False
    for host in hosts:
        try:
            profile = subprocess.check_output(
                [host, "-NoProfile", "-Command", "$PROFILE"], text=True
            ).strip()
        except Exception as e:
            console.print(f"[red]Failed to determine {host} profile:[/] {e}", markup=True)
            continue

        prof_path = Path(profile)
        # Do not create missing profiles here; if it doesn't exist, nothing to remove.
        if not prof_path.exists():
            console.print(f"{host}: profile not found at [bold]{prof_path}[/]. Nothing to remove.", markup=True)
            continue

        changed = _remove_ps_register_block(prof_path, exe)
        if changed:
            any_changed = True
            console.print(
                f"Updated {host} profile [bold]{prof_path}[/] (removed {exe} completer).",
                markup=True,
            )

            if _remove_if_blank(str(prof_path)):
                console.print(f"Profile [bold]{prof_path}[/] was empty and has been deleted.", markup=True)
        else:
            console.print(
                f"No {exe} Register-ArgumentCompleter block found in {host} profile [bold]{prof_path}[/].",
                markup=True,
            )

    if not any_changed:
        console.print("[yellow]No PowerShell completion blocks needed removal.[/]", markup=True)


def _remove_if_blank(path: str) -> bool:
    """
    Delete file if it contains only whitespace (or is empty).
    Returns True if removed.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for chunk in iter(lambda: f.read(8192), ""):
                if chunk.strip():  # found non-whitespace
                    return False
        # got here => empty or whitespace-only
        from pathlib import Path
        Path(path).unlink()
        return True
    except FileNotFoundError:
        return False
    except PermissionError as e:
        print(f"Permission denied: {e}")
        return False


def _remove_ps_register_block(path: Path, exe: str) -> bool:
    """
    Locate and remove:
        Register-ArgumentCompleter ... -CommandName <exe> ... -ScriptBlock { ... }
    Removes the ENTIRE scriptblock, handling nested braces and quotes.

    Returns True if the file was modified.
    """
    with path.open("r", encoding="utf-8") as fh:
        lines = fh.readlines()

    # Match a start line that mentions Register-ArgumentCompleter and our exe (quoted or not), case-insensitive.
    start_line_re = re.compile(
        rf"(?i)^\s*Register-ArgumentCompleter\b.*?-CommandName\s+(?:['\"])?{re.escape(exe)}(?:['\"])?"
    )

    i = 0
    changed = False
    while i < len(lines):
        if start_line_re.search(lines[i]):
            start_idx = i
            end_idx = _find_closing_brace_index(lines, i)
            if end_idx is None:
                # Can't confidently find the closing '}' — skip to avoid corrupting the profile.
                i += 1
                continue

            # Remove the full block [start_idx, end_idx], inclusive.
            del lines[start_idx:end_idx + 1]

            # Tidy: drop a single trailing blank line that block removal might leave behind.
            if start_idx < len(lines) and not lines[start_idx].strip():
                del lines[start_idx:start_idx + 1]

            changed = True
            # Continue scanning from same index for any additional blocks.
            continue
        i += 1

    if changed:
        with path.open("w", encoding="utf-8") as fh:
            fh.writelines(lines)

    return changed


def _find_closing_brace_index(lines, start_from):
    """
    Starting at the Register-ArgumentCompleter line, find the matching closing '}' for
    the *outer* -ScriptBlock. Counts { and } outside of quotes and supports nested blocks.
    PowerShell escaping with backtick ` is honored for quotes.
    """
    in_single = False
    in_double = False
    started = False
    depth = 0

    for idx in range(start_from, len(lines)):
        s = lines[idx]
        j = 0
        while j < len(s):
            ch = s[j]
            prev = s[j - 1] if j > 0 else ""

            # Toggle quote states (PowerShell uses backtick to escape quotes)
            if ch == "'" and not in_double and prev != "`":
                in_single = not in_single
            elif ch == '"' and not in_single and prev != "`":
                in_double = not in_double
            elif not in_single and not in_double:
                if ch == "{":
                    started = True
                    depth += 1
                elif ch == "}":
                    if started:
                        depth -= 1
                        if depth == 0:
                            return idx
            j += 1

    return None
