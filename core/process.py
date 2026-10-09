"""Run external commands with bounded waits and cooperative cancellation."""

import subprocess
import sys
import time
from typing import Callable, Optional, Sequence


def run_process(
    command: Sequence[str],
    *,
    timeout: float,
    cancel_check: Optional[Callable[[], bool]] = None,
    check: bool = True,
    capture_stdout: bool = False,
) -> subprocess.CompletedProcess:
    """Run a command, terminate it on cancellation/timeout, and always reap it."""
    no_window = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        list(command),
        stdout=subprocess.PIPE if capture_stdout else subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=no_window,
    )
    started_at = time.monotonic()

    def stop_process() -> tuple[str, str]:
        if proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                # The process may exit between poll() and terminate().
                pass
            try:
                return proc.communicate(timeout=2.0)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except OSError:
                    # The process may exit between timeout and kill().
                    pass
        return proc.communicate()

    while True:
        if cancel_check and cancel_check():
            stop_process()
            raise InterruptedError("The operation was cancelled by the user.")

        remaining = timeout - (time.monotonic() - started_at)
        if remaining <= 0:
            stdout, stderr = stop_process()
            raise TimeoutError(
                f"Command timed out after {timeout:.1f}s: {stderr[-500:] if stderr else command[0]}"
            )

        try:
            stdout, stderr = proc.communicate(timeout=min(0.25, remaining))
            break
        except subprocess.TimeoutExpired:
            continue

    result = subprocess.CompletedProcess(command, proc.returncode, stdout, stderr)
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, command, output=stdout, stderr=stderr)
    return result
