"""Start the real engine as the app would, without any AI models."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import httpx


def start(tmp_path) -> subprocess.Popen[str]:
    env = {**os.environ, "SYNAPSE_DATA_DIR": str(tmp_path)}
    return subprocess.Popen(
        [sys.executable, "-m", "synapse_engine"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )


def test_handshake_auth_and_exit_when_parent_goes_away(tmp_path) -> None:
    process = start(tmp_path)
    try:
        process.stdin.write("launch-token\n")
        process.stdin.flush()
        ready = json.loads(process.stdout.readline())
        assert ready["event"] == "ready"
        base = f"http://127.0.0.1:{ready['port']}"
        with httpx.Client(trust_env=False) as client:
            for _ in range(50):
                try:
                    client.get(base + "/health")
                    break
                except httpx.TransportError:
                    time.sleep(0.1)
            assert client.get(base + "/health").status_code == 401
            ok = client.get(base + "/health", headers={"Authorization": "Bearer launch-token"})
            assert ok.json() == {"status": "ok"}
        process.stdin.close()
        assert process.wait(timeout=15) == 0
    finally:
        process.kill()
        process.stdout.close()
        process.stderr.close()


def test_refuses_to_start_without_a_token(tmp_path) -> None:
    process = start(tmp_path)
    try:
        process.stdin.close()
        assert process.wait(timeout=15) != 0
    finally:
        process.kill()
        process.stdout.close()
        process.stderr.close()
