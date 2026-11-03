# 0018. Bundle the llama.cpp server instead of Ollama

- Status: Accepted
- Date: 2026-11-03
- Deciders: Project owner

## Context

Complete must run its AI model offline, and it promises that nothing leaves the computer. Ollama made that promise hard to verify, because it has background tasks of its own, including one scheduled hours after it starts. It also ran as two processes: Ollama itself, and the llama.cpp server it started to hold the model.

## Decision

Complete bundles the llama.cpp server, built from source at a pinned commit (`v0.8.0`) by `packaging/build_llama_macos.sh`. The engine starts it on first use on a private port, with a random key, and talks to it through its OpenAI-compatible API.

The model file is the same Gemma GGUF file that Phase 0 tested, pinned by hash in `packaging/models.lock.yaml`.

The build leaves out HTTPS, the web page and the tools that run other programs. It is also not built for this computer's chip alone, so it can run on every Apple Silicon Mac.

## Consequences

**Size:** the download falls only slightly, because the OpenAI client adds back 23 MB of Python packages. Size was not the reason for this change. It may matter more on Windows, but that is not measured.

**Patch:** Metal rejects one shader file in `v0.8.0` on macOS 15, so the build script removes a wrong `constexpr` from it. Each new llama.cpp version must be checked for this.

**Speed:** with a 3,800-token prompt on an M4, the GPU answered in 2.0 seconds and the CPU in 6.7 seconds. GPU code can still fail on a macOS version we have not tested, so the engine retries on the CPU if the server crashes while starting. `GGML_METAL_DEVICES=0` is needed for this, because `--device none` still starts the GPU code.

**Memory:** the server frees the model after 5 idle minutes, falling from about 950 MB to about 90 MB, and reloads it on the next question.

**Our own work:** we now build and update llama.cpp ourselves. Downloading larger models and switching between them must also be built, because Ollama no longer does it. The option to use a copy of Ollama the user installed themselves can still be added as a separate setting.

**Minimum macOS:** the app now needs macOS 14, because sqlite-vec and onnxruntime have no wheels for anything older. This has only been run on macOS 15.7.

## Alternatives considered

- **Keep Ollama:** it manages models and updates for us, but we could not rule out its network use without a long packet capture, and might have had to block what it found.
- **Use llama.cpp's own downloads:** its release has no usable files, and a third-party fork's notes say its standard Mac build needs macOS 26.
- **CPU only:** this removes the GPU risk, but long prompts take three times as long and use about 500 MB more memory.
