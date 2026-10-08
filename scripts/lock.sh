#!/usr/bin/env bash
# lock.sh: machine-wide locks for city builds, so that parallel agents never run two heavy things at once:
#   chrome    one Chrome with a city loaded (a city takes 4-5 GB of RAM in Chrome; two at once can freeze the machine)
#   pipeline  one heavy pipeline stage (tiles, buildings, a local Overpass import: several GB each)
#
# usage: lock.sh take    <chrome|pipeline> <agent-name> <note>  -> exit 0 taken, 1 busy (prints the holder)
#        lock.sh pid     <chrome|pipeline> <pid>                -> record the PID of the process the lock protects
#        lock.sh release <chrome|pipeline>                      -> release (only the holder should)
#        lock.sh show                                           -> both locks' state
#
# A lock is a one-line file "<pid|-> <agent> <HH:MM> <note>", or "free". `take` reports a lock whose recorded PID
# is dead as stale but does not break it: whoever coordinates the agents decides. speedtest.mjs and pixdiff.mjs
# use this script with the same lock folder (they wait while the pipeline lock is held and take the chrome lock).
#
# Lock folder: $CITY3D_LOCKS, default <project>/demos/data/.locks, where <project> is $CITY3D_PROJECT or, by
# default, the folder four levels above this script (the skill installed at <project>/.agents/skills/build-3d-city;
# from a git worktree of that project: the main tree, so that every worktree shares one set of locks).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
project_root() {
  local c; c="$(cd "$HERE/../../../.." && pwd)"
  if [ "$(git -C "$c" rev-parse --show-toplevel 2>/dev/null)" = "$c" ]; then
    dirname "$(git -C "$c" rev-parse --path-format=absolute --git-common-dir)"
  else echo "$c"; fi
}
PROJECT="${CITY3D_PROJECT:-$(project_root)}"
D="${CITY3D_LOCKS:-${CITY3D_DATA:-$PROJECT/demos/data}/.locks}"
mkdir -p "$D"
for l in chrome pipeline; do [ -s "$D/$l" ] || echo free > "$D/$l"; done
cmd="${1:-show}"; name="${2:-}"
case "$name" in chrome|pipeline|"") ;; *) echo "unknown lock '$name' (chrome or pipeline)"; exit 2;; esac
f="$D/$name"
case "$cmd" in
  take)
    exec 9>>"$D/.mutex"; flock 9
    cur="$(cat "$f")"
    if [ "$cur" != "free" ]; then
      pid="$(echo "$cur" | awk '{print $1}')"
      if [ "$pid" != "-" ] && ! kill -0 "$pid" 2>/dev/null; then echo "stale lock (pid $pid dead), still held by note: $cur -- ask the coordinator"; fi
      echo "BUSY: $cur"; exit 1; fi
    echo "- $3 $(date +%H:%M) ${*:4}" > "$f"; echo "taken: $(cat "$f")";;
  pid)
    exec 9>>"$D/.mutex"; flock 9
    cur="$(cat "$f")"; echo "$3 ${cur#* }" > "$f"; echo "now: $(cat "$f")";;
  release) echo free > "$f"; echo "released $name";;
  show) for l in chrome pipeline; do echo "$l: $(cat "$D/$l")"; done;;
  *) echo "usage: $0 take|pid|release|show <chrome|pipeline> ..."; exit 2;;
esac
