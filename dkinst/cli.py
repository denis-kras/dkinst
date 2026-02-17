"""Command-line driver for dkinst."""
import sys
import pkgutil
from importlib import import_module
import argparse
from pathlib import Path
import subprocess
import os
from typing import Literal
import shlex
import json
import tempfile
import time

from rich.console import Console
from rich.table import Table
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion

try:
    import argcomplete
except ImportError:  # pragma: no cover
    argcomplete = None

from . import __version__
from .installers._base import BaseInstaller
from .installers import _base
from . import installers
from .installers.helpers.infra import system, permissions, folders


console = Console()


VERSION: str = __version__

_ELEVATE_BOOTSTRAP_ENV = "DKINST_ELEVATE_BOOTSTRAP_ARGV"
_ELEVATE_BOOTSTRAP_FILE = str(Path(tempfile.gettempdir()) / "dkinst_elevate_bootstrap.json")
_ELEVATE_BOOTSTRAP_FILE_MAX_AGE_SEC = 10 * 60


# Short aliases for top-level commands
COMMAND_ALIASES: dict[str, str] = {
    "i": "install",
    "up": "upgrade",
    "un": "uninstall",
    "m": "manual",
    "a": "available",
    "h": "help",
}


def _write_elevate_bootstrap(argv: list[str]) -> None:
    """Best-effort: persist bootstrap argv for an elevated re-exec on Windows.

    We prefer env var bootstrap, but UAC relaunch paths don't always inherit the
    parent process environment. A temp-file fallback makes the bootstrap robust.
    """
    try:
        payload = {"ts": time.time(), "argv": argv}
        Path(_ELEVATE_BOOTSTRAP_FILE).write_text(json.dumps(payload), encoding="utf-8")
    except Exception:
        # Best-effort only.
        pass


def _pop_elevate_bootstrap() -> list[str] | None:
    """Pop a bootstrap argv for interactive-mode startup.

    Sources (in priority order):
      1) env var (fast path)
      2) temp-file fallback (robust across UAC relaunch mechanisms)
    """
    # Fast path: env var bootstrap.
    bootstrap_raw = os.environ.pop(_ELEVATE_BOOTSTRAP_ENV, None)
    if bootstrap_raw:
        try:
            argv = json.loads(bootstrap_raw)
            if (
                    isinstance(argv, list)
                    and all(isinstance(x, str) for x in argv)
            ):
                return argv
            raise ValueError("bootstrap argv must be a list[str]")
        except Exception:
            console.print(
                f"Invalid {_ELEVATE_BOOTSTRAP_ENV} value; ignoring.",
                style="yellow",
                markup=False,
            )

    # Fallback: temp file (Windows-only to avoid surprises on other platforms).
    if system.get_platform() != "windows":
        return None

    p = Path(_ELEVATE_BOOTSTRAP_FILE)
    if not p.exists():
        return None

    try:
        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception:
        # Don't keep retrying a corrupt file.
        try:
            p.unlink()
        except Exception:
            pass
        return None
    finally:
        # One-shot semantics: delete after read attempt.
        try:
            p.unlink()
        except Exception:
            pass

    # Accept both legacy "list[str]" and the newer dict payload.
    if isinstance(data, list) and all(isinstance(x, str) for x in data):
        return data

    if isinstance(data, dict):
        ts = data.get("ts", None)
        argv = data.get("argv", None)
        if isinstance(ts, (int, float)):
            if (time.time() - float(ts)) > _ELEVATE_BOOTSTRAP_FILE_MAX_AGE_SEC:
                return None
        if isinstance(argv, list) and all(isinstance(x, str) for x in argv):
            return argv

    return None


def _normalize_argv(argv: list[str]) -> list[str]:
    """
    Map short aliases (i, up, un, a) to their full subcommand names.

    Examples:
      dkinst i foo        -> dkinst install foo
      dkinst up foo       -> dkinst upgrade foo
      dkinst un foo       -> dkinst uninstall foo
      dkinst a            -> dkinst available
    """
    if argv and argv[0] in COMMAND_ALIASES:
        argv = [COMMAND_ALIASES[argv[0]]] + argv[1:]
    return argv


