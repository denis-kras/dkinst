import subprocess
import sys
import threading
import queue
import time
import codecs
import shlex
import textwrap

from rich.console import Console


console = Console()


def run_command_stream_and_return_output(
    cmd: list[str] | str,
    stream: bool = True,
) -> tuple[int, str]:
    """
    Run a command as a subprocess, optionally streaming its output to the console
    in real-time, and capturing the output for later use.

    Args:
        cmd: The command and its arguments to run.
             If str, will be split by shlex to list.
        stream: If True, stream output to terminal as it arrives.
                 If False, do not stream; only capture and return output.

    Returns:
        (return_code, captured_output)
    """
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            bufsize=0,          # unbuffered pipe
            close_fds=True,     # reduces inherited handles
        )
    except FileNotFoundError:
        message = f"FileNotFoundError: {cmd[0]} is not installed or not in PATH."
        # If you have rich console available, keep it; otherwise print.
        try:
            console.print(f"[red]{message}[/red]")  # type: ignore[name-defined]
        except Exception:
            print(message, file=sys.stderr)
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

        if stream:
            # Stream raw bytes (preserves \r progress behavior)
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()

        # Capture decoded text safely (incremental decoding)
        captured_parts.append(decoder.decode(chunk))

    captured_parts.append(decoder.decode(b"", final=True))

    returncode = process.wait()
    output = "".join(captured_parts)
    return returncode, output


def execute_bash_script_string(
        script_lines: list[str]
):
    """
    Execute a bash script provided as a list of strings.
    Example:
        script = [
            \"\"\"

echo "Hello, World!"
ls -la
echo "test complete"
\"\"\"]

    :param script_lines: list of strings, The bash script to execute.
    :return:
    """

    # Build the script (strict mode makes the shell exit on the first error)
    script = "set -Eeuo pipefail\n" + textwrap.dedent("\n".join(script_lines)).strip() + "\n"

    # Start the process with pipes so we can stream
    proc = subprocess.Popen(
        ["bash", "-s"],  # read script from stdin
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,  # decode to str
        bufsize=1,  # line-buffered (in text mode)
    )

    # Send the script and close stdin to signal EOF
    assert proc.stdin is not None
    proc.stdin.write(script)
    proc.stdin.flush()
    proc.stdin.close()

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    def _reader(pipe, sink, to_stderr: bool):
        try:
            for line in iter(pipe.readline, ''):
                sink.append(line)
                # Mirror to the caller's console immediately
                if to_stderr:
                    print(line, end='', file=sys.stderr, flush=True)
                else:
                    print(line, end='', flush=True)
        finally:
            pipe.close()

    # Read both streams concurrently to avoid deadlocks
    t_out = threading.Thread(target=_reader, args=(proc.stdout, stdout_lines, False), daemon=True)
    t_err = threading.Thread(target=_reader, args=(proc.stderr, stderr_lines, True), daemon=True)
    t_out.start()
    t_err.start()

    # Wait for process and readers to finish
    returncode = proc.wait()
    t_out.join()
    t_err.join()

    if returncode != 0:
        raise RuntimeError(
            f"String script failed (exit code {returncode}).\n"
            # f"--- STDOUT ---\n{''.join(stdout_lines)}\n"
            f"--- STDERR ---\n{''.join(stderr_lines)}"
        )


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