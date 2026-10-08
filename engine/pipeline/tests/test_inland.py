"""An inland city, end to end: a tiny synthetic town (2 x 2 km on a hillside near Madrid, UTM 30N) with no
coastline, a pond, a river with a bridge, a park, a wood, a few streets, a car park and some buildings, built
by every stage from 01_osm to 07b_blocks. Overpass is replaced by canned answers (01_osm, 05_ground,
05c_landuse; the other stages read their caches in raw/), the DEM by a synthetic Copernicus tile. Only OSM
footprints and heights, no landmark research: the minimal source set a new city starts with.

Run: `cd .agents/skills/build-3d-city/engine/pipeline && uv run pytest tests` (about a minute).
"""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest

LON0, LAT0 = -3.70, 40.42                       # the town's centre
KX, KY = 111320 * np.cos(np.radians(LAT0)), 110950   # metres per degree
CITY_TOML = """
name = "inlandtest"
title = "Inland test town"
utm_epsg = 32630
coast = "auto"
drive = "right"

[districts]
"Test" = 1

[paths]
data = "data"

[sun]
latitude = 40.42

[sources]
footprints = ["osm"]
heights = ["landmark", "osm_height", "osm_levels", "default"]
[sources.copernicus]
tiles = ["N40_00_W004_00"]

[ground]
margin = 1000

[terrain]
far_reach = 3000.0
[terrain.peaks]
"Test hill" = [-3.69, 40.425]

[views.areas]
"Centre" = [-3.70, 40.42, 1500, 30]
[views.landmarks]
"Town hall" = "Ayuntamiento"
"""


def ll(dx, dy):
    """(lon, lat) of a point dx east, dy north of the centre (metres)."""
    return LON0 + dx / KX, LAT0 + dy / KY


def rect(x0, y0, x1, y1):
    return [ll(x0, y0), ll(x1, y0), ll(x1, y1), ll(x0, y1), ll(x0, y0)]


def way(i, tags, pts, nodes=None):
    e = {"type": "way", "id": i, "tags": tags, "geometry": [{"lon": x, "lat": y} for x, y in pts]}
    if nodes is not None:
        e["nodes"] = nodes
    return e


def overpass_answers():
    """Canned Overpass answers, by what the query asks for."""
    district = {"type": "relation", "id": 1, "tags": {"name": "Test"},
                "members": [{"type": "way", "role": "outer", "geometry":
                             [{"lon": x, "lat": y} for x, y in rect(-1000, -1000, 1000, 1000)]}]}
    buildings = []
    k = 0
    for gx in range(-800, 800, 160):
        for gy in range(-700, 700, 200):
            if -300 < gy < -100:                                  # the river
                continue
            k += 1
            tags = {"building": "apartments" if k % 3 else "house"}
            if k % 4 == 0:
                tags["building:levels"] = str(3 + k % 9)
            if k % 7 == 0:
                tags["height"] = str(12 + k % 30)
            buildings.append(way(1000 + k, tags, rect(gx, gy, gx + 40, gy + 25)))
    buildings.append(way(999, {"building": "civic", "name": "Ayuntamiento", "height": "28"},
                         rect(100, 300, 160, 350)))
    water = [way(2001, {"natural": "water"}, rect(300, 400, 450, 500)),                # a pond
             way(2002, {"waterway": "riverbank"}, rect(-2000, -260, 2000, -140))]       # a river
    green = [way(3001, {"leisure": "park"}, rect(250, 350, 600, 600)),
             way(3002, {"natural": "wood"}, rect(-1800, 1200, -900, 1800))]
    landuse = [way(4001, {"landuse": "residential"}, rect(-900, 0, 0, 900)),
               way(4002, {"landuse": "commercial"}, rect(0, -900, 900, -300))]
    return {"district": {"elements": [district]}, "buildings": {"elements": buildings},
            "ground": {"elements": water + green}, "landuse": {"elements": landuse}}, water, green


def roads():
    """Streets (sharing nodes where they cross) and a bridge over the river."""
    els, node = [], [100]

    def street(i, tags, pts):
        ids = list(range(node[0], node[0] + len(pts)))
        node[0] += len(pts)
        els.append(way(i, tags, [ll(*p) for p in pts], ids))
        return ids

    a = street(5001, {"highway": "primary", "lanes": "4"}, [(-1500, 0), (-500, 0), (0, 0)])
    b = street(5002, {"highway": "primary", "lanes": "4"}, [(0, 0), (700, 0), (1500, 0)])
    # the residential street crosses the primary at (0, 0): same node
    c = street(5003, {"highway": "residential"}, [(0, 900), (0, 400)])
    d = street(5004, {"highway": "residential"}, [(0, 400), (0, 0)])
    els[-1]["nodes"][-1] = a[-1]
    els[-2]["nodes"][-1] = d[0]
    e = street(5005, {"highway": "tertiary"}, [(0, -100), (0, -50)])
    els[-1]["nodes"][-1] = a[-1]
    br = street(5006, {"highway": "tertiary", "bridge": "yes", "layer": "1"}, [(0, -300), (0, -100)])
    els[-1]["nodes"][-1] = e[0]
    street(5007, {"highway": "tertiary"}, [(0, -900), (0, -300)])
    els[-1]["nodes"][-1] = br[0]
    street(5008, {"highway": "service"}, [(300, 100), (500, 100)])
    return {"elements": els}


