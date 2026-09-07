"""Launch the local server and open Jerome's Laboratory in a browser."""

from __future__ import annotations

import os
import socket
import threading
import time
import urllib.error
import urllib.request
import webbrowser

import uvicorn

from jeromes_laboratory.api.main import app
from jeromes_laboratory.storage.workspace import WorkspaceLocationError

HOST = "127.0.0.1"


def find_available_port() -> int:
    """Ask the operating system for an available loopback TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((HOST, 0))
        return int(listener.getsockname()[1])


def get_launch_port() -> int:
    """Return a test override or choose an available loopback port."""
    configured_port = os.environ.get("JEROMES_LABORATORY_PORT")
    if configured_port is None:
        return find_available_port()

    port = int(configured_port)
    if not 1 <= port <= 65535:
        raise ValueError("JEROMES_LABORATORY_PORT must be between 1 and 65535")
    return port


def open_browser_when_ready(url: str, health_url: str) -> None:
    """Open the browser after the local API begins accepting requests."""
    for _ in range(100):
        try:
            with urllib.request.urlopen(health_url, timeout=0.25) as response:
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)


def main() -> None:
    """Run the application on loopback while keeping terminal logs visible."""
    try:
        app.state.workspace_service.initialize_configured_workspace()
    except WorkspaceLocationError as error:
        raise SystemExit(f"Workspace initialization failed: {error}") from error

    port = get_launch_port()
    application_url = f"http://{HOST}:{port}"
    health_url = f"{application_url}/api/health"
    if os.environ.get("JEROMES_LABORATORY_NO_BROWSER") != "1":
        browser_thread = threading.Thread(
            target=open_browser_when_ready,
            args=(application_url, health_url),
            daemon=True,
        )
        browser_thread.start()
    uvicorn.run(app, host=HOST, port=port)


if __name__ == "__main__":
    main()