class DkinstCompleter(Completer):
    def __init__(self, subcommands: list[str], installer_names: list[str]):
        self.subcommands = subcommands
        self.installer_names = installer_names

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        stripped = text.strip()
        if not stripped:
            token_index = 0
            prefix = ""
            first_word = ""
        else:
            parts = stripped.split()
            if text.endswith(" "):
                token_index = len(parts)
                prefix = ""
            else:
                token_index = len(parts) - 1
                prefix = parts[-1]
            first_word = parts[0] if parts else ""

        # Treat aliases (i, up, un, m, a, h) as their full commands
        normalized_first = COMMAND_ALIASES.get(first_word, first_word)

        candidates: list[str] = []

        if token_index == 0:
            # Completing the first word: include both full commands and aliases
            all_cmds = list(self.subcommands) + list(COMMAND_ALIASES.keys())
            candidates = [cmd for cmd in all_cmds if cmd.startswith(prefix)]

        elif token_index == 1 and normalized_first in _base.ALL_METHODS:
            # Completing the second word after install/upgrade/uninstall/manual
            candidates = [name for name in self.installer_names if name.startswith(prefix)]

        for cand in candidates:
            # Replace just the current word (prefix) with the full candidate
            yield Completion(cand, start_position=-len(prefix))


def _installer_name_completer(prefix, parsed_args, **kwargs):
    """
    Return installer names that start with what's already typed.
    Enables: `dkinst install v<Tab>` -> `virtual_keyboard`.
    """
    names = [i.name for i in _get_installers()]
    return [n for n in names if n.startswith(prefix)]


def _available_scope_or_prefix_completer(prefix, parsed_args, **kwargs):
    """
    Completion for `dkinst available ...`.
    Supports both: `all` and installer name prefixes.
    """
    candidates = ["all"] + [i.name for i in _get_installers()]
    return [c for c in candidates if c.startswith(prefix)]


def _get_installers() -> list[BaseInstaller]:
    """get list of tuples (name, instance) for every subclass found in dkinst.installers.*"""
    # import every *.py file so its classes are defined
    for _, stem_name, _ in pkgutil.iter_modules(installers.__path__):
        module_string: str = f"{installers.__name__}.{stem_name}"
        import_module(module_string)

    # collect subclasses
    installers_list: list[BaseInstaller] = []
    for subclass in BaseInstaller.__subclasses__():
        if subclass is not BaseInstaller:
            installer = subclass()
            installers_list.append(installer)

    return installers_list


def cmd_available(
        prefix: str | None = None,
        show_all: bool = False
) -> None:
    """List known installers with metadata.

    By default, only installers that support the current platform are shown.
    Pass show_all=True to list installers for all platforms.

    If `prefix` is provided, only installers whose name starts with that prefix
    (case-insensitive) are shown.
    """
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Name", style="bold")
    table.add_column("Platforms")
    table.add_column("Methods")
    table.add_column("Manual Arguments")

    installers_list: list[BaseInstaller] = _get_installers()

    # Ensure platforms are initialized before filtering/printing
    for inst in installers_list:
        inst._platforms_known()

    if not show_all:
        current_platform = system.get_platform()
        installers_list = [
            inst for inst in installers_list
            if current_platform in inst.platforms
        ]

    if prefix:
        p = prefix.lower()
        installers_list = [
            inst for inst in installers_list
            if inst.name.lower().startswith(p)
        ]

    for installer in installers_list:
        methods = _base.get_known_methods(installer)
        manual_args = _base._extract_helper_args(installer, methods)
        table.add_row(
            installer.name,
            ", ".join(installer.platforms) or "—",
            ", ".join(methods) or "—",
            ", ".join(manual_args) or "—",
        )

    console.print(table)


