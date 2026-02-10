import sys
import os


def initialize_ansi() -> None:
    """
    On Windows platforms, this is needed in order for ANSI escape codes to work in CMD.

    :return: None
    """

    if sys.platform.lower() == "win32":
        os.system("")


# https://en.wikipedia.org/wiki/ANSI_escape_code#Colors
class ColorsBasic:
    """
    Usage 1:
        print(f'{ColorsBasic.GREEN}green{ColorsBasic.END}')
    Usage 2:
        col = ColorsBasic()
        print(f'{col.GREEN}red{col.END}')
    """

    initialize_ansi()

    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    HEADER = '\033[95m'
    CYAN = '\033[96m'
    ORANGE = '\033[38;2;255;165;0m'
    END = '\033[0m'


def get_colors_basic_dict(color):
    colors_basic_dict = {
        'red': ColorsBasic.RED,
        'green': ColorsBasic.GREEN,
        'yellow': ColorsBasic.YELLOW,
        'blue': ColorsBasic.BLUE,
        'header': ColorsBasic.HEADER,
        'cyan': ColorsBasic.CYAN,
        'orange': ColorsBasic.ORANGE
    }

    return colors_basic_dict[color]


def printc(
        message: str,
        color: str
):
    print(get_colors_basic_dict(color.lower()) + message + ColorsBasic.END)