"""Command-line driver for dkinst."""
import sys
import pkgutil
from importlib import import_module
import argparse
from pathlib import Path
import subprocess

from rich.console import Console
from rich.table import Table

from . import __version__
from .installers._base import BaseInstaller
from .installers import _base
from . import installers
from .installers.helpers.infra import system

console = Console()


VERSION: str = __version__


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


def _make_parser() -> argparse.ArgumentParser:
    description: str = (
        "Den K Simple Installer\n"
        f"{VERSION}\n"
        "\n"
        "Arguments:\n"
        "  install <installer>          Install the script with the given name.\n"
        "  update  <installer>          Update the script with the given name.\n"
        "  uninstall <installer>        Uninstall the script with the given name.\n"
        "  manual <installer>           If manual method is available for specific installer, "
        "                               you can use it to execute the helper script with its parameters.\n"
        "\n"
        "  manual <installer> <args>    Execute the helper script with its parameters.\n"
        "  manual <installer> help      Show help for manual arguments of the helper script.\n"
        "  available                    List all available installers.\n"
        "  edit-config                  Open the configuration file in the default editor.\n"
        "                               You can change the base installation path here.\n"
        "  help                         Show this help message.\n"
        "\n"
        "You can use help for any sub-command to see its specific usage.\n"
        "Examples:\n"
        "  dkinst help\n"
        "  dkinst install help\n"
        "  dkinst update help\n"
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
        sc.add_argument(
            "script",
            nargs="?",  # optional to allow `install help`
            help="installer script name or 'help'",
        )
        # Everything after <script> is handed untouched to the installer
        sc.add_argument("installer_args", nargs=argparse.REMAINDER)

    sub.add_parser("available")
    sub.add_parser("edit-config")
    sub.add_parser("help")
    return parser


def main() -> int:
    """
    Entrypoint for the `dkinst` CLI.

    Supported commands
    ------------------
    dkinst help
    dkinst available
    dkinst install <script>    [extra args passed through]
    dkinst update  <script>    [extra args passed through]
    dkinst uninstall <script>  [extra args passed through]
    """
    parser = _make_parser()          # builds the ArgumentParser shown earlier

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

    # Methods from the Known Methods list
    if namespace.sub in _base.ALL_METHODS:
        method = namespace.sub

        # No script provided OR explicitly asked for help
        if namespace.script is None or namespace.script == "help":
            # `manual help` should show the fixed, centralized manual help
            if method == "manual":
                BaseInstaller._show_manual_help()
                return 0
            BaseInstaller._show_help(method)
            return 0

        # From here on, a specific installer was provided
        installer_name = namespace.script
        extras = namespace.installer_args or []

        for inst in _get_installers():
            # Find the provided installer.
            if inst.name != installer_name:
                continue

            inst._platforms_known()

            # Now check if the current platform is supported by this installer.
            current_platform = system.get_platform()
            if current_platform not in inst.platforms:
                console.print(f"This installer [{inst.name}] does not support your platform [{current_platform}].", style='red', markup=False)
                return 1

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

                if (
                        # Installer-specific help: [dkinst <method> <installer> help]
                        len(extras) == 1 and extras[0] == "help"
                ) or (
                        # Manual installer execution without arguments: dkinst manual <installer>
                        # show helper parser help if available.
                        len(extras) == 0
                ):
                    helper_parser.print_help()

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