def _run_dependencies(
    installer: BaseInstaller,
    installers_map: dict[str, BaseInstaller],
    method: Literal["install", "uninstall", "upgrade"] = "install",
    done: set[str] | None = None,
    stack: list[str] | None = None,
    top_level_reexec_argv: list[str] | None = None,
) -> tuple[int, set[str]]:
    """
    Recursively resolve `installer.dependencies` (list of installer names or
    installer objects) before running `installer` itself.

    Behaviour by top-level method
    -----------------------------
    * install: dependencies use their 'install' method (no-op if already installed)
    * upgrade: dependencies use 'upgrade' if installed, otherwise 'install'
    * uninstall: dependencies are ignored

    :param installer: The installer whose dependencies to install.
    :param installers_map: A map of installer name -> installer instance.
    :param method: The method for which dependencies are being resolved.
    :param done: Set of already installed dependency names.
    :param stack: Current dependency resolution stack (for circular dep detection).
    :param top_level_reexec_argv: If provided, the original argv of the top-level command that triggered this resolution.
        This is used for re-execing with elevated privileges on platforms that require it.

    :return: (return code, set of installed dependency names)
    """
    done = done or set()
    stack = stack or []

    # We never cascade uninstalls to dependencies.
    if method == "uninstall":
        return 0, done

    deps = getattr(installer, "dependencies", []) or []
    for dep in deps:
        # Accept either a name ("brew") or an installer instance/class with .name
        dep_name = dep if isinstance(dep, str) else getattr(dep, "name", str(dep))

        if dep_name in done:
            continue
        if dep_name in stack:
            console.print(
                f"Detected circular dependency: {' -> '.join(stack + [dep_name])}",
                style="red", markup=False
            )
            return 1, done

        dep_inst = installers_map.get(dep_name)
        if dep_inst is None:
            console.print(
                f"Dependency [{dep_name}] referenced by [{installer.name}] was not found.",
                style="red", markup=False
            )
            return 1, done

        # Platform check for the dependency
        dep_inst._platforms_known()
        current_platform = system.get_platform()
        if current_platform not in dep_inst.platforms:
            console.print(
                f"Dependency [{dep_name}] does not support your platform [{current_platform}].",
                style="red", markup=False
            )
            return 1, done

        is_installed = dep_inst.is_installed()
        known_methods: list[str] = _base.get_known_methods(dep_inst)

        # Work out which method we actually want to call on this dependency.
        if method == "install":
            # For install we only need the dependency to exist; if it's
            # already installed we leave it alone.
            if is_installed:
                console.print(
                    f"Dependency [{dep_name}] is already installed. Skipping.",
                    style="cyan",
                    markup=False,
                )
                done.add(dep_name)
                continue

            if "install" not in known_methods:
                console.print(
                    f"Dependency [{dep_name}] has no 'install' method.",
                    style="red",
                    markup=False,
                )
                return 1, done

            dep_method_name: Literal["install", "uninstall", "upgrade"] = "install"

        elif method == "upgrade":
            # On upgrade:
            #   * if the dependency is installed, prefer its 'upgrade' method
            #     and fall back to 'install' if needed.
            #   * if the dependency is NOT installed, use 'instal'`.
            if is_installed:
                if "upgrade" in known_methods:
                    dep_method_name = "upgrade"
                else:
                    console.print(
                        f"Dependency [{dep_name}] doesn't have 'upgrade' method.",
                        style="red",
                        markup=False,
                    )
                    return 1, done
            else:
                # Not installed: install instead of upgrade.
                if "install" not in known_methods:
                    console.print(
                        f"Dependency [{dep_name}] is not installed and has no 'install' method.",
                        style="red",
                        markup=False,
                    )
                    return 1, done
                dep_method_name = "install"
        else:
            # Shouldn't happen because we early-return for "uninstall"
            continue

        # Admin check for the dependency if required on this platform.
        reexec = top_level_reexec_argv or [dep_method_name, dep_inst.name]
        rc = _require_admin_if_needed(dep_inst, method=dep_method_name, reexec_argv=reexec)
        if rc != 0:
            return rc, done

        # Recurse first so deep deps resolve in correct order. We keep passing
        # the *top-level* method ("install"/"upgrade") so all transitive
        # dependencies follow the same policy.
        rc, _ = _run_dependencies(
            dep_inst, installers_map, method, done, stack + [dep_name],
            top_level_reexec_argv=top_level_reexec_argv)
        if rc != 0:
            return rc, done

        # Finally, actually run the chosen method on the dependency
        verb = (
            "Installing"
            if dep_method_name == "install"
            else "Upgrading"
            if dep_method_name == "upgrade"
            else f"Running '{dep_method_name}' for"
        )
        console.print(
            f"{verb} dependency [{dep_name}] for [{installer.name}]…",
            style="green",
            markup=False,
        )

        dep_func = getattr(dep_inst, dep_method_name)
        result = dep_func()

        # Support installers that return either an int rc or a subprocess.CompletedProcess-like object.
        rc = getattr(result, "returncode", result)
        if rc is None:
            console.print(
                f"Dependency [{dep_name}] command did not return an exit code.",
                style="red",
                markup=False,
            )
            return 1, done
        if not isinstance(rc, int):
            console.print(
                f"Dependency [{dep_name}] command returned invalid exit code: {rc!r}",
                style="red",
                markup=False,
            )
            return 1, done
        if rc != 0:
            console.print(
                f"Dependency [{dep_name}] Command failed with exit code {rc}. Exiting.",
                style="red",
                markup=False,
            )
            return rc, done

        done.add(dep_name)

    return 0, done


