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

from rich.console import Console
from rich.table import Table
import argcomplete

from . import __version__
from .installers._base import BaseInstaller
from .installers import _base
from . import installers
from .installers.helpers.infra import system, permissions, prereqs, prereqs_uninstall

console = Console()


VERSION: str = __version__


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
    done: set[str] | None = None,
    stack: list[str] | None = None,
) -> tuple[int, set[str]]:
    """
    Recursively install `installer.dependencies` (list of installer names or
    installer objects) before installing `installer` itself.
    Returns 0 on success; non-zero aborts the whole command.
    """
    done = done or set()
    stack = stack or []

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

        # Admin check for the dependency if required on this platform
        rc = _require_admin_if_needed(dep_inst)
        if rc != 0:
            return rc, done

        # Recurse first so deep deps install in correct order
        rc, _ = _run_dependencies(dep_inst, installers_map, done, stack + [dep_name])
        if rc != 0:
            return rc, done

        console.print(
            f"Installing dependency [{dep_name}] for [{installer.name}]…",
            style="green", markup=False
        )
        rc = dep_inst.install()
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


def _require_admin_if_needed(installer: BaseInstaller) -> int:
    """
    If the installer declares an `admins` list (subset of its `platforms`)
    and the current platform is in that list, enforce admin privileges.
    Returns 0 if ok; non-zero to abort.
    """
    admins = getattr(installer, "admins", None) or []
    if not admins:
        return 0
    current_platform = system.get_platform()
    if current_platform in admins and not permissions.is_admin():

        console.print("This action requires administrator privileges.", style='red')
        if current_platform == "debian":
            # Auto-elevate; this never returns on success
            ensure_root_or_reexec()

            # If we get here, sudo failed
            venv = os.environ.get('VIRTUAL_ENV', None)
            if venv:
                print(f'Try: sudo "{venv}/bin/dkinst" install mongodb')
        return 1
    return 0


def _make_parser() -> argparse.ArgumentParser:
    description: str = (
        "Den K Simple Installer\n"
        f"{VERSION}\n"
        "\n"
        "Arguments:\n"
        "  install <installer>          Install the script with the given name.\n"
        "  upgrade  <installer>          Update the script with the given name.\n"
        "  uninstall <installer>        Uninstall the script with the given name.\n"
        "\n"
        "  manual <installer>           If manual method is available for specific installer, "
        "                               you can use it to execute the helper script with its parameters.\n"
        "  manual <installer> <args>    Execute the helper script with its parameters.\n"
        "  manual <installer> help      Show help for manual arguments of the helper script.\n"
        "\n"
        "  available                    List all available installers.\n"
        "  edit-config                  Open the configuration file in the default editor.\n"
        "                               You can change the base installation path here.\n"
        "  prereqs                      Install prerequisites for dkinst. Run this after installing or updating dkinst.\n"
        "                               This includes argcomplete for tab-completion. Example: \n"
        "                               While typing `dkinst install v<Tab>` it will auto-complete to `virtual_keyboard`.\n"
        "                               While typing `dkinst in<Tab>` it will auto-complete to `install`.\n"
        "                               Currently uses argcomplete's global activation method: register-python-argcomplete\n"
        "  prereqs-uninstall            Uninstall prerequisites for dkinst, removing tab-completion support.\n"
        "  help                         Show this help message.\n"
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


def main() -> int:
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

    # If no arguments, show the top-level help and exit successfully
    passed_arguments = sys.argv[1:]
    if not passed_arguments:
        parser.print_help()
        return 0

    namespace = parser.parse_args()         # plain parsing now

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
                console.print(f"This installer [{inst.name}] does not support your platform [{current_platform}].", style='red', markup=False)
                return 1

            # If this is an install, enforce admin privileges when requested.
            if method in ["install", "manual"] and "help" not in extras:
                rc = _require_admin_if_needed(inst)
                if rc != 0:
                    return rc

            # Processing the 'manual' method.
            if method == 'manual':
                installer_methods = _base.get_known_methods(inst)
                if 'manual' not in installer_methods:
                    console.print(f"No 'manual' method available for the installer: [{inst.name}]", style='red', markup=False)
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

            # If this is an 'install', resolve & install dependencies first
            if method == "install":
                rc, all_dependencies = _run_dependencies(inst, installers_map)
                if rc != 0:
                    return rc

                if all_dependencies:
                    console.print(
                        f"All dependencies for [{inst.name}] are installed. Proceeding to main installer…",
                        style = "cyan", markup = False)

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


if __name__ == "__main__":
    sys.exit(main())