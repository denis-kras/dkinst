"""Command-line driver for dkinst."""
import sys
import pkgutil
from importlib import import_module
import argparse
from pathlib import Path
import subprocess
import os
import shutil
from typing import Literal
import shlex

from rich.console import Console
from rich.table import Table
import argcomplete
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion

from . import __version__
from .installers._base import BaseInstaller
from .installers import _base
from . import installers
from .installers.helpers.infra import system, permissions, prereqs, prereqs_uninstall


console = Console()


VERSION: str = __version__


# Short aliases for top-level commands
COMMAND_ALIASES: dict[str, str] = {
    "i": "install",
    "up": "upgrade",
    "un": "uninstall",
    "m": "manual",
    "a": "available",
    "h": "help",
}


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

        candidates: list[str] = []

        if token_index == 0:
            # Completing the first word: choose from subcommands
            candidates = [cmd for cmd in self.subcommands if cmd.startswith(prefix)]
        elif token_index == 1 and first_word in _base.ALL_METHODS:
            # Completing the second word: installer names for install/upgrade/uninstall/manual
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


def cmd_available() -> None:
    """List every known installer with metadata."""
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Name", style="bold")
    table.add_column("Platforms")
    table.add_column("Methods")
    table.add_column("Manual Arguments")

    # collect all installers
    installers_list: list[BaseInstaller] = _get_installers()

    methods: list[str]
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
) -> tuple[int, set[str]]:
    """
    Recursively install `installer.dependencies` (list of installer names or
    installer objects) before installing `installer` itself.
    Returns 0 on success; non-zero aborts the whole command.

    :param installer: The installer whose dependencies to install.
    :param installers_map: A map of installer name -> installer instance.
    :param method: The method for which dependencies are being resolved.
    :param done: Set of already installed dependency names.
    :param stack: Current dependency resolution stack (for circular dep detection).

    :return: (return code, set of installed dependency names)
    """
    done = done or set()
    stack = stack or []

    # When resolving dependencies for an 'upgrade', we only need to ensure
    # they are installed. Dependencies should always use their 'install'
    # method, even if they implement 'upgrade'.
    if method == "upgrade":
        method = "install"

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

        # If the dependency is already installed, skip its installation (and its own deps)
        if dep_inst.is_installed():
            console.print(
                f"Dependency [{dep_name}] is already installed. Skipping.",
                style="cyan",
                markup=False,
            )
            done.add(dep_name)
            continue

        # Decide which method to run on the dependency:
        #  - Prefer the same 'method' as the main command, if supported.
        #  - Otherwise fall back to 'install' (to ensure the dep is present).
        known_methods: list[str] = _base.get_known_methods(dep_inst)
        dep_method_name: Literal["install", "uninstall", "upgrade"] = method if method in known_methods else "install"

        # Admin check for the dependency if required on this platform. Dependencies are always checked only for the 'install' method.
        rc = _require_admin_if_needed(dep_inst, method=dep_method_name)
        if rc != 0:
            return rc, done

        # Recurse first so deep deps install in correct order
        rc, _ = _run_dependencies(dep_inst, installers_map, method, done, stack + [dep_name])
        if rc != 0:
            return rc, done

        # Finally, actually run the chosen method on the dependency
        verb = "Installing" if dep_method_name == "install" else (
            "Upgrading" if dep_method_name == "upgrade" else f"Running '{dep_method_name}' for"
        )
        console.print(
            f"{verb} dependency [{dep_name}] for [{installer.name}]…",
            style="green",
            markup=False,
        )

        dep_func = getattr(dep_inst, dep_method_name)
        rc = dep_func()
        if rc not in (0, None):
            return rc, done

        done.add(dep_name)

    return 0, done


def ensure_root_or_reexec() -> None:
    """If not root, re-exec this command under sudo, preserving args."""
    if os.geteuid() == 0:
        return  # already root
    exe = shutil.which("dkinst") or sys.argv[0]
    # make it absolute in case it was found via PATH
    exe = os.path.abspath(exe)
    # Replace the current process with: sudo <same dkinst> <same args>
    os.execvp("sudo", ["sudo", "-E", exe] + sys.argv[1:])


def _require_admin_if_needed(
        installer: BaseInstaller,
        method: Literal["install", "uninstall", "upgrade"] = "install"
) -> int:
    """
    Enforce admin privileges when requested by the installer.

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
        # Be tolerant: allow string or list
        if isinstance(methods_for_platform, str):
            methods_for_platform = [methods_for_platform]
        methods_for_platform = [m.lower() for m in methods_for_platform]

        if method.lower() in methods_for_platform:
            needs_admin = True
    else:
        raise ValueError(f"installer.admins has unsupported type: {type(admins)}")

    if not needs_admin:
        return 0

    # If we require admin but already have it, we're fine
    if permissions.is_admin():
        return 0

    console.print('This action requires administrator privileges.', style='red')

    if current_platform == 'debian':
        # Auto-elevate; this never returns on success
        ensure_root_or_reexec()

        # If we get here, sudo failed
        venv = os.environ.get('VIRTUAL_ENV', None)
        if venv:
            print(f'Try: sudo "{venv}/bin/dkinst" {method} {installer.name}')

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

            _dispatch(namespace, parser)
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

            _dispatch(namespace, parser)

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
        cmd_available()
        return 0

    if namespace.sub == "edit-config":
        config_path: str = str(Path(__file__).parent / "config.toml")
        subprocess.run(["notepad", config_path])
        return 0

    if namespace.sub == "prereqs":
        return prereqs._cmd_prereqs()

    if namespace.sub == "prereqs-uninstall":
        return prereqs_uninstall._cmd_uninstall_prereqs()

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
                rc = _require_admin_if_needed(inst, method)
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
                rc, all_dependencies = _run_dependencies(inst, installers_map, method=method)
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
        "  available                    List all available installers.\n"
        "       a                       (alias for available)\n"
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

    sub.add_parser("available")
    sub.add_parser("edit-config")
    sub.add_parser("prereqs")
    sub.add_parser("prereqs-uninstall")
    sub.add_parser("help")

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
    parser: argparse.ArgumentParser = _make_parser()          # builds the ArgumentParser shown earlier

    if argv is None:
        argv = sys.argv[1:]

        # If no arguments, enter interactive console instead of printing help
    if not argv:
        return _interactive_console(parser)

    # Map short aliases to the full subcommand before argparse sees them
    argv = _normalize_argv(argv)

    # Normal one-shot CLI mode
    namespace = parser.parse_args(argv)
    return _dispatch(namespace, parser)


if __name__ == "__main__":
    sys.exit(main())