import os

from ... import _base


def remove_empty_portable_folders() -> None:
    """Remove empty portable installation folders."""
    if os.name == 'nt':
        path_to_check: str = _base.INSTALLATION_PATH_PORTABLE_WINDOWS
        # Get folders in the config path.
        if os.path.exists(path_to_check):
            for item in os.listdir(path_to_check):
                item_path: str = os.path.join(path_to_check, item)
                if os.path.isdir(item_path) and not os.listdir(item_path):
                    os.rmdir(item_path)