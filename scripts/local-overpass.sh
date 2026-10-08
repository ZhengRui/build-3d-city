#!/usr/bin/env bash
# local-overpass.sh: build (import) a local Overpass API in Docker from one BBBike city extract, for when the public
# Overpass servers are blocked or overloaded (they answer 429/504 under the load of a big city's queries; Paris,
# 2026: overpass-api.de and Geofabrik unreachable from one network, the mirrors 504). A static snapshot: rebuild
# for fresher data.
#
#   scripts/local-overpass.sh <BBBike city: Paris|London|Berlin|Tokyo|...> [port, default 8799]
#
# The extract and its .poly go to $OVERPASS_DATA/<city>/, default <data>/overpass/<city>/, <data> being
# $CITY3D_DATA or <project>/demos/data (<project>: $CITY3D_PROJECT, else four folders above this script, a
# worktree's main tree). The database lives in the Docker volume city3d-overpass-<city>-db (2-5.5 GB per city).
# Then list http://127.0.0.1:<port>/api/interpreter first in the city.toml's `overpass` list; the engine caches
# every answer in raw/overpass_cache, so the container can go once the OSM stages have run
# (docker stop/rm the container, docker volume rm the volume).
# Before: take the pipeline lock (scripts/lock.sh take pipeline <you> "overpass import"), check `free -g` shows
# >= 6 GB available, and run one import at a time: it peaks near 3 GB (capped at 5 GB) and takes ~15 min (Paris).
set -euo pipefail
[ $# -ge 1 ] || { echo "usage: $0 <BBBike city> [port]"; exit 2; }
CITY="$1"; PORT="${2:-8799}"; lc="$(echo "$CITY" | tr A-Z a-z)"
HERE="$(cd "$(dirname "$0")" && pwd)"
project_root() {
  local c; c="$(cd "$HERE/../../../.." && pwd)"
  if [ "$(git -C "$c" rev-parse --show-toplevel 2>/dev/null)" = "$c" ]; then
    dirname "$(git -C "$c" rev-parse --path-format=absolute --git-common-dir)"
  else echo "$c"; fi
}
D="${OVERPASS_DATA:-${CITY3D_DATA:-${CITY3D_PROJECT:-$(project_root)}/demos/data}/overpass}"; mkdir -p "$D/$lc"
NAME=city3d-overpass; [ "$lc" = paris ] || NAME="city3d-overpass-$lc"   # (Paris, the first city imported this way, kept the plain name)
if [ ! -s "$D/$lc/$CITY.osm.pbf" ]; then   # curl -C - resumes; BBBike sometimes stalls, hence the speed limit + retry
  for i in $(seq 1 60); do
    curl -sS -C - --speed-limit 20000 --speed-time 15 --connect-timeout 10 -o "$D/$lc/$CITY.osm.pbf.part" \
      "https://download.bbbike.org/osm/bbbike/$CITY/$CITY.osm.pbf" && break; sleep 2; done
  mv "$D/$lc/$CITY.osm.pbf.part" "$D/$lc/$CITY.osm.pbf"
  curl -sS "https://download.bbbike.org/osm/bbbike/$CITY/$CITY.poly" -o "$D/$lc/$CITY.poly"
fi
docker volume create "city3d-overpass-$lc-db" >/dev/null
# the image reads bz2 XML only, so the pbf is converted first (OVERPASS_PLANET_PREPROCESS); FLUSH_SIZE=1 keeps the
# import under ~3 GB (the default 16 was OOM-killed at 4 GB); OVERPASS_MODE=init builds the areas too
docker run -d --name "$NAME" --memory 5g --memory-swap 5g -p "127.0.0.1:$PORT:80" \
  -v "city3d-overpass-$lc-db:/db" -v "$D/$lc/$CITY.osm.pbf:/import/$CITY.osm.pbf:ro" \
  -e OVERPASS_MODE=init -e OVERPASS_META=no -e OVERPASS_STOP_AFTER_INIT=false -e OVERPASS_USE_AREAS=true \
  -e OVERPASS_FLUSH_SIZE=1 -e "OVERPASS_PLANET_URL=file:///import/$CITY.osm.pbf" \
  -e OVERPASS_PLANET_PREPROCESS='mv /db/planet.osm.bz2 /db/planet.osm.pbf && osmium cat -f osm.bz2 -o /db/planet.osm.bz2 /db/planet.osm.pbf && rm /db/planet.osm.pbf' \
  -e OVERPASS_SPACE=3221225472 -e OVERPASS_TIME=3600 \
  wiktorn/overpass-api:latest
docker inspect -f 'container PID (record it in the lock): {{.State.Pid}}' "$NAME"
echo "wait for 'Starting supervisord' in: docker logs $NAME | tail; then: docker exec $NAME chmod 755 /db"
echo "(the image leaves /db mode 700 so nginx cannot reach the dispatcher socket: every query fails with Permission denied until then)"