@pytest.fixture(scope="module")
def city(tmp_path_factory):
    import rasterio
    from rasterio.transform import from_origin
    root = tmp_path_factory.mktemp("inland")
    (root / "city.toml").write_text(CITY_TOML)
    raw = root / "data" / "raw"
    raw.mkdir(parents=True)
    # the DEM: a plain at 600-640 m rising to a 200 m hill north-east, 0.0005 degree pixels
    n = 2000
    lon = -4 + (np.arange(n) + 0.5) / n
    lat = 41 - (np.arange(n) + 0.5) / n
    X, Y = np.meshgrid((lon - LON0) * KX, (lat - LAT0) * KY)
    z = 600 + 0.01 * (Y + 3000) + 200 * np.exp(-((X - 850) ** 2 + (Y - 550) ** 2) / 800 ** 2)
    with rasterio.open(raw / "Copernicus_DSM_COG_10_N40_00_W004_00_DEM.tif", "w", driver="GTiff", width=n, height=n,
                       count=1, dtype="float32", crs="EPSG:4326", transform=from_origin(-4, 41, 1 / n, 1 / n)) as f:
        f.write(z.astype(np.float32), 1)
    answers, water, green = overpass_answers()
    (root / "answers.json").write_text(json.dumps(answers))
    (raw / "osm_roads.json").write_text(json.dumps(roads()))
    (raw / "osm_green.json").write_text(json.dumps({"elements": green}))
    (raw / "osm_shores.json").write_text(json.dumps({"elements": water + [
        way(6001, {"leisure": "swimming_pool"}, rect(-600, 500, -588, 508))]}))
    (raw / "osm_parking.json").write_text(json.dumps({"elements": [
        way(7001, {"amenity": "parking"}, rect(-400, 60, -300, 130))]}))
    return root


# the stages that ask Overpass get a canned answer through this driver
DRIVER = textwrap.dedent("""
    import json, sys
    from city3d import config
    config.load(sys.argv[1])
    answers = json.load(open(sys.argv[2]))
    import importlib
    mod = importlib.import_module("city3d.stages." + sys.argv[3])
    def fake(query, timeout=900):
        if "rel(" in query:
            return answers["district"]
        if '["building"]' in query:
            return answers["buildings"]
        if "coastline" in query:
            return answers["ground"]
        return answers["landuse"]
    mod.overpass = fake
    mod.main()
""")


def run(city, *args):
    env = {**os.environ, "CITY3D_CITY": str(city / "city.toml")}
    r = subprocess.run([sys.executable, "-m", "city3d", *args], cwd=city, env=env, capture_output=True, text=True)
    assert r.returncode == 0, f"{args}: {r.stdout[-2000:]}\n{r.stderr[-4000:]}"
    return r.stdout


def fetch(city, module):
    r = subprocess.run([sys.executable, "-c", DRIVER, str(city / "city.toml"), str(city / "answers.json"), module],
                       cwd=city, capture_output=True, text=True)
    assert r.returncode == 0, f"{module}: {r.stdout[-2000:]}\n{r.stderr[-4000:]}"
    return r.stdout


def test_inland_city_end_to_end(city):
    import geopandas as gpd
    fetch(city, "osm")
    run(city, "04_buildings")
    run(city, "04b_quality")
    out = fetch(city, "ground")
    fetch(city, "landuse")
    data = city / "data"
    area = gpd.read_file(data / "ground.gpkg", layer="area").geometry.iloc[0]
    land = gpd.read_file(data / "ground.gpkg", layer="land")
    # no coastline: the whole area is land
    assert len(land) == 1 and abs(land.area.sum() - area.area) < 1, out
    run(city, "08_trees", "--green-only")
    run(city, "05a_terrain")
    t = np.load(data / "terrain.npz")
    assert "datum" in t.files and 580 < float(t["datum"]) < 640          # lowered by the lowest ground
    assert t["y"].min() < 5 and t["y"].max() > 150                        # the hill stands on a plain near 0
    # no coast ramp: the ground along the area's edge keeps its height (the plain rises northwards)
    md = (city / "checks" / "terrain.md").read_text()
    assert "inland" in md
    for stage in ("05b_roads", "06_tiles", "07_pack", "06b_markings", "05e_shores", "08_trees", "06d_cars",
                  "06c_rooftops", "07b_blocks"):
        run(city, stage)
    b = gpd.read_file(data / "buildings.gpkg")
    assert set(b.source) == {"osm"} and (b.h >= 3.5).all()
    assert b.loc[b.name == "Ayuntamiento", "h"].iloc[0] == 28
    shores = json.loads((data / "shores" / "shores.json").read_text())
    # banks and the pool only: no sea coast types
    assert shores["pools"] == 1
    assert not {"revetment", "quay", "beach", "mudflat", "mudbank", "mudedge"} & set(shores["lengths_km"])
    assert {"embankment", "pondbank"} & set(shores["lengths_km"])
    tiles = json.loads((data / "tiles" / "tiles.json").read_text())
    assert tiles["origin"]["utm_epsg"] == 32630 and {v["name"] for v in tiles["views"]} == {"Centre", "Town hall"}
    for d in ("tiles", "markings", "trees", "cars", "rooftops", "blocks", "shores"):
        assert (city / "web" / d).resolve() == (data / d).resolve(), d
    assert (data / "blocks" / "blocks.json").exists()



