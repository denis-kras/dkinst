import subprocess
import sys

from rich.console import Console


console = Console()


def run_package_manager_command(
        cmd: list[str],
        action: str
) -> tuple[int, str]:
    """
    Run a package manager command (like winget/choco) and stream its output to the console, and capture it.

    :param cmd: The command to run as a list of strings.
    :param action: A string describing the action (for logging purposes). like "Installation", "Upgrade", "Uninstallation".

    :return: A tuple of (return code, captured output as string).
    """
    try:
        # text=False -> we get raw bytes, so \r is preserved
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # merge stderr into stdout
        )
    except FileNotFoundError:
        console.print(f"[red]{cmd[0]} is not installed or not in PATH.[/red]")
        return 1, ""

    assert process.stdout is not None

    captured_chunks: list[str] = []

    while True:
        chunk = process.stdout.read(4096)
        if not chunk:
            break

        # 1) Forward raw bytes to the underlying stdout (preserves \r progress)
        sys.stdout.buffer.write(chunk)
        sys.stdout.buffer.flush()

        # 2) Decode and store for later use / logging
        captured_chunks.append(chunk.decode("utf-8", errors="replace"))

    returncode = process.wait()
    output = "".join(captured_chunks)

    if returncode != 0:
        console.print(
            f"\n[red]{action} failed with exit code {returncode}. "
            "See output above for details.[/red]"
        )
    else:
        console.print(f"\n[green]{action} completed successfully.[/green]")

    return returncode, output