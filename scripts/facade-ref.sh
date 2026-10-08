#!/usr/bin/env bash
# facade-ref.sh: (re)take the reference screenshots and facade-shader measurements (pixdiff.mjs) that a viewer
# refactor is compared against: the safety net for a change that must not alter the picture (written for a facade
# shader refactor, hence the name; any viewer change can use it). Run it from the tree whose viewer is the
# reference (e.g. the main branch before the refactor's first viewer change); it shoots that tree's viewer over the
# data its demos/<city>/web links reach. Retake after any data change of a city (a rebuild of its tiles), before
# comparing a refactor stage against it.
#
#   scripts/facade-ref.sh [all | webgpu | webgl | repeat] [pixdiff options, e.g. --cities paris,london]
#
#   webgpu  every city's 4 standard views, day 16:00 and night 21:30, WebGPU, 3200x2000, + the built facade shader of
#           each city's first view (day and night): $OUT/webgpu/
#   webgl   each city's first view, day and night, WebGL 2, + its facade shader (GLSL): $OUT/webgl/
#   repeat  two views of one city again into $OUT/repeat-webgpu/ and the diff against webgpu/ (the noise floor:
#           two runs of the same tree). REPEAT_CITY (default paris) and REPEAT_VIEWS ("A|B", default two Paris views)
#   all     webgpu, then webgl, then repeat (about 75 min for five cities: 2 views per Chrome session, 2 min between)
#
# Output: $FACADE_REF_OUT, default <data>/facade-ref, <data> being $CITY3D_DATA or <project>/demos/data (pixdiff.mjs
# resolves <project> the same way: $CITY3D_PROJECT, else four folders above this script, a worktree's main tree).
# Your own cities: --views-file <file.json> or CITY3D_VIEWS (see pixdiff.mjs), and set REPEAT_CITY/REPEAT_VIEWS.
# Each session takes the chrome lock (scripts/lock.sh) with the real browser PID and waits while the pipeline lock
# is held. Ports: server 8795, Chrome 9355 (override: PORT=8796 CDP=9356 scripts/facade-ref.sh ...).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
project_root() {
  local c; c="$(cd "$HERE/../../../.." && pwd)"
  if [ "$(git -C "$c" rev-parse --show-toplevel 2>/dev/null)" = "$c" ]; then
    dirname "$(git -C "$c" rev-parse --path-format=absolute --git-common-dir)"
  else echo "$c"; fi
}
MAIN="${CITY3D_PROJECT:-$(project_root)}"
OUT="${FACADE_REF_OUT:-${CITY3D_DATA:-$MAIN/demos/data}/facade-ref}"
what="${1:-all}"; shift || true
P=(--port "${PORT:-8795}" --cdp-port "${CDP:-9355}" "$@")
mkdir -p "$OUT"
run_webgpu() { node "$HERE/pixdiff.mjs" shoot --out "$OUT/webgpu" --shader "${P[@]}"; }
run_webgl() { node "$HERE/pixdiff.mjs" shoot --out "$OUT/webgl" --webgl --first --shader "${P[@]}"; }
DEFAULT_RV="Paris overview|Avenue de l'Opéra (street level)"
run_repeat() {
  node "$HERE/pixdiff.mjs" shoot --out "$OUT/repeat-webgpu" --cities "${REPEAT_CITY:-paris}" --views "${REPEAT_VIEWS:-$DEFAULT_RV}" "${P[@]}"
  node "$HERE/pixdiff.mjs" compare "$OUT/webgpu" "$OUT/repeat-webgpu" || true
}
case "$what" in
  webgpu) run_webgpu ;;
  webgl) run_webgl ;;
  repeat) run_repeat ;;
  all) run_webgpu; sleep 120; run_webgl; sleep 120; run_repeat ;;
  *) echo "usage: $0 [all|webgpu|webgl|repeat] [pixdiff options]"; exit 2 ;;
esac
# then, after a viewer change, against this reference:
#   node scripts/pixdiff.mjs run --ref "$OUT/webgpu" --out "$OUT/runs/<name>"
