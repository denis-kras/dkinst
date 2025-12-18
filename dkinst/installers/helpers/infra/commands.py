import subprocess
import sys
import threading
import queue
import time
import codecs

from rich.console import Console


console = Console()


def run_package_manager_command(cmd: list[str], action: str) -> tuple[int, str]:
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
        console.print(f"[red]{cmd[0]} is not installed or not in PATH.[/red]")
        return 1, ""

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

        # 1) Stream raw bytes (preserves \r progress behavior)
        sys.stdout.buffer.write(chunk)
        sys.stdout.buffer.flush()

        # 2) Capture decoded text safely (incremental decoding)
        captured_parts.append(decoder.decode(chunk))

    captured_parts.append(decoder.decode(b"", final=True))

    returncode = process.wait()
    output = "".join(captured_parts)

    if returncode != 0:
        console.print(
            f"\n[red]{action} failed with exit code {returncode}. "
            "See output above for details.[/red]"
        )
    else:
        console.print(f"\n[green]{action} completed successfully.[/green]")

    return returncode, output