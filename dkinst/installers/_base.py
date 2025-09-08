import inspect
import argparse
import tomllib
from pathlib import Path
from types import ModuleType
from typing import Literal


INSTALLATION_PATH_PORTABLE_WINDOWS: str = "C:\\dkinst"      # Installation path for portable files on Windows that don't have a default location.

KNOWN_SUPPORTED_PLATFORMS: list[str] = ["windows", "debian"]

KNOWN_METHODS: list[str] | None = None
CUSTOM_METHODS: list[str] = ["manual"]
ALL_METHODS: list[str] | None = None


class BaseInstaller:
    def __init__(self):
        # The name of the installation script that will be used by the main script to install.
        self.name: str = "baseinstall"
        # The description of the installation script.
        self.description: str = "Base Installer"
        # The version of the installation script.
        self.version: str = "1.0.0"
        # The platforms supported by this installer.
        self.platforms: list[str] = []
        # The helper module that provides additional functionality for this installer.
        # Providing the helper module will automatically introduce the 'manual()' method on the 'cli.py' level.
        self.helper: ModuleType | None = None

        self.base_path: str = INSTALLATION_PATH_PORTABLE_WINDOWS
        self.dir_path: str | None = None  # Path to the installation directory of the installed application, if applicable. Example: Path(self.base_path) / self.name
        self.exe_path: str | None = None  # Path to the main executable of the installed application, if applicable. Example: Path(self.dir_path) / "app.exe"

    def install(self):
        raise NotImplementedError("Subclasses should implement this method.")

    def uninstall(self):
        raise NotImplementedError("Method not implemented by the subclass. Uninstall manually.")

    def update(self):
        raise NotImplementedError("Method not implemented by the subclass. Update manually.")

    @staticmethod
    def _show_help(
            method: Literal["install", "uninstall", "update"]
    ) -> None:
        """
        Print default help for a given method. Can be called as:
          BaseInstaller._show_help("install")
          inst._show_help("install")  # also works (staticmethod)
        """
        m = (method or "").lower()

        header = {
            "install": "Install — download and set up an application/installer.",
            "uninstall": "Uninstall — remove an application installed by this tool.",
            "update": "Update — update an application to the latest supported version.",
            "manual": "Manual — run the installer helper directly with custom args.",
        }.get(m, "dkinst — helpers and installers")

        lines: list[str] = [header, ""]

        if m == "install":
            lines += [
                "Usage:",
                "  dkinst install help",
                "  dkinst install <installer> help",
                "  dkinst install <installer> [args...]",
                "",
                "Notes:",
                "  • Use `dkinst available` to see all installers.",
                "  • `install <installer> help` shows details for that installer’s install flow.",
                "  • Extra [args...] are passed to the installer/its helper if supported.",
            ]
        elif m == "uninstall":
            lines += [
                "Usage:",
                "  dkinst uninstall help",
                "  dkinst uninstall <installer> help",
                "  dkinst uninstall <installer> [args...]",
                "",
                "Notes:",
                "  • Some installers support silent removal flags; check per-installer help.",
                "  • Extra [args...] are passed through if the installer supports them.",
            ]
        elif m == "update":
            lines += [
                "Usage:",
                "  dkinst update help",
                "  dkinst update <installer> help",
                "  dkinst update <installer> [args...]",
                "",
                "Notes:",
                "  • If an installer doesn’t support in-place updates, it may reinstall.",
                "  • Extra [args...] are passed through if supported by the installer.",
            ]
        else:
            lines += [
                "Usage:",
                "  dkinst help",
                "  dkinst available",
                "  dkinst <install|uninstall|update|manual> help",
                "  dkinst <install|uninstall|update|manual> <installer> help",
                "  dkinst <install|uninstall|update|manual> <installer> [args...]",
            ]

        print("\n".join(lines))

    @staticmethod
    def _show_manual_help():
        lines: list[str] = []
        lines += [
                "Usage:",
                "  dkinst manual help",
                "  dkinst manual <installer> help",
                "  dkinst manual <installer> <helper-args...>",
                "",
                "Notes:",
                "  • `manual` exposes the installer’s helper parser directly.",
                "  • `<installer> help` will print that helper’s argparse usage if available.",
                "  • Use this when you need fine-grained flags not covered by the defaults.",
            ]

        print("\n".join(lines))

    def _platforms_known(self):
        """
        Check if the current platform list is known list.
        """

        for platform in self.platforms:
            if platform not in KNOWN_SUPPORTED_PLATFORMS:
                raise ValueError(f"Platform '{platform}' is not known.")


