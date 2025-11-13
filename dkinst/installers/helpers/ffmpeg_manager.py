import sys

from rich.console import Console

from .infra import wingets


console = Console()


SCRIPT_NAME: str = "FFMPEG Manager"
AUTHOR: str = "Denis Kras"
VERSION: str = "1.0.0"
RELEASE_COMMENT: str = "Initial version."


"""
We can use the GitHub repository to download the portales:
https://github.com/GyanD/codexffmpeg/releases
"""


WINGET_PACKAGE_ID_FULL: str = "Gyan.FFmpeg"
WINGET_PACKAGE_ID_ESSENTIALS: str = "Gyan.FFmpeg.Essentials"
WINGET_PACKAGE_ID_SHARED: str = "Gyan.FFmpeg.Shared"


def _make_parser():
    import argparse
    parser = argparse.ArgumentParser(description="Install FFMPEG on Windows.")
    parser.add_argument(
        "-ifw", "--install-full-winget", action="store_true",
        help="Uses WinGet to install the latest FFMPEG Full version from the official WinGet repository."
    )
    parser.add_argument(
        "-iew", "--install-essentials-winget", action="store_true",
        help="Uses WinGet to install the latest FFMPEG Essentials version from the official WinGet repository."
    )
    parser.add_argument(
        "-isw", "--install-shared-winget", action="store_true",
        help="Uses WinGet to install the latest FFMPEG Essentials version from the official WinGet repository."
    )

    parser.add_argument(
        "-ufw", "--uninstall-full-winget", action="store_true",
        help="Uses WinGet to uninstall the latest FFMPEG Full version from the official WinGet repository."
    )
    parser.add_argument(
        "-uew", "--uninstall-essentials-winget", action="store_true",
        help="Uses WinGet to uninstall the latest FFMPEG Essentials version from the official WinGet repository."
    )
    parser.add_argument(
        "-usw", "--uninstall-shared-winget", action="store_true",
        help="Uses WinGet to uninstall the latest FFMPEG Essentials version from the official WinGet repository."
    )

    return parser


def main(
        install_full_winget: bool = False,
        install_essentials_winget: bool = False,
        install_shared_winget: bool = False,
        uninstall_full_winget: bool = False,
        uninstall_essentials_winget: bool = False,
        uninstall_shared_winget: bool = False,
) -> int:
    if not (install_full_winget or install_essentials_winget or install_shared_winget or
            uninstall_full_winget or uninstall_essentials_winget or uninstall_shared_winget):
        console.print("[red]No method specified. Use --help for more information.[/red]")
        return 1
    if (install_full_winget + install_essentials_winget + install_shared_winget) > 1:
        console.print("[red]Please specify only one method at a time.[/red]")
        return 1

    if install_full_winget:
        return wingets.install_package(WINGET_PACKAGE_ID_FULL)
    if install_essentials_winget:
        return wingets.install_package(WINGET_PACKAGE_ID_ESSENTIALS)
    if install_shared_winget:
        return wingets.install_package(WINGET_PACKAGE_ID_SHARED)
    if uninstall_full_winget:
        return wingets.uninstall_package(WINGET_PACKAGE_ID_FULL)
    if uninstall_essentials_winget:
        return wingets.uninstall_package(WINGET_PACKAGE_ID_ESSENTIALS)
    if uninstall_shared_winget:
        return wingets.uninstall_package(WINGET_PACKAGE_ID_SHARED)

    return 0


if __name__ == '__main__':
    exec_parser = _make_parser()
    args = exec_parser.parse_args()
    sys.exit(main(**vars(args)))