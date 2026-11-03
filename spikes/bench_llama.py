"""Repeat the bench_llm.py checks through the bundled llama.cpp server instead of Ollama.

Run: uv run python bench_llama.py <llama-server> <model file> [server arguments...]
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

from bench_llm import EXTRACT, FILTER_SCHEMA, FILTERS, QA, SCHEMA, SYSTEM

PORT = 18768
URL = f"http://127.0.0.1:{PORT}"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def chat(messages: list[dict], **extra: object) -> dict:
    body = {"messages": messages, "temperature": 0.2, "max_tokens": 300, **extra}
    request = urllib.request.Request(f"{URL}/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with OPENER.open(request, timeout=300) as response:
        return json.load(response)


def schema(value: dict) -> dict:
    return {"response_format": {"type": "json_schema", "json_schema": {"name": "x", "schema": value}}}


def main(binary: str, model: str, *arguments: str) -> None:
    server = subprocess.Popen(
        [binary, "--model", model, "--host", "127.0.0.1", "--port", str(PORT), "--ctx-size", "8192", "--parallel", "1", "--jinja", "--no-webui", "--offline", *arguments],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(480):
            try:
                if OPENER.open(f"{URL}/health", timeout=1).status == 200:
                    break
            except (urllib.error.URLError, OSError):
                time.sleep(0.25)
        qa, speeds, fails = 0, [], []
        for question, passages, must, must_not in QA:
            reply = chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Passages:\n{passages}\n\nQuestion: {question}"}])
            text = reply["choices"][0]["message"]["content"]
            low = text.lower().replace("’", "'")
            ok = all(m in low for m in must) and not any(m in low for m in must_not)
            qa += ok
            speeds.append(reply["timings"]["predicted_per_second"])
            if not ok:
                fails.append({"q": question, "a": text[:140]})
        extraction = 0
        for text, want in EXTRACT:
            reply = chat([{"role": "user", "content": f"Extract the fields from this ticket as JSON.\n{text}"}], **schema(SCHEMA))
            got = json.loads(reply["choices"][0]["message"]["content"])
            extraction += all(str(got.get(k, "")).lower().strip() == v for k, v in want.items())
        filters = 0
        for text, want in FILTERS:
            reply = chat([{"role": "user", "content": f"Turn this question into filters. Use null when not mentioned.\n{text}"}], **schema(FILTER_SCHEMA))
            got = json.loads(reply["choices"][0]["message"]["content"])
            filters += all((str(got.get(k)).lower() if v is not None else got.get(k)) == v for k, v in want.items())
        print(json.dumps({"arguments": arguments, "qa": f"{qa}/{len(QA)}", "extraction": f"{extraction}/{len(EXTRACT)}", "filters": f"{filters}/{len(FILTERS)}", "tokens_per_s": round(sum(speeds) / len(speeds), 1), "qa_failures": fails}, indent=1))
    finally:
        server.terminate()
        server.wait()


if __name__ == "__main__":
    main(*sys.argv[1:])
