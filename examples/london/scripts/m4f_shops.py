"""London M4 fix round (builder F): OSM shop and street-level amenity nodes (shops, cafés, pubs, restaurants,
banks...) inside the boundary's box, from the local Overpass (city.toml's first server), to
demos/data/london/osm_shops.json ([[lon, lat], ...]). The uk-london preset's facade_styles() marks the buildings
holding one (or fronting a primary or secondary road in the centre) as shopfront buildings: 06_tiles puts their
seed in the lower half, and the viewer's facade.js gives them a shopfront ground floor (city.json
facade.shopSeed). Run once before 06_tiles: `uv run python scripts/m4f_shops.py` (13,491 nodes, a few seconds)."""
import json
import urllib.parse
import urllib.request

from city3d import config
from city3d.common import DATA

BOX = (51.47, -0.165, 51.535, 0.03)          # s, w, n, e: the districts with a margin
AMENITY = "restaurant|cafe|pub|bar|bank|fast_food|pharmacy|bureau_de_change|ice_cream"


def main():
    url = config.get()["overpass"][0]
    b = ",".join(map(str, BOX))
    q = f'[out:json][timeout:120];(node["shop"]({b});node["amenity"~"^({AMENITY})$"]({b}););out skel;'
    with urllib.request.urlopen(url, urllib.parse.urlencode({"data": q}).encode(), timeout=180) as r:
        els = json.load(r)["elements"]
    pts = [[round(e["lon"], 6), round(e["lat"], 6)] for e in els if e["type"] == "node"]
    (DATA / "osm_shops.json").write_text(json.dumps(pts))
    print(f"{len(pts):,} shop and amenity nodes -> {DATA / 'osm_shops.json'}")


if __name__ == "__main__":
    main()
