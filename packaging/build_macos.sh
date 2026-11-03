#!/bin/zsh
# Build a Synapse Complete .dmg for this Mac's architecture.
#
#   packaging/build_macos.sh <llama dir> <fastembed cache> <model file> <gemma terms file>
#
# The llama folder comes from build_llama_macos.sh. CI will fetch and verify the models from
# packaging/models.lock.yaml. This stops if the result is above the 1.9 GiB limit.
set -euo pipefail
setopt null_glob
ROOT=${0:A:h:h}
LLAMA_DIR=${1:A}; EMBEDDING_DIR=${2:A}; MODEL_FILE=${3:A}; GEMMA_TERMS=${4:A}
LIMIT_BYTES=$((1900 * 1024 * 1024 * 1024 / 1000))
MIN_MACOS=14.0  # sqlite-vec and onnxruntime have no wheels for anything older.

MODEL_SHA=$(sed -n 's/^ *sha256: //p' "$ROOT/packaging/models.lock.yaml")
[[ "$(shasum -a 256 "$MODEL_FILE" | cut -d' ' -f1)" == "$MODEL_SHA" ]] || { echo "Model file does not match models.lock.yaml"; exit 1; }
[[ "$(head -c 18 "$GEMMA_TERMS")" == "Gemma Terms of Use" ]] || { echo "Not the Gemma terms: $GEMMA_TERMS"; exit 1; }

cd "$ROOT/apps/desktop"
flutter build macos --release
APP="$ROOT/apps/desktop/build/macos/Build/Products/Release/synapse_desktop.app"
RES="$APP/Contents/Resources/engine"
rm -rf "$RES"; mkdir -p "$RES/models"

# The Python runtime, without its test suite and other parts the engine never uses.
PYTHON_HOME=$(uv python find --managed-python 3.13 | xargs dirname | xargs dirname)
cp -R "${PYTHON_HOME:A}" "$RES/python"  # :A because uv's folder for 3.13 is itself a link
rm -rf "$RES"/python/lib/python3.13/test "$RES"/python/lib/python3.13/idlelib \
  "$RES"/python/lib/python3.13/tkinter "$RES"/python/lib/python3.13/turtledemo \
  "$RES"/python/lib/tcl* "$RES"/python/lib/tk* "$RES"/python/lib/itcl* "$RES"/python/include

# The engine and its locked dependencies, without development tools.
cd "$ROOT/engine"
uv export --quiet --frozen --no-dev --no-emit-project --no-hashes -o "$RES/requirements.txt"
# The platform and target choose wheels for our minimum macOS, not for this computer's version.
MACOSX_DEPLOYMENT_TARGET=$MIN_MACOS uv pip install --quiet --python "$RES/python/bin/python3" \
  --python-platform aarch64-apple-darwin --target "$RES/site-packages" \
  --no-compile -r "$RES/requirements.txt"
cp -R src/synapse_engine "$RES/site-packages/synapse_engine"
rm -rf "$RES/requirements.txt" "$RES/site-packages/bin"  # bin holds scripts naming this computer's Python
find "$RES" -type d -name __pycache__ -prune -exec rm -rf {} +
# Compiled now, because the signed app must not write into itself and each launch would pay for it.
"$RES/python/bin/python3" -I -m compileall -q "$RES/site-packages" "$RES/python/lib/python3.13" >/dev/null || true

cp -R "$LLAMA_DIR" "$RES/llama"
mkdir -p "$RES/models/embedding"
# -L copies real files, because the model cache keeps its weights behind symlinks.
cp -RL "$EMBEDDING_DIR"/models--Qdrant--bge-small-en-v1.5-onnx-Q "$RES/models/embedding/"
mkdir -p "$RES/models/ai"
cp "$MODEL_FILE" "$RES/models/ai/gemma-3-1b-Q4_K_M.gguf"
# ADR 0017: Gemma may be redistributed only with its terms and this notice.
cp "$GEMMA_TERMS" "$RES/models/ai/GEMMA_TERMS_OF_USE.txt"
cp "$ROOT/packaging/GEMMA_NOTICE.txt" "$RES/models/ai/NOTICE.txt"

# ADR 0019: nothing bundled may carry Microsoft's telemetry address.
if find "$RES/site-packages" "$RES/python/lib" -type f \( -name '*.so' -o -name '*.dylib' \) -print0 | xargs -0 grep -l 'events.data.microsoft.com'; then
  echo "A bundled library contains telemetry. See ADR 0019."; exit 1
fi

# Nothing bundled may need a newer macOS than the app says it supports.
find "$RES" -type f \( -name '*.so' -o -name '*.dylib' -o -name llama-server \) | while read -r library; do
  needs=$(otool -l "$library" | awk '/LC_BUILD_VERSION/{b=1} b&&/minos/{print $2; exit}')
  if [[ -n "$needs" && "$(printf '%s\n%s\n' "$MIN_MACOS" "$needs" | sort -t. -k1,1n -k2,2n | tail -1)" != "$MIN_MACOS" ]]; then
    echo "$library needs macOS $needs, above $MIN_MACOS"; exit 1
  fi
done

# Every link must stay inside the bundle, or the app only works on the computer that built it.
find "$RES" -type l | while read -r link; do
  target=${link:A}
  if [[ "$(readlink "$link")" == /* || ! -e "$target" || "$target" != "${RES:A}"/* ]]; then
    echo "Link leaves the bundle or is broken: $link -> $target"; exit 1
  fi
done

# Apple Silicon refuses to run unsigned programs. This is an ad-hoc signature, not a Developer ID,
# so the first-launch warning in ADR 0013 still appears.
codesign --force --deep --sign - "$APP"
codesign --verify "$APP"

DMG="$ROOT/apps/desktop/build/Synapse-Complete-macos-$(uname -m).dmg"
rm -f "$DMG"
hdiutil create -quiet -volname Synapse -srcfolder "$APP" -ov -format UDZO "$DMG"
SIZE=$(stat -f%z "$DMG")
echo "app: $(du -sh "$APP" | cut -f1)  dmg: $((SIZE / 1048576)) MB  at $DMG"
if (( SIZE > LIMIT_BYTES )); then echo "Above the 1.9 GiB limit"; exit 1; fi
