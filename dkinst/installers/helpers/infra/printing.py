from atomicshop.basics import ansi_escape_codes


def printc(
        message: str,
        color: str
):
    print(ansi_escape_codes.get_colors_basic_dict(color) + message + ansi_escape_codes.ColorsBasic.END)