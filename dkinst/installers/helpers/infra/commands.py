import subprocess
import sys
import threading
import queue
import time
import codecs

from rich.console import Console


console = Console()


def run_command_stream_and_return_output(
        cmd: list[str],
) -> tuple[int, str]:
    """
    Run a command as a subprocess, streaming its output to the console
    in real-time, and capturing the output for later use.

    Args:
        cmd (list[str]): The command and its arguments to run.

    Returns:
        tuple[int, str]: A tuple containing the return code and the captured output.
    """

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            bufsize=0,          # IMPORTANT: unbuffered pipe; avoids BufferedReader "fill N bytes" stalls
            close_fds=True,     # IMPORTANT: reduces inherited handles (esp. helpful on Windows)
        )
    except FileNotFoundError:
        message = f'FileNotFoundError: {cmd[0]} is not installed or not in PATH.'
        console.print(f"[red]{message}[/red]")
        return 1, message

    assert process.stdout is not None

    q: queue.Queue[bytes | None] = queue.Queue()

    def pump_stdout() -> None:
        try:
            while True:
                chunk = process.stdout.read(4096)
                if not chunk:
                    break
                q.put(chunk)
        finally:
            q.put(None)  # sentinel

    t = threading.Thread(target=pump_stdout, daemon=True)
    t.start()

    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    captured_parts: list[str] = []

    exit_seen_at: float | None = None

    while True:
        try:
            chunk = q.get(timeout=0.1)
        except queue.Empty:
            # If process ended but the pipe never reaches EOF (handle inheritance),
            # don't wait forever.
            if process.poll() is not None:
                if exit_seen_at is None:
                    exit_seen_at = time.monotonic()
                if time.monotonic() - exit_seen_at > 2.0:
                    try:
                        process.stdout.close()
                    except Exception:
                        pass
                    break
            continue

        if chunk is None:
            break

        # Stream raw bytes (preserves \r progress behavior)
        sys.stdout.buffer.write(chunk)
        sys.stdout.buffer.flush()

        # Capture decoded text safely (incremental decoding)
        captured_parts.append(decoder.decode(chunk))

    captured_parts.append(decoder.decode(b"", final=True))

    returncode = process.wait()
    output = "".join(captured_parts)

    return returncode, output


def run_package_manager_command(
        cmd: list[str],
        action: str,
        verbose: bool = False,
) -> tuple[int, str]:
    rc, output = run_command_stream_and_return_output(cmd)

    if verbose:
        if rc != 0:
            console.print(
                f"\n[red]{action} failed with exit code {rc}. "
                "See output above for details.[/red]"
            )
        else:
            console.print(f"\n[green]{action} completed successfully.[/green]")

    return rc, output