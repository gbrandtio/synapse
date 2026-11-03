"""Test process handling with a small stand-in program, because the real server needs a large model."""

from __future__ import annotations

import asyncio
import stat
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from synapse_engine.adapters.ai.llama_process import LlamaProcess, LocalAiUnavailableError

FAKE = f"""#!{sys.executable}
import http.server, json, os, sys
host = sys.argv[sys.argv.index("--host") + 1]
port = sys.argv[sys.argv.index("--port") + 1]
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps(dict(env=dict(os.environ), args=sys.argv)).encode()
        self.send_response(200); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
http.server.HTTPServer((host, int(port)), H).serve_forever()
"""


def program(tmp_path: Path, source: str = FAKE) -> Path:
    path = tmp_path / "llama-server"
    path.write_text(source)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def subject(tmp_path: Path, binary: Path) -> LlamaProcess:
    model = tmp_path / "model.gguf"
    model.touch()
    return LlamaProcess(binary, model, tmp_path / "llama.pid", 8192)


async def test_starts_once_privately_and_without_proxy_settings(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:9")
    llama = subject(tmp_path, program(tmp_path))
    try:
        url = await llama.ensure_started()
        assert await llama.ensure_started() == url
        async with httpx.AsyncClient(trust_env=False) as client:
            seen = (await client.get(f"{url}/health")).json()
        args, env = seen["args"], seen["env"]
        assert args[args.index("--model") + 1] == str(tmp_path / "model.gguf")
        assert args[args.index("--host") + 1] == "127.0.0.1"
        assert args[args.index("--ctx-size") + 1] == "8192"
        assert args[args.index("--parallel") + 1] == "1"
        assert "--offline" in args
        assert llama.api_key not in " ".join(args)
        assert env["LLAMA_API_KEY"] == llama.api_key
        assert "HTTP_PROXY" not in env
        assert "https_proxy" not in env
        assert (tmp_path / "llama.pid").is_file()
    finally:
        llama.stop()
    assert not (tmp_path / "llama.pid").exists()


async def test_missing_program_is_explained(tmp_path) -> None:
    with pytest.raises(LocalAiUnavailableError, match="missing"):
        await subject(tmp_path, tmp_path / "gone").ensure_started()


async def test_missing_model_is_explained(tmp_path) -> None:
    llama = LlamaProcess(program(tmp_path), tmp_path / "gone.gguf", tmp_path / "llama.pid", 8192)
    with pytest.raises(LocalAiUnavailableError, match="missing"):
        await llama.ensure_started()


async def test_program_that_dies_fails_quickly(tmp_path) -> None:
    llama = subject(tmp_path, program(tmp_path, f"#!{sys.executable}\nraise SystemExit(1)\n"))
    started = time.perf_counter()
    with pytest.raises(LocalAiUnavailableError, match="stopped"):
        await llama.ensure_started()
    assert time.perf_counter() - started < 10


async def test_falls_back_to_cpu_when_the_gpu_start_crashes(tmp_path) -> None:
    gpu_crashes = FAKE.replace(
        "import http.server, json, os, sys\n",
        "import http.server, json, os, sys\n"
        'if os.environ.get("GGML_METAL_DEVICES") != "0": raise SystemExit(1)\n',
    )
    llama = subject(tmp_path, program(tmp_path, gpu_crashes))
    try:
        url = await llama.ensure_started()
        async with httpx.AsyncClient(trust_env=False) as client:
            assert (await client.get(f"{url}/health")).is_success
    finally:
        llama.stop()


async def test_cancelling_a_start_does_not_leave_it_half_started(tmp_path) -> None:
    slow = f"#!{sys.executable}\nimport time\ntime.sleep(60)\n"
    binary = program(tmp_path, slow)
    llama = subject(tmp_path, binary)
    task = asyncio.create_task(llama.ensure_started())
    await asyncio.sleep(0.3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert llama._base_url is None
    assert llama._process is None


def test_leftover_and_its_process_group_are_both_stopped(tmp_path) -> None:
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
    old = subprocess.Popen([str(binary), "--model", "x"], start_new_session=True)
    (tmp_path / "llama.pid").write_text(str(old.pid))
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
        (tmp_path / "llama.pid").write_text(str(other.pid))
        subject(tmp_path, tmp_path / "llama-server").stop_leftover()
        time.sleep(0.2)
        assert other.poll() is None
    finally:
        other.kill()
        other.wait()


def test_corrupt_pid_file_is_ignored(tmp_path) -> None:
    (tmp_path / "llama.pid").write_text("not a number")
    subject(tmp_path, tmp_path / "llama-server").stop_leftover()
    assert not (tmp_path / "llama.pid").exists()
