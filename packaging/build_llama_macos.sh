#!/bin/zsh
# Build the pinned llama.cpp server that Synapse Complete bundles.
#
#   packaging/build_llama_macos.sh <empty work folder> <output folder>
#
# HTTPS, the web page and the tools that run other programs are left out, because Synapse never
# needs them. Everything is linked statically, so only system libraries are needed.
set -euo pipefail
TAG=v0.8.0
COMMIT=8642541b255bfb5dc39cd351a178be09013a55d6
WORK=${1:A}; OUT=${2:A}

[[ -d "$WORK/src" ]] || git clone --quiet --depth 1 --branch "$TAG" https://github.com/ggml-org/llama.cpp "$WORK/src"
[[ "$(git -C "$WORK/src" rev-parse HEAD)" == "$COMMIT" ]] || { echo "Source is not $TAG at the pinned commit"; exit 1; }

# Metal rejects this file on macOS 15, which stops the whole GPU backend. These functions call
# conversions that cannot be constant, so `constexpr` is simply wrong here. v0.8.0 still has it.
sed -i '' 's/inline constexpr/inline/' "$WORK/src/ggml/src/ggml-metal/kernels/unary.metal"
if grep -q constexpr "$WORK/src/ggml/src/ggml-metal/kernels/unary.metal"; then echo "Patch did not apply"; exit 1; fi

cmake -S "$WORK/src" -B "$WORK/build" -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_SHARED_LIBS=OFF -DCMAKE_OSX_DEPLOYMENT_TARGET=13.3 \
  -DLLAMA_OPENSSL=OFF -DLLAMA_SUBPROCESS=OFF -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF \
  -DLLAMA_CONNECT=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_APP=OFF \
  -DLLAMA_BUILD_SERVER=ON -DLLAMA_BUILD_TOOLS=ON \
  -DGGML_NATIVE=OFF -DGGML_CPU_ARM_ARCH=armv8.2-a+dotprod+fp16 >/dev/null  # Runs on every Apple Silicon chip, not just this one.
cmake --build "$WORK/build" --target llama-server --parallel >/dev/null

mkdir -p "$OUT"
cp "$WORK/build/bin/llama-server" "$OUT/llama-server"
strip -x "$OUT/llama-server"
cp "$WORK/src/LICENSE" "$OUT/LLAMA_CPP_LICENSE"
cp -R "$WORK/src/licenses" "$OUT/licenses"  # Notices of libraries built into the program.
cp "$WORK/src/vendor/cpp-httplib/LICENSE" "$OUT/licenses/LICENSE-cpp-httplib"
ls -l "$OUT"
otool -L "$OUT/llama-server"