def test_deck_ends_raise_the_ground_to_the_road(city, tmp_path):
    """[terrain] deck_ends: a notch dug into the DEM under the bridge's south end (a lidar's water under the first
    arch) is filled to the road's level, and the deck ends on the ground there (no step where the road runs on)."""
    import shutil
    import rasterio
    if not (city / "data" / "roads.gpkg").exists():
        pytest.skip("needs the end-to-end test's city")
    c2 = tmp_path / "deckends"
    shutil.copytree(city, c2, ignore=shutil.ignore_patterns("tiles*", "blocks", "markings*", "cars", "trees",
                                                           "rooftops", "shores*", "web"))
    (c2 / "city.toml").write_text((c2 / "city.toml").read_text().replace(
        "[terrain]\n", "[terrain]\ndeck_ends = { reach = 12.0, ramp = 20.0 }\n"))
    dem = c2 / "data" / "raw" / "Copernicus_DSM_COG_10_N40_00_W004_00_DEM.tif"
    with rasterio.open(dem) as f:
        z, prof = f.read(1), f.profile
        r, c = f.index(*ll(0, -300))                      # the bridge's south end meets the tertiary road there
        z[r, c] -= 8.0
    with rasterio.open(dem, "w", **prof) as f:
        f.write(z, 1)
    out = run(c2, "05a_terrain")
    assert "deck ends: 2 road deck ends" in out, out
    out = run(c2, "05b_roads")
    assert "2 of 2 pinned nodes on the ground 05a raised" in out, out
    code = textwrap.dedent("""
        import json, numpy as np, geopandas as gpd
        from city3d.common import DATA, Terrain
        T = Terrain()
        w = gpd.read_file(DATA / "roads.gpkg", layer="ways")
        c = np.asarray(w[w.elevated].geometry.iloc[0].coords)
        s = c[np.argmin(c[:, 1])]
        ys = s[1] - np.arange(0, 21, 2.0)
        print(json.dumps({"ends": [[float(p[2]), float(T.height_utm([p[0]], [p[1]])[0])] for p in (c[0], c[-1])],
                          "road": T.height_utm(np.full(len(ys), s[0]), ys).tolist()}))
    """)
    r = subprocess.run([sys.executable, "-c", code], cwd=c2, capture_output=True, text=True,
                       env={**os.environ, "CITY3D_CITY": str(c2 / "city.toml")})
    assert r.returncode == 0, r.stderr[-3000:]
    got = json.loads(r.stdout.strip().splitlines()[-1])
    for deck, ground in got["ends"]:
        assert abs(deck - ground) < 0.05, got             # the deck ends on the ground the road meets
    road = np.array(got["road"])                          # the road leaving the south end: no notch under its end
    assert (road >= np.linspace(road[0], road[-1], len(road)) - 0.3).all(), got

def test_land_from_coastline_without_a_coast(city):
    """The unit behind it: no coastline (auto) or coast = false gives the whole area; a coastline still
    splits it."""
    import geopandas as gpd
    from shapely.geometry import LineString, box
    env_city = str(city / "city.toml")
    code = textwrap.dedent(f"""
        import geopandas as gpd
        from shapely.geometry import LineString, box
        from city3d import config
        config.load({env_city!r})
        from city3d.stages.ground import land_from_coastline
        area = box(0, 0, 1000, 1000)
        none = gpd.GeoSeries([], crs="EPSG:32630")
        assert land_from_coastline(none, area, "auto").area.sum() == area.area
        # a coastline running north along x = 400: land on its left (west)
        coast = gpd.GeoSeries([LineString([(400, -10), (400, 1010)])], crs="EPSG:32630")
        assert abs(land_from_coastline(coast, area, "auto").area.sum() - 400_000) < 1
        assert land_from_coastline(coast, area, False).area.sum() == area.area
        print("ok")
    """)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr[-3000:]
