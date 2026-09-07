"""Launch the local server and open Jerome's Laboratory in a browser."""

from __future__ import annotations

import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
import webbrowser

import uvicorn

from jeromes_laboratory.api.main import app
from jeromes_laboratory.launcher.instance import InstanceCoordinator, RunningInstance
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


def instance_is_healthy(instance: RunningInstance) -> bool:
    """Confirm that a record belongs to the responding local application."""
    health_url = f"http://{HOST}:{instance.port}/api/health"
    try:
        with urllib.request.urlopen(health_url, timeout=0.25) as response:
            content = json.loads(response.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, urllib.error.URLError):
        return False
    return (
        response.status == 200
        and isinstance(content, dict)
        and content.get("instance_id") == instance.instance_id
    )


def open_browser_when_ready(url: str, instance: RunningInstance) -> None:
    """Open the browser after the local API begins accepting requests."""
    for _ in range(100):
        try:
            if instance_is_healthy(instance):
                webbrowser.open(url)
                return
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)


def main() -> None:
    """Run the application on loopback while keeping terminal logs visible."""
    try:
        app.state.workspace_service.initialize_configured_workspace()
    except WorkspaceLocationError as error:
        print(f"Workspace recovery required: {error}")

    port = get_launch_port()
    application_url = f"http://{HOST}:{port}"
    coordinator = InstanceCoordinator(health_checker=instance_is_healthy)
    claim = coordinator.claim(port)
    if not claim.owns_instance:
        if os.environ.get("JEROMES_LABORATORY_NO_BROWSER") != "1":
            open_browser_when_ready(f"http://{HOST}:{claim.instance.port}", claim.instance)
        return

    app.state.instance_id = claim.instance.instance_id
    if os.environ.get("JEROMES_LABORATORY_NO_BROWSER") != "1":
        browser_thread = threading.Thread(
            target=open_browser_when_ready,
            args=(application_url, claim.instance),
            daemon=True,
        )
        browser_thread.start()
    try:
        uvicorn.run(app, host=HOST, port=port)
    finally:
        coordinator.release(claim.instance.instance_id)
        app.state.instance_id = None


if __name__ == "__main__":
    main()
