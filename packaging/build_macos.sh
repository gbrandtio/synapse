#!/bin/zsh
# Build a Synapse Complete .dmg for this Mac's architecture.
#
#   packaging/build_macos.sh <llama dir> <models dir>
#
# The llama folder comes from build_llama_macos.sh. Models are downloaded into the models folder if
# needed, and checked against packaging/models.lock.yaml. This stops if the result is above the
# 1.9 GiB limit.
set -euo pipefail
setopt null_glob
ROOT=${0:A:h:h}
LLAMA_DIR=${1:A}; MODELS_DIR=${2:A}
LIMIT_BYTES=$((1900 * 1024 * 1024 * 1024 / 1000))
MIN_MACOS=14.0  # sqlite-vec and onnxruntime have no wheels for anything older.


cd "$ROOT/apps/desktop"
flutter build macos --release
APP="$ROOT/apps/desktop/build/macos/Build/Products/Release/Synapse.app"
RES="$APP/Contents/Resources/engine"
rm -rf "$RES"; mkdir -p "$RES"

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
uv run --no-project --with pyyaml==6.0.3 "$ROOT/packaging/fetch_models.py" "$MODELS_DIR" "$RES/models"
# ADR 0017: Gemma may be redistributed only with its terms and this notice.
cp "$ROOT/packaging/GEMMA_NOTICE.txt" "$RES/models/ai/NOTICE.txt"
# The terms promise these copies are inside the app.
cp "$ROOT/packaging/BGE_LICENSE.txt" "$RES/models/embedding/LICENSE.txt"
cp "$ROOT/LICENSE" "$RES/LICENSE.txt"

# ADR 0019: nothing bundled may carry Microsoft's telemetry address.
if grep -rl --include='*.so' --include='*.dylib' 'events.data.microsoft.com' "$RES/site-packages" "$RES/python/lib"; then
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
