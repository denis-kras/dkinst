from typing import Dict, Optional
import time

import psutil
import win32com.client


def get_process_dict() -> Dict[int, Dict[str, Optional[str]]]:
    locator = win32com.client.Dispatch("WbemScripting.SWbemLocator")
    svc = locator.ConnectServer(".", "root\\cimv2")

    query = "SELECT ProcessId, Name, CommandLine FROM Win32_Process"
    processes: Dict[int, Dict[str, Optional[str]]] = {}

    for p in svc.ExecQuery(query):
        pid = int(p.ProcessId)
        processes[pid] = {
            "pid": pid,
            "name": str(p.Name) if p.Name is not None else None,
            "cmdline": str(p.CommandLine) if getattr(p, "CommandLine", None) is not None else None,
        }

    return processes


def wait_for_process(pid: int):
    """
    Wait for the process with the given PID to finish.
    :param pid: int, PID of the process to wait for.
    :return:
    """
    try:
        # Create a process object for the given PID
        process = psutil.Process(pid)

        # Wait for the process to terminate
        while process.is_running():
            print(f"Process with PID {pid} is still running...")
            time.sleep(1)  # Sleep for 1 second before checking again

        # Refresh process status and get the exit code
        process.wait()
        print(f"Process with PID [{pid}] has finished.")
    except psutil.NoSuchProcess:
        print(f"No process found with PID {pid}")
    except psutil.AccessDenied:
        print(f"Access denied to process with PID {pid}")