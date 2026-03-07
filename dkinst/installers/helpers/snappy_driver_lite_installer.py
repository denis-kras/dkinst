import sys
import os
import re
import shutil
import tempfile
from pathlib import Path

import requests
from rich.console import Console

from atomicshop import web
from dkarchiver.arch_wrappers import sevenz_app_w


console = Console()


SCRIPT_NAME: str = "Snappy Driver Installer Lite Manager"
AUTHOR: str = "Denis Kras"
VERSION: str = "1.0.0"
RELEASE_COMMENT: str = "Initial version."

DOWNLOAD_PAGE_URL: str = "https://sdi-tool.org/download/"
DOWNLOAD_URL_TEMPLATE: str = "https://driveroff.net/drv/SDI_{version}.7z"
VERSION_FILE_NAME: str = "version.txt"
VERSION_REGEX: str = r"SDI_([\d.]+)\.7z"


def get_latest_version() -> str | None:
    """Scrape the SDI download page to find the latest Lite version."""
    print("Fetching latest SDI Lite version...")
    response = requests.get(DOWNLOAD_PAGE_URL, timeout=15)
    response.raise_for_status()

    match = re.search(VERSION_REGEX, response.text)
    if not match:
        console.print("[red]Could not find SDI Lite version on the download page.[/red]")
        return None

    version: str = match.group(1)
    print(f"Latest SDI Lite version: {version}")
    return version


def get_installed_version(dir_path: str) -> str | None:
    """Read the installed version from version.txt in the install directory."""
    version_file: str = os.path.join(dir_path, VERSION_FILE_NAME)
    if not os.path.isfile(version_file):
        return None
    with open(version_file, "r") as f:
        return f.read().strip()


def _write_version_file(dir_path: str, version: str) -> None:
    """Write version to version.txt in the install directory."""
    version_file: str = os.path.join(dir_path, VERSION_FILE_NAME)
    with open(version_file, "w") as f:
        f.write(version)


def install(dir_path: str) -> int:
    """Download and install SDI Lite to the given directory."""
    version: str | None = get_latest_version()
    if not version:
        return 1

    download_url: str = DOWNLOAD_URL_TEMPLATE.format(version=version)
    console.print(f"Downloading SDI Lite {version} from: {download_url}")

    temp_dir: str = tempfile.mkdtemp()
    try:
        archive_path: str = web.download(download_url, temp_dir)

        # Extract archive to a temp extraction dir.
        temp_extract_dir: str = os.path.join(temp_dir, "extracted")
        sevenz_app_w.extract_file(archive_path, temp_extract_dir, force_overwrite=True)

        # The archive contains a top-level SDI_{version}/ folder.
        # Move its contents into dir_path.
        extracted_inner: str = os.path.join(temp_extract_dir, f"SDI_{version}")
        if not os.path.isdir(extracted_inner):
            # Fallback: if no inner folder, use the extraction root.
            extracted_inner = temp_extract_dir

        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
        shutil.move(extracted_inner, dir_path)

        _write_version_file(dir_path, version)
    finally:
        # Clean up temp directory.
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

    console.print(f"[green]SDI Lite {version} installed to: {dir_path}[/green]")
    return 0


def upgrade(dir_path: str) -> int:
    """Upgrade SDI Lite: check latest version, remove old, install new."""
    installed_version: str | None = get_installed_version(dir_path)
    if installed_version:
        console.print(f"Installed SDI Lite version: {installed_version}")
    else:
        console.print("[yellow]No installed version found. Will perform fresh install.[/yellow]")

    latest_version: str | None = get_latest_version()
    if not latest_version:
        return 1

    if installed_version == latest_version:
        console.print(f"[green]Already up to date: {installed_version}[/green]")
        return 0

    console.print(f"[yellow]Upgrading from {installed_version or 'N/A'} to {latest_version}...[/yellow]")

    # Remove old installation.
    if os.path.exists(dir_path):
        console.print(f"Removing old installation at: {dir_path}")
        shutil.rmtree(dir_path)

    return install(dir_path)


def _make_parser():
    import argparse
    parser = argparse.ArgumentParser(description="Snappy Driver Installer Lite Manager.")
    parser.add_argument(
        "-i", "--install", action="store_true",
        help="Install SDI Lite."
    )
    parser.add_argument(
        "-u", "--upgrade", action="store_true",
        help="Upgrade SDI Lite to the latest version."
    )
    parser.add_argument(
        "-d", "--dir-path", type=str, default=None,
        help="Installation directory path. Defaults to C:\\dkinst\\snappy_driver_lite."
    )
    return parser


# Aliases to avoid parameter name shadowing in main().
install_function = install
upgrade_function = upgrade


def main(
        install: bool = False,
        upgrade: bool = False,
        dir_path: str = None,
) -> int:
    if not install and not upgrade:
        console.print("[red]No method specified. Use --help for more information.[/red]")
        return 1

    if install and upgrade:
        console.print("[red]Please specify only one method at a time.[/red]")
        return 1

    if not dir_path:
        dir_path = str(Path("C:\\dkinst") / "snappy_driver_lite")

    if install:
        return install_function(dir_path)

    if upgrade:
        return upgrade_function(dir_path)

    return 0


if __name__ == '__main__':
    exec_parser = _make_parser()
    args = exec_parser.parse_args()
    sys.exit(main(**vars(args)))
