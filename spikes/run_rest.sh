#!/bin/zsh
# Runs the remaining measurements one after another, so they do not skew each other's timings.
cd "$(dirname "$0")"
while pgrep -f "python -u bench_retrieval" >/dev/null; do /bin/sleep 20; done
HF_HUB_DISABLE_TELEMETRY=1 .venv/bin/python -u bench_weights.py > results/raw/weights.log 2>&1
.venv/bin/python -u bench_llm.py qwen2.5:0.5b qwen3:0.6b granite4:350m gemma3:1b qwen2.5:1.5b > results/raw/llm.log 2>&1
