"""Start the engine: read the token, bind a free port, report it, and run until stdin closes."""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time

import uvicorn

from synapse_engine.composition import build_app
from synapse_engine.settings import Settings

_GRACEFUL_SECONDS = 5
# Worker threads can outlast uvicorn, so the process is ended if it has not gone by then.
_FORCE_EXIT_SECONDS = 10


def main() -> None:
    """Run the engine as the desktop app's child process."""
    token = sys.stdin.readline().strip()
    if not token:
        sys.exit("A token is required on stdin.")
    # Binding before uvicorn starts means there is no gap in which a port could be taken.
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    app = build_app(Settings.from_environment(), token)
    config = uvicorn.Config(
        app,
        log_level="warning",
        access_log=False,
        timeout_graceful_shutdown=_GRACEFUL_SECONDS,
    )
    server = uvicorn.Server(config)

    def stop_when_parent_exits() -> None:
        sys.stdin.read()
        server.should_exit = True
        time.sleep(_FORCE_EXIT_SECONDS)
        app.state.stop_children()
        os._exit(0)

    threading.Thread(target=stop_when_parent_exits, daemon=True).start()
    print(json.dumps({"event": "ready", "port": port}), flush=True)
    server.run(sockets=[sock])


if __name__ == "__main__":
    main()
