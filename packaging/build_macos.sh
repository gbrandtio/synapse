#!/bin/zsh
# Build a Synapse Complete .dmg for this Mac's architecture.
#
#   packaging/build_macos.sh <ollama dir> <fastembed cache> <ollama models dir>
#
# The three folders hold the trimmed Ollama and the bundled models. CI will fetch and verify
# them from packaging/models.lock.yaml. This stops if the result is above the 1.9 GiB limit.
set -euo pipefail
setopt null_glob
ROOT=${0:A:h:h}
OLLAMA_DIR=${1:A}; EMBEDDING_DIR=${2:A}; MODELS_DIR=${3:A}
LIMIT_BYTES=$((1900 * 1024 * 1024 * 1024 / 1000))

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
uv pip install --quiet --python "$RES/python/bin/python3" --target "$RES/site-packages" \
  --no-compile -r "$RES/requirements.txt"
cp -R src/synapse_engine "$RES/site-packages/synapse_engine"
rm -rf "$RES/requirements.txt" "$RES/site-packages/bin"  # bin holds scripts naming this computer's Python
find "$RES" -type d -name __pycache__ -prune -exec rm -rf {} +
# Compiled now, because the signed app must not write into itself and each launch would pay for it.
"$RES/python/bin/python3" -I -m compileall -q "$RES/site-packages" "$RES/python/lib/python3.13" >/dev/null || true

cp -R "$OLLAMA_DIR" "$RES/ollama"
mkdir -p "$RES/models/embedding"
# -L copies real files, because the model cache keeps its weights behind symlinks.
cp -RL "$EMBEDDING_DIR"/models--Qdrant--bge-small-en-v1.5-onnx-Q "$RES/models/embedding/"
cp -R "$MODELS_DIR" "$RES/models/ollama"

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
