"""Test process handling with a small stand-in program, because real Ollama is large."""

from __future__ import annotations

import asyncio
import stat
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from synapse_engine.adapters.ai.ollama_process import OllamaProcess, OllamaUnavailableError

FAKE = f"""#!{sys.executable}
import http.server, json, os
host, port = os.environ["OLLAMA_HOST"].split(":")
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps(dict(os.environ)).encode()
        self.send_response(200); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
http.server.HTTPServer((host, int(port)), H).serve_forever()
"""


def program(tmp_path: Path, source: str = FAKE) -> Path:
    path = tmp_path / "ollama"
    path.write_text(source)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def subject(tmp_path: Path, binary: Path) -> OllamaProcess:
    return OllamaProcess(binary, tmp_path / "models", tmp_path / "ollama.pid")


async def test_starts_once_privately_and_without_proxy_settings(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:9")
    ollama = subject(tmp_path, program(tmp_path))
    try:
        url = await ollama.ensure_started()
        assert await ollama.ensure_started() == url
        async with httpx.AsyncClient(trust_env=False) as client:
            seen = (await client.get(f"{url}/api/version")).json()
        assert seen["OLLAMA_NO_CLOUD"] == "1"
        assert seen["OLLAMA_MODELS"] == str(tmp_path / "models")
        assert "HTTP_PROXY" not in seen
        assert "https_proxy" not in seen
        assert (tmp_path / "ollama.pid").is_file()
    finally:
        ollama.stop()
    assert not (tmp_path / "ollama.pid").exists()


async def test_missing_program_is_explained(tmp_path) -> None:
    with pytest.raises(OllamaUnavailableError, match="missing"):
        await subject(tmp_path, tmp_path / "gone").ensure_started()


async def test_program_that_dies_fails_quickly(tmp_path) -> None:
    ollama = subject(tmp_path, program(tmp_path, f"#!{sys.executable}\nraise SystemExit(1)\n"))
    started = time.perf_counter()
    with pytest.raises(OllamaUnavailableError, match="stopped"):
        await ollama.ensure_started()
    assert time.perf_counter() - started < 10


async def test_cancelling_a_start_does_not_leave_it_half_started(tmp_path) -> None:
    slow = f"#!{sys.executable}\nimport time\ntime.sleep(60)\n"
    binary = program(tmp_path, slow)
    ollama = subject(tmp_path, binary)
    task = asyncio.create_task(ollama.ensure_started())
    await asyncio.sleep(0.3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert ollama._base_url is None
    assert ollama._process is None


def test_leftover_and_its_runner_are_both_stopped(tmp_path) -> None:
    runner_pid = tmp_path / "runner.pid"
    binary = program(
        tmp_path,
        f"""#!{sys.executable}
import pathlib, subprocess, sys, time
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
pathlib.Path({str(runner_pid)!r}).write_text(str(child.pid))
time.sleep(60)
""",
    )
    old = subprocess.Popen([str(binary), "serve"], start_new_session=True)
    (tmp_path / "ollama.pid").write_text(str(old.pid))
    for _ in range(50):
        if runner_pid.is_file() and runner_pid.read_text():
            break
        time.sleep(0.1)
    runner = int(runner_pid.read_text())
    subject(tmp_path, binary).stop_leftover()
    assert old.wait(timeout=5) != 0
    for _ in range(50):
        state = subprocess.run(
            ["/bin/ps", "-p", str(runner), "-o", "state="], capture_output=True, text=True
        ).stdout.strip()
        if not state or state.startswith("Z"):
            return
        time.sleep(0.1)
    raise AssertionError("The runner was left behind")


def test_unrelated_process_with_a_reused_id_is_left_alone(tmp_path) -> None:
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        (tmp_path / "ollama.pid").write_text(str(other.pid))
        subject(tmp_path, tmp_path / "ollama").stop_leftover()
        time.sleep(0.2)
        assert other.poll() is None
    finally:
        other.kill()
        other.wait()


def test_corrupt_pid_file_is_ignored(tmp_path) -> None:
    (tmp_path / "ollama.pid").write_text("not a number")
    subject(tmp_path, tmp_path / "ollama").stop_leftover()
    assert not (tmp_path / "ollama.pid").exists()
