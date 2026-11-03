"""Run the assembled bundle as the app does: token on stdin, port on stdout, then a real question.

Run with this Python's -I flag, passing the bundle's engine folder, a PDF and a data folder. It
reports any connection the engine or Ollama opens to another computer.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

res, pdf, data = (Path(a) for a in sys.argv[1:4])
QUESTIONS = ["How long are backups kept?", "Which firmware fixes the PX-400 printer?", "What is the capital of Australia?"]
env = {
    "PATH": "/usr/bin:/bin", "HOME": str(data), "SYNAPSE_DATA_DIR": str(data),
    "SYNAPSE_EMBEDDING_DIR": str(res / "models/embedding"), "SYNAPSE_OLLAMA_BIN": str(res / "ollama/ollama"),
    "SYNAPSE_OLLAMA_MODELS": str(res / "models/ollama"), "HF_HUB_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1", "PYTHONDONTWRITEBYTECODE": "1",
    # A closed port. If anything used these, every answer would fail.
    "HTTP_PROXY": "http://127.0.0.1:9", "ALL_PROXY": "http://127.0.0.1:9", "http_proxy": "http://127.0.0.1:9",
}
boot = f"import sys; sys.path.insert(0, {str(res / 'site-packages')!r}); from synapse_engine.__main__ import main; main()"
start = time.perf_counter()
p = subprocess.Popen([str(res / "python/bin/python3"), "-I", "-c", boot], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=env)
p.stdin.write("tok\n"); p.stdin.flush()
port = json.loads(p.stdout.readline())["port"]
print(f"ready on 127.0.0.1 in {time.perf_counter() - start:.1f}s")
outside: set[str] = set()
stop = threading.Event()


def watch() -> None:
    while not stop.is_set():
        pids = subprocess.run(["pgrep", "-g", str(os.getpgid(p.pid))], capture_output=True, text=True).stdout.split()
        kids = subprocess.run(["pgrep", "-P", str(p.pid)], capture_output=True, text=True).stdout.split()
        for pid in {str(p.pid), *kids}:
            out = subprocess.run(["lsof", "-nP", "-a", "-p", pid, "-i"], capture_output=True, text=True).stdout
            for line in out.splitlines()[1:]:
                name = line.split()[8] if len(line.split()) > 8 else ""
                if "->" in name and "127.0.0.1" not in name.split("->")[1]:
                    outside.add(f"{line.split()[0]} {name}")
        time.sleep(0.2)


threading.Thread(target=watch, daemon=True).start()


def call(path: str, body: dict) -> list[tuple[str, dict]]:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", json.dumps(body).encode(), {"Authorization": "Bearer tok", "Content-Type": "application/json"})
    out, name = [], None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=300) as r:
        for raw in r:
            line = raw.decode().strip()
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:") and name:
                out.append((name, json.loads(line[5:]))); name = None
    return out


t = time.perf_counter()
added = call("/documents", {"path": str(pdf)})
print(f"ingest {time.perf_counter() - t:.1f}s ->", added[-1])
for q in QUESTIONS:
    t = time.perf_counter()
    ev = call("/ask", {"question": q})
    text = "".join(d["text"] for k, d in ev if k == "token")
    other = [(k, d if k != "citations" else [(c["document_name"], c["page"], c["is_inferred"]) for c in d["citations"]]) for k, d in ev if k != "token"]
    print(f"{time.perf_counter() - t:.1f}s Q: {q}\n   A: {text.strip()}\n   {other}")
time.sleep(5)
stop.set()
p.stdin.close()
code = p.wait(timeout=20)
time.sleep(1)
left = subprocess.run(["pgrep", "-f", str(res)], capture_output=True, text=True).stdout.split()
print("engine exit code", code, "| processes left", left, "| outside connections", sorted(outside) or "none seen")