def _require_admin_if_needed(
        installer: BaseInstaller,
        method: Literal["install", "uninstall", "upgrade"] = "install",
        reexec_argv: list[str] | None = None,
) -> int:
    """
    Enforce admin privileges when requested by the installer.

    If we need to elevate on Windows while currently running with no CLI args
    (interactive mode), we stash the attempted argv in an env var so the elevated
    session can execute it automatically before entering interactive mode.

    installer.admins can be:

      - A dict mapping platform -> list of methods that require admin.
        Example:
            {
                "windows": ["install", "upgrade"],
                "debian": ["install"],
            }

      - (Legacy) a list of platforms, meaning all methods require admin on
        those platforms.

    Returns 0 if ok; non-zero to abort.
    """
    admins = getattr(installer, 'admins', None)
    if not admins:
        return 0

    current_platform = system.get_platform()
    needs_admin = False

    if isinstance(admins, dict):
        methods_for_platform = admins.get(current_platform) or []
        # Allow either string or list
        if isinstance(methods_for_platform, str):
            methods_for_platform = [methods_for_platform]
        methods_for_platform = [m.lower() for m in methods_for_platform]

        if str(method).lower() in methods_for_platform:
            needs_admin = True
    else:
        raise ValueError(f"installer.admins has unsupported type: {type(admins)}")

    if not needs_admin:
        return 0

    # If we require admin but already have it, we're fine
    if permissions.is_admin():
        return 0

    console.print('This action requires administrator privileges. Upgrading...', style='yellow')

    if current_platform == 'debian':
        # Auto-elevate; this never returns on success
        permissions.ensure_root_or_reexec_debian()

        # If we get here, sudo failed
        venv = os.environ.get('VIRTUAL_ENV', None)
        if venv:
            print(f'Try: sudo "{venv}/bin/dkinst" {method} {installer.name}')
    elif current_platform == 'windows':
        # If we're about to re-launch into an elevated *interactive* session (no args),
        # bootstrap it by telling the elevated process what to run first.
        if reexec_argv and (len(sys.argv) <= 1) and _ELEVATE_BOOTSTRAP_ENV not in os.environ:
            try:
                os.environ[_ELEVATE_BOOTSTRAP_ENV] = json.dumps(reexec_argv)
            except Exception:
                pass

        if reexec_argv and (len(sys.argv) <= 1):
            _write_elevate_bootstrap(reexec_argv)

        print("Will try to relaunch with elevated privileges...")
        # Auto-elevate via UAC; this will exit on success
        permissions.ensure_admin_or_reexec_windows()

        # If we get here, elevation failed or was cancelled. Clean up any bootstrap file
        # so a later elevated interactive start doesn't accidentally replay it.
        try:
            Path(_ELEVATE_BOOTSTRAP_FILE).unlink()
        except Exception:
            pass

        # If we get here, elevation failed or was cancelled
        console.print(
            "You can also rerun this command from an elevated PowerShell or CMD.",
            style='yellow',
        )

    # If we’re still here, elevation failed or was cancelled
    return 1


def _get_subcommands_from_parser(parser: argparse.ArgumentParser) -> list[str]:
    """
    Return the list of top-level subcommand names from an argparse parser.
    """
    for action in parser._actions:
        # _SubParsersAction is the thing created by add_subparsers()
        if isinstance(action, argparse._SubParsersAction):
            return list(action.choices.keys())
    return []