def get_base_known_methods() -> list[str]:
    """Return a list of known methods that can be called on installers."""
    all_methods = inspect.getmembers(BaseInstaller, predicate=inspect.isroutine)

    filtered_methods: list[str] = []
    for method_name, bound_method in all_methods:
        if not method_name.startswith("_"):
            filtered_methods.append(method_name)

    global KNOWN_METHODS
    if KNOWN_METHODS is None:
        KNOWN_METHODS = filtered_methods

    global ALL_METHODS
    ALL_METHODS = CUSTOM_METHODS + KNOWN_METHODS

    return filtered_methods
# Run this at module load time to initialize KNOWN_METHODS
get_base_known_methods()


def assign_base_paths_from_config() -> None:
    """Assign the base_path of all installers from the configuration file."""

    working_path: Path = Path(__file__).parent.parent
    config_path: Path = working_path / "config.toml"

    with open(str(config_path), "rb") as f:
        config_content: dict = tomllib.load(f)

    global INSTALLATION_PATH_PORTABLE_WINDOWS
    INSTALLATION_PATH_PORTABLE_WINDOWS = config_content["windows_portable_installation_dir"]
assign_base_paths_from_config()


def get_known_methods(installer: BaseInstaller) -> list[str]:
    """Return a list of known methods that can be called on the given installer."""

    # All the subclasses of BaseInstaller will have most of the methods of BaseInstaller.
    # But not all, if a method is not overridden, it will be present in subclass as a bound method.
    # So we filter out the methods that are not overridden.
    filtered_methods: list[str] = []
    for method_name in KNOWN_METHODS:
        if getattr(installer.__class__, method_name) is not getattr(BaseInstaller, method_name):
            filtered_methods.append(method_name)

    # If 'helper' attribute is not None, this means that the helper module was provided, add the 'manual()' method.
    if installer.helper:
        filtered_methods = filtered_methods + CUSTOM_METHODS

    return filtered_methods


def _get_helper_parser(
        installer: BaseInstaller,
        methods: list[str] = None
) -> argparse.ArgumentParser | None:
    """
    If installer overrides `manual`, try to import
    `installers.helpers.<installer.name>` and harvest its ArgumentParser.

    :param installer: The installer instance to check.
    :param methods: Optional list of methods to check against. If not provided, will gather known methods.
    :return: An ArgumentParser instance if available, or None if nothing could be found.
    """

    if not methods:
        methods = get_known_methods(installer)

    if "manual" not in methods:
        return None  # no manual method, nothing to return
    if installer.helper is None:
        return None  # no helper, nothing to return

    # Is there a parser function in the helper?
    parse_args_callable = getattr(installer.helper, "_make_parser", None)
    if parse_args_callable is None:
        return None  # couldn’t obtain one

    parser: argparse.ArgumentParser = parse_args_callable()
    return parser


def _extract_helper_args(
        installer: BaseInstaller,
        methods: list[str] = None
) -> list[str]:
    """
    If installer overrides `manual`, try to import
    `installers.helpers.<installer.name>` and harvest its ArgumentParser and get its tokens (arguments).

    :param installer: The installer instance to check.
    :param methods: Optional list of methods to check against. If not provided, will gather known methods.
    :return: A list of CLI tokens that can be used with the installer.
        Example: ['--prefix', '--force', 'target'], or [] if nothing could be found.
    """
    parser: argparse.ArgumentParser | None = _get_helper_parser(installer, methods)
    if not parser:
        return []

    tokens: list[str] = []
    for act in parser._actions:
        if act.option_strings:                # flags like -f/--force
            tokens.append("/".join(act.option_strings))
        else:                                 # positionals
            tokens.append(act.dest)
    return tokens
