import os
import platform
import subprocess
import sys
import textwrap
import threading


def get_platform() -> str:
    """Return the current platform as a string."""
    current_platform = platform.system().lower()
    if current_platform == "windows":
        return "windows"
    elif current_platform == "linux":
        if is_debian():
            return "debian"
        else:
            return "linux unknown"
    else:
        return ""


def is_debian() -> bool:
    """Check if the current Linux distribution is Debian-based."""
    if os.path.exists("/etc/os-release"):
        with open("/etc/os-release") as f:
            data = f.read().lower()
            return "debian" in data
    return False


def get_ubuntu_version() -> str | None:
    """Return the Ubuntu version as a string, or None if not on Ubuntu."""
    if os.path.exists("/etc/os-release"):
        with open("/etc/os-release") as f:
            data = f.read().lower()
            if "ubuntu" in data:
                for line in data.splitlines():
                    if line.startswith("version_id="):
                        return line.split("=")[1].strip().strip('"')
    return None


def get_architecture() -> str:
    """Return the system architecture as a string."""
    arch = platform.machine().lower()
    if arch in ["x86_64", "amd64"]:
        return "x64"
    elif arch in ["i386", "i486", "i586", "i686", "i786", "x86"]:
        return "x86"
    elif arch in ["aarch64", "arm64"]:
        return "arm64"
    elif arch in ["armv7l", "armv8l", "arm", "aarch32"]:
        return "arm"
    else:
        raise ValueError(f"Unknown architecture: {arch}")


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