def _interactive_console(parser: argparse.ArgumentParser) -> int:
    installers_list = _get_installers()
    installer_names = [i.name for i in installers_list]

    # Dynamically grab all subcommand names from the parser
    subcommands: list[str] = _get_subcommands_from_parser(parser)

    console.print(
        f"[bold cyan]dkinst v{VERSION}[/bold cyan]\n"
        "[bold green]Entering dkinst interactive console.[/bold green]\n"
        "Type 'help' to see top-level usage, or 'exit' / 'quit' / Ctrl+C to leave.\n"
    )

    if PromptSession is not None:
        session = PromptSession(
            completer=DkinstCompleter(subcommands, installer_names),
            complete_while_typing=False,  # or True if you like
        )

        while True:
            try:
                # Note: prompt_toolkit handles TAB completion here
                line = session.prompt("dkinst> ")
            except (EOFError, KeyboardInterrupt):
                console.print()
                break

            line = line.strip()
            if not line:
                continue

            if line in {"exit", "quit"}:
                break

            try:
                argv = shlex.split(line)
            except ValueError as e:
                console.print(f"[red]Parse error:[/red] {e}")
                continue

            argv = _normalize_argv(argv)

            try:
                namespace = parser.parse_args(argv)
            except SystemExit:
                continue

            rc = _dispatch(namespace, parser)
            if rc is None:
                console.print(
                    "Internal error: command did not return an exit code.",
                    style="red",
                    markup=False,
                )
                return 1
            if not isinstance(rc, int):
                console.print(
                    f"Internal error: command returned invalid exit code: {rc!r}",
                    style="red",
                    markup=False,
                )
                return 1
            if rc != 0:
                console.print(
                    f"Command failed with exit code {rc}. Exiting.",
                    style="red",
                    markup=False,
                )
                return rc
    else:
        # Fallback: no prompt_toolkit installed, just a plain prompt
        console.print(
            "[yellow]prompt_toolkit not installed; TAB completion is disabled.[/yellow]"
        )
        while True:
            try:
                line = console.input("[bold magenta]dkinst> [/bold magenta]").strip()
            except (EOFError, KeyboardInterrupt):
                console.print()
                break

            if not line:
                continue

            if line in {"exit", "quit"}:
                break

            try:
                argv = shlex.split(line)
            except ValueError as e:
                console.print(f"[red]Parse error:[/red] {e}")
                continue

            argv = _normalize_argv(argv)

            try:
                namespace = parser.parse_args(argv)
            except SystemExit:
                continue

            rc = _dispatch(namespace, parser)
            if rc is None:
                console.print(
                    "Internal error: command did not return an exit code.",
                    style="red",
                    markup=False,
                )
                return 1
            if not isinstance(rc, int):
                console.print(
                    f"Internal error: command returned invalid exit code: {rc!r}",
                    style="red",
                    markup=False,
                )
                return 1
            if rc != 0:
                console.print(
                    f"Command failed with exit code {rc}. Exiting.",
                    style="red",
                    markup=False,
                )
                return rc

    console.print("[bold]Bye![/bold]")
    return 0


