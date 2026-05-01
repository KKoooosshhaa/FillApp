from __future__ import annotations

import socket
import subprocess
import time
from os import environ
from pathlib import Path


DEFAULT_CHROME_PATH = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
DEFAULT_DEBUG_PROFILE = Path(environ.get("LOCALAPPDATA", str(Path.home()))) / "FillApp" / "chrome_debug_profile"
DEFAULT_DEBUG_PORT = 9222


def is_debug_port_open(port: int = DEFAULT_DEBUG_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def launch_chrome_debug(
    chrome_path: Path = DEFAULT_CHROME_PATH,
    profile_dir: Path = DEFAULT_DEBUG_PROFILE,
    port: int = DEFAULT_DEBUG_PORT,
) -> subprocess.Popen:
    if not chrome_path.exists():
        raise FileNotFoundError(f"Chrome was not found at {chrome_path}")

    if is_debug_port_open(port):
        raise RuntimeError(
            f"Port {port} is already open. Close the existing debug Chrome window, "
            "or use the browser that is already open."
        )

    profile_dir.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen(
        [
            str(chrome_path),
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--new-window",
            "--disable-background-mode",
            "about:blank",
        ],
    )


def chrome_launch_command(
    chrome_path: Path = DEFAULT_CHROME_PATH,
    profile_dir: Path = DEFAULT_DEBUG_PROFILE,
    port: int = DEFAULT_DEBUG_PORT,
) -> str:
    return (
        f'& "{chrome_path}" '
        f"--remote-debugging-port={port} "
        f'--user-data-dir="{profile_dir}" '
        "--no-first-run --new-window about:blank"
    )


def wait_for_debug_port(process: subprocess.Popen, port: int = DEFAULT_DEBUG_PORT, timeout_seconds: float = 8.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if is_debug_port_open(port):
            return
        exit_code = process.poll()
        if exit_code is not None:
            raise RuntimeError(f"Chrome exited immediately with code {exit_code}.")
        time.sleep(0.25)
    raise RuntimeError(f"Chrome started, but port {port} did not open within {timeout_seconds:.0f} seconds.")
