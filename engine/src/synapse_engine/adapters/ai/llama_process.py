"""Runs the bundled llama.cpp server as a private child process."""

from __future__ import annotations

import asyncio
import os
import secrets
import signal
import socket
import subprocess
from pathlib import Path

import httpx

_START_TIMEOUT_SECONDS = 120  # The model loads before the server reports ready.
_IDLE_SECONDS = 300  # Then it frees the model's memory, and reloads it on the next question.
_PROXY_VARIABLES = {
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
}


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class LocalAiUnavailableError(Exception):
    """The local AI could not start. The message is safe to show the user."""


class _StartupCrashError(Exception):
    """The server exited before it became ready."""


class LlamaProcess:
    """Starts the server on a private port, on first use, with a key only this engine knows.

    If the engine is killed outright, the server keeps running. Its process ID is saved in
    `pid_file`, so the next start can stop it. Windows does not do this yet.
    """

    def __init__(self, binary: Path, model_file: Path, pid_file: Path, context_tokens: int) -> None:
        self.api_key = secrets.token_urlsafe(32)
        self._binary = binary
        self._model_file = model_file
        self._pid_file = pid_file
        self._context_tokens = context_tokens
        self._process: subprocess.Popen[bytes] | None = None
        self._base_url: str | None = None
        self._lock = asyncio.Lock()

    async def ensure_started(self) -> str:
        """Return the base URL, starting the server if it is not already running."""
        async with self._lock:
            if self._process is not None and self._process.poll() is None and self._base_url:
                return self._base_url
            self._base_url = None
            return await self._start()

    async def _start(self) -> str:
        parts = (self._binary, self._model_file)
        if not all(await asyncio.gather(*(asyncio.to_thread(p.is_file) for p in parts))):
            raise LocalAiUnavailableError("The local AI is missing from this installation.")
        await asyncio.to_thread(self.stop_leftover)
        try:
            return await self._launch()
        except _StartupCrashError:
            # A macOS version can reject the GPU code, which stops the server at once.
            try:
                return await self._launch(gpu=False)
            except _StartupCrashError as error:
                raise LocalAiUnavailableError(str(error)) from error

    async def _launch(self, *, gpu: bool = True) -> str:
        port = _free_port()
        environment = {k: v for k, v in os.environ.items() if k not in _PROXY_VARIABLES}
        # Not an argument, so process lists don't show it.
        environment["LLAMA_API_KEY"] = self.api_key
        if not gpu:
            # `--device none` is not enough, because the GPU code is built before it is read.
            environment["GGML_METAL_DEVICES"] = "0"
        self._process = subprocess.Popen(  # noqa: S603, ASYNC220 - fixed binary, no shell, returns at once
            [
                str(self._binary),
                "--model",
                str(self._model_file),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--ctx-size",
                str(self._context_tokens),
                "--parallel",  # One slot, or the context is shared out and each gets less.
                "1",
                "--jinja",
                "--no-webui",
                "--offline",
                "--sleep-idle-seconds",
                str(_IDLE_SECONDS),
            ],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            # Its own process group, which is what `_signal` and `stop_leftover` signal.
            start_new_session=os.name == "posix",
        )
        await asyncio.to_thread(self._pid_file.write_text, str(self._process.pid))
        base_url = f"http://127.0.0.1:{port}"
        try:
            await self._wait_until_ready(base_url)
        except BaseException:
            await asyncio.shield(asyncio.to_thread(self.stop))
            raise
        self._base_url = base_url
        return base_url

    async def _wait_until_ready(self, base_url: str) -> None:
        async with httpx.AsyncClient(timeout=2, trust_env=False) as client:
            for _ in range(_START_TIMEOUT_SECONDS * 4):
                if self._process is None or self._process.poll() is not None:
                    raise _StartupCrashError("The local AI stopped while starting.")
                try:
                    if (await client.get(f"{base_url}/health")).is_success:
                        return
                except httpx.TransportError:
                    pass
                await asyncio.sleep(0.25)
        raise LocalAiUnavailableError("The local AI did not start in time.")

    def stop_leftover(self) -> None:
        """Stop a server left by an earlier engine, after checking the ID is still that program."""
        if os.name != "posix" or not self._pid_file.is_file():
            return
        try:
            pid = int(self._pid_file.read_text())
            command = subprocess.run(  # noqa: S603 - fixed program, and pid is an integer
                ["/bin/ps", "-p", str(pid), "-o", "command="],
                capture_output=True,
                text=True,
                check=False,
            ).stdout
            if f"{self._binary} --model" in command:
                os.killpg(pid, signal.SIGKILL)
        except (ValueError, ProcessLookupError, PermissionError):
            pass
        self._pid_file.unlink(missing_ok=True)

    def stop(self) -> None:
        """Stop the server if it is running."""
        self._base_url = None
        process, self._process = self._process, None
        self._pid_file.unlink(missing_ok=True)
        if process is None or process.poll() is not None:
            return
        self._signal(process, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._signal(process, signal.SIGKILL)
            process.wait()

    @staticmethod
    def _signal(process: subprocess.Popen[bytes], signal_number: signal.Signals) -> None:
        if os.name == "posix":
            os.killpg(process.pid, signal_number)
        else:
            process.send_signal(signal_number)