def _dispatch(
        namespace: argparse.Namespace,
        parser: argparse.ArgumentParser
) -> int:
    if namespace.sub == "help":
        parser.print_help()
        return 0

    if namespace.sub == "available":
        scope_or_prefix = getattr(namespace, "scope_or_prefix", None)

        show_all = False
        prefix = None

        if scope_or_prefix:
            if str(scope_or_prefix).lower() == "all":
                show_all = True
            else:
                prefix = scope_or_prefix

        cmd_available(prefix=prefix, show_all=show_all)
        return 0

    if namespace.sub == "edit-config":
        config_path: str = str(Path(__file__).parent / "config.toml")
        subprocess.run(["notepad", config_path])
        return 0

    if namespace.sub == "prereqs":
        from .installers.helpers.infra import prereqs_mod
        return prereqs_mod._cmd_prereqs()

    if namespace.sub == "prereqs-uninstall":
        from .installers.helpers.infra import prereqs_uninstall
        return prereqs_uninstall_mod._cmd_uninstall_prereqs()

    # Methods from the Known Methods list
    if namespace.sub in _base.ALL_METHODS:
        method: Literal["install", "uninstall", "upgrade"] = namespace.sub

        # No script provided OR explicitly asked for help
        if namespace.script is None or namespace.script == "help":
            BaseInstaller._show_help(method)
            return 0

        # From here on, a specific installer was provided
        installer_name: str = namespace.script
        extras: list = namespace.installer_args or []

        # Build a single map of installer instances so dependency resolution
        # uses the same instances.
        installers_list: list = _get_installers()
        installers_map: dict = {i.name: i for i in installers_list}

        for inst in installers_list:
            # Find the provided installer.
            if inst.name != installer_name:
                continue

            inst._platforms_known()

            # Now check if the current platform is supported by this installer.
            current_platform = system.get_platform()
            if current_platform not in inst.platforms:
                console.print(f"This installer [{inst.name}] does not support your platform [{current_platform}].",
                              style='red', markup=False)
                return 1

            # Enforce admin privileges for this method when requested, unless the user is just asking for help.
            if 'help' not in extras:
                attempted_argv = [str(method), inst.name, *extras]
                rc = _require_admin_if_needed(inst, method, reexec_argv=attempted_argv)
                if rc != 0:
                    return rc

            # Processing the 'manual' method.
            if method == 'manual':
                installer_methods = _base.get_known_methods(inst)
                if 'manual' not in installer_methods:
                    console.print(f"No 'manual' method available for the installer: [{inst.name}]", style='red',
                                  markup=False)
                    return 1

                # Use the helper parser for this installer, if available
                helper_parser = _base._get_helper_parser(inst, installer_methods)
                if helper_parser is None:
                    console.print(f"No manual argparser available for [{inst.name}].", style='red', markup=False)
                    return 1

                # Change the command line program name to include the installer name.
                helper_parser.prog = f"{helper_parser.prog} {method} {inst.name}"

                # Output help of specific installer helper parser
                if (
                        # Installer-specific help: [dkinst <method> <installer> help]
                        len(extras) == 1 and extras[0] == "help"
                ) or (
                        # Manual installer execution without arguments: dkinst manual <installer>
                        # show helper parser help if available.
                        len(extras) == 0
                ):
                    helper_parser.print_help()
                    return 0

                # Regular arguments execution of the manual method.
                # Parse just the extras, not the whole argv
                try:
                    parsed = helper_parser.parse_args(extras)
                except SystemExit:
                    # argparse already printed usage/error; treat as handled
                    return 2
                # If your installers accept kwargs:
                target_helper = inst.helper
                return target_helper.main(**vars(parsed))

            # For all the other methods that aren't manual.
            if len(extras) == 1 and extras[0] == "help":
                inst._show_help(method)
                return 0

            # For 'install' and 'upgrade', resolve dependencies first
            if method in ("install", "upgrade"):
                attempted_argv = [str(method), inst.name, *extras]
                rc, all_dependencies = _run_dependencies(
                    inst,
                    installers_map,
                    method=method,
                    top_level_reexec_argv=attempted_argv,
                )
                if rc != 0:
                    return rc

                if all_dependencies:
                    console.print(
                        f"All dependencies for [{inst.name}] are installed. Proceeding to main installer…",
                        style="cyan",
                        markup=False,
                    )

            # Normal execution: call method and pass through extras (if any)
            target = getattr(inst, method)

            if extras:
                return target(*extras)
            else:
                return target()

        console.print(f"No installer found with the name: [{installer_name}]", style='red', markup=False)
        return 0

    # should never get here: argparse enforces valid sub-commands
    parser.error(f"Unknown command {namespace.sub!r}")


