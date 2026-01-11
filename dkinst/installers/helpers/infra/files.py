import os


def find_file(
        file_name: str,
        directory_path: str
):
    """
    The function finds the file in the directory recursively.
    :param file_name: string, The name of the file to find.
    :param directory_path: string, The directory to search in.
    :return:
    """
    for dir_path, dir_names, filenames in os.walk(directory_path):
        for filename in filenames:
            if filename == file_name:
                return os.path.join(dir_path, filename)
    return None