def _make_parser() -> argparse.ArgumentParser:
    description: str = (
        "Den K Simple Installer\n"
        f"{VERSION}\n"
        "\n"
        "Arguments:\n"
        "  install <installer>          Install the script with the given name.\n"
        "       i <installer>           (alias for install)\n"
        "  upgrade  <installer>         Update the script with the given name.\n"
        "       up <installer>          (alias for upgrade)\n"
        "  uninstall <installer>        Uninstall the script with the given name.\n"
        "       un <installer>         (alias for uninstall)\n"
        "\n"
        "  manual <installer>           If manual method is available for specific installer, "
        "                               you can use it to execute the helper script with its parameters.\n"
        "  manual <installer> <args>    Execute the helper script with its parameters.\n"
        "  manual <installer> help      Show help for manual arguments of the helper script.\n"
        "       m <installer>            (alias for manual)\n"
        "\n"
        "  available                    List installers available for the current platform.\n"
        "  available all                List installers for all platforms.\n"
        "       a                       (alias for available)\n"
        "       a all                   (example with alias for available all)\n"
        "  edit-config                  Open the configuration file in the default editor.\n"
        "                               You can change the base installation path here.\n"
        "  prereqs                      Install prerequisites for dkinst. Run this after installing or updating dkinst.\n"
        "                               This includes argcomplete for tab-completion. Example: \n"
        "                               While typing `dkinst install v<Tab>` it will auto-complete to `virtual_keyboard`.\n"
        "                               While typing `dkinst in<Tab>` it will auto-complete to `install`.\n"
        "                               Currently uses argcomplete's global activation method: register-python-argcomplete\n"
        "  prereqs-uninstall            Uninstall prerequisites for dkinst, removing tab-completion support.\n"
        "  help                         Show this help message.\n"
        "       h                       (alias for help)\n"
        "\n"
        "You can use help for any sub-command to see its specific usage.\n"
        "Examples:\n"
        "  dkinst help\n"
        "  dkinst install help\n"
        "  dkinst upgrade help\n"
        "  dkinst uninstall help\n"
        "\n"
        "==============================\n"
        "\n"
    )

    parser = argparse.ArgumentParser(
        prog="dkinst",
        description=description,
        formatter_class=argparse.RawTextHelpFormatter,
        usage=argparse.SUPPRESS,
        add_help=False
    )

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=VERSION,  # prints only the version string, e.g. "1.2.3"
        help="Show the dkinst version and exit.",
    )

    sub = parser.add_subparsers(dest="sub", required=False)

    for subcmd in _base.ALL_METHODS:
        # Make <script> optional so `dkinst install help` works
        sc = sub.add_parser(subcmd, add_help=False)
        # sc.add_argument(
        script_arg = sc.add_argument(
            "script",
            # nargs="?",  # optional to allow `install help`
            help="installer script name or 'help'",
        )

        # Attach dynamic completion for the installer name
        script_arg.completer = _installer_name_completer

        # Everything after <script> is handed untouched to the installer
        sc.add_argument("installer_args", nargs=argparse.REMAINDER)

    available_parser = sub.add_parser("available")
    available_arg = available_parser.add_argument(
        "scope_or_prefix",
        nargs="?",
        help="optional: 'all' to show installers for all platforms, or a name prefix to filter installer names",
    )
    available_arg.completer = _available_scope_or_prefix_completer

    sub.add_parser("edit-config")
    sub.add_parser("prereqs")
    sub.add_parser("prereqs-uninstall")
    sub.add_parser("help")

    if argcomplete is not None:
        argcomplete.autocomplete(parser)

    return parser


def main(argv: list[str] | None = None) -> int:
    """
    Entrypoint for the `dkinst` CLI.

    Supported commands
    ------------------
    dkinst help
    dkinst available
    dkinst install <script>    [extra args passed through]
    dkinst upgrade  <script>    [extra args passed through]
    dkinst uninstall <script>  [extra args passed through]
    """

    # Remove empty folders in config dir on Windows.
    folders.remove_empty_portable_folders()

    parser: argparse.ArgumentParser = _make_parser()          # builds the ArgumentParser shown earlier

    if argv is None:
        argv = sys.argv[1:]

    # If no arguments, enter interactive console instead of printing help
    if not argv:
        bootstrap_argv = _pop_elevate_bootstrap()
        if bootstrap_argv:
            bootstrap_argv = _normalize_argv(bootstrap_argv)

            try:
                namespace = parser.parse_args(bootstrap_argv)
            except SystemExit:
                folders.remove_empty_portable_folders()
                return 2

            rc = _dispatch(namespace, parser)
            if rc is None:
                console.print(
                    "Internal error: command did not return an exit code.",
                    style="red",
                    markup=False,
                )
                folders.remove_empty_portable_folders()
                return 1
            if not isinstance(rc, int):
                console.print(
                    f"Internal error: command returned invalid exit code: {rc!r}",
                    style="red",
                    markup=False,
                )
                folders.remove_empty_portable_folders()
                return 1
            if rc != 0:
                folders.remove_empty_portable_folders()
                return rc

        rc: int = _interactive_console(parser)
        folders.remove_empty_portable_folders()
        return rc

    # Map short aliases to the full subcommand before argparse sees them
    argv = _normalize_argv(argv)

    # Normal one-shot CLI mode
    namespace = parser.parse_args(argv)
    rc: int = _dispatch(namespace, parser)
    folders.remove_empty_portable_folders()
    return rc


if __name__ == "__main__":
    sys.exit(main())