"""The europe-west preset's code (Western Europe: Paris first, then London and Berlin; tables in
presets/europe-west.toml): building kinds (Paris's since M2), facade styles and roof shapes (Paris's since M4:
facade_styles(), roof_shapes()). Its rooftop clutter is in rooftops.py (New York's until M6).

Building kinds (04_buildings). Names are stable: facade styles and rooftops key off them, and a new city of the
region adds kinds of its own rather than renaming these:
  haussmann  1850-1914 stone apartment blocks, 5-8 storeys (12 m and up) with mansards: Paris's fabric
  faubourg   before 1850, and lower 19th-century houses: plastered rubble, 2-5 storeys (the Marais, the faubourgs)
  interwar   1915-1944 apartment and office buildings: brick, concrete and stone, art deco
  hbm        1919-1939 social housing (Habitations à bon marché): the brick rings along the Boulevards des
             Maréchaux, on the old fortifications' belt (within [buildings.kinds] hbm.ring m of the city's edge)
  postwar    1945-1979 slabs, plots and grands ensembles under tower height
  modern     since 1980 under tower height
  tower      tower_h (50 m) and up, any period (La Défense, Front de Seine, Montparnasse, the Olympiades)
  house      houses and villas (OSM house, detached...): the 16e's and Neuilly's villas, the 20e's cités
  civic      churches, monuments (and the landmark list's monuments: use_height false), schools, hospitals,
             stations, ministries, museums
  factory    workshops, warehouses, depots, garages; big low halls
  shed       sheds, kiosks, lean-tos and small low annexes in the courtyards

Where the data comes from, in order (a later rule wins; the order follows demos/paris/data/region_research.md §5.3):
  1. the period: the first known year of YEAR_FIELDS (APUR's an_const in Paris; BD TOPO's date_d_apparition, its
     year, in La Défense and Neuilly and lent onto APUR's footprints where APUR has none; they agree within 5
     years on 95 % of 59,572 footprints with both), else a period code ([buildings.kinds] periods: APUR's
     c_perconst, 98 % filled), else the median year of the dated buildings in its [buildings.kinds] neighbours m
     grid cell (150 m, at least 5 of them). 1850-1914 from haussmann_min_h (15 m) haussmann, lower faubourg;
     1915-44 interwar; 1945-81 postwar; 1982 on modern
  2. undated (no year, no code): its own roof and form over the neighbours' period: a pitched or mansard roof (APUR
     c_forme_toit 2-4) in an old (pre-1945 or unknown) neighbourhood is haussmann from 15 m to 32 m, faubourg
     under; a flat roof (c_forme_toit 1) or a postwar form (c_morpho 5-7: barre, plot, tour) from 9 m postwar
     (modern among post-1982 neighbours); nothing known at all: 15-25 m haussmann, 25 m and up postwar, but
     modern in a grid cell with a tower_h building or for an office (BD TOPO usage_1 Commercial et services): La
     Défense's undated buildings
  3. APUR's urban fabric (c_tissu) and form: small-scale fabric (TPE) 5-15 m and not postwar house; the
     individual-house form (c_morpho 1) elsewhere faubourg from 9 m, shed under; HBM hbm (without c_tissu: interwar housing within hbm.ring m of the city's
     edge); industrial fabric (TI) factory
  4. shape: low (under 14 m) and 3,000 m² or more factory; under 30 m² and 6 m, or under 5 m on under 200 m², or a
     courtyard cover (APUR b_dalle) under 6 m shed; tower_h (50 m) and up, or APUR's tower forms (c_tissu IGH,
     c_morpho 7) from tower_form_h (37 m), tower
  5. tags: OSM building tag ([buildings.osm_kind]), BD TOPO's usage_1 (Industriel; Annexe) and
     construction_legere (an OSM shed or garage tag only under 9 m); civic buildings become towers at tower_h
     unless religious; APUR's remarkable fabric (c_tissu ER) unless homes (BD TOPO Résidentiel, OSM residential
     tags) or a dwelling or office tower, BD TOPO's nature (Eglise, Monument, Chapelle...) and usage_1 Religieux, OSM's
     religious tags and the landmark list's monuments (use_height false) are civic however tall
A city picks its rules by the fields it has: APUR's (an_const, c_perconst, c_tissu, c_morpho, c_forme_toit,
b_dalle) only where present, BD TOPO's where present; a city without them gets the period rules from YEAR_FIELDS
and the shape and tag rules.
"""
import numpy as np
import pandas as pd

from ... import config

CFG = config.get()
OSM_KIND = CFG["buildings"]["osm_kind"]          # OSM building tag -> kind
KINDS = CFG["buildings"].get("kinds", {})
TOWER_H = KINDS.get("tower_h", 50.0)
# the fields building_kind reads (04_buildings takes them onto a building made of OSM parts, from its first part)
KIND_FIELDS = ("osm_building", "monument", "an_const", "c_perconst", "c_tissu", "b_dalle", "c_morpho", "c_forme_toit", "c_toiture_mat", "b_terrasse", "usage_1",
               "nature", "construction_legere", "date_d_apparition", "construction_year", "yearbuilt", "source")
YEAR_FIELDS = ("an_const", "construction_year", "yearbuilt", "date_d_apparition")
RELIGIOUS = {"church", "cathedral", "chapel", "basilica", "synagogue", "mosque", "temple", "shrine", "monastery",
             "religious", "monument", "triumphal_arch", "palace", "castle"}
BDTOPO_CIVIC = {"Eglise", "Chapelle", "Monument", "Arc de triomphe", "Tour, donjon", "Château", "Tribune"}
_EDGE = {}


def col(df: pd.DataFrame, c: str, fill=np.nan) -> pd.Series:
    return df[c] if c in df else pd.Series(fill, index=df.index)


def years(df: pd.DataFrame, c: str) -> pd.Series:
    """A field's year (a date's first four digits), NaN when missing or implausible."""
    if c not in df:
        return pd.Series(np.nan, index=df.index)
    v = pd.to_numeric(df[c].astype(str).str.extract(r"^\s*(\d{4})")[0], errors="coerce")
    return v.where((v >= 1100) & (v <= 2035))


def year_of(df: pd.DataFrame) -> pd.Series:
    """Year of construction, by trust: a built year (YEAR_FIELDS but the last: APUR's an_const, NYC's), then a
    period code ([buildings.kinds] periods: APUR's c_perconst), then a date the object entered a database
    (the last of YEAR_FIELDS: BD TOPO's date_d_apparition), only where there is no period code field at all (La
    Défense, Neuilly: it disagrees with APUR's period on 2,690 pre-1914 buildings it made "modern").
    APUR's an_const of exactly 1850 is its floor for older buildings: with c_perconst 1-2 the period's year."""
    built = pd.Series(np.nan, index=df.index)
    for c in YEAR_FIELDS[:-1]:
        built = built.fillna(years(df, c))
    period = period_year(df)
    floor = (built == 1850) & (period < 1850)
    built[floor] = period[floor]
    y = built.fillna(period)
    has_code = pd.Series(False, index=df.index)
    for c in KINDS.get("periods", {}):
        if c in df:
            has_code |= df[c].notna()
    return y.fillna(years(df, YEAR_FIELDS[-1]).where(~has_code))


def edge_distance(df: pd.DataFrame, prefix: str) -> pd.Series:
    """Distance (m) of each building inside the city (the districts named prefix...) to the city's edge; NaN outside."""
    if prefix not in _EDGE:
        from ...common import districts
        d = districts()
        d = d[d.name.str.startswith(prefix)]
        _EDGE[prefix] = d.union_all() if len(d) else None
    city = _EDGE[prefix]
    if city is None or not hasattr(df, "geometry"):
        return pd.Series(np.nan, index=df.index)
    pt = df.geometry.representative_point()
    inside = pt.within(city)
    return pd.Series(np.where(inside, pt.distance(city.boundary), np.nan), index=df.index)


NEIGHBOURS = KINDS.get("neighbours", 150.0)     # m: the grid cell whose dated buildings date an undated one


def neighbour_year(df: pd.DataFrame, year: pd.Series) -> pd.Series:
    """Median year of construction of the dated buildings in the same NEIGHBOURS m grid cell (at least 5 of
    them); NaN else. A grid, not a radius: 50,000 undated buildings among 80,000 dated ones in Paris."""
    if not hasattr(df, "geometry") or year.notna().sum() < 5 or year.isna().sum() == 0:
        return pd.Series(np.nan, index=df.index)
    pt = df.geometry.representative_point()
    cell = pd.Series(list(zip((pt.x // NEIGHBOURS).astype(int), (pt.y // NEIGHBOURS).astype(int))), index=df.index)
    g = pd.DataFrame({"cell": cell, "y": year}).dropna().groupby("cell").y.agg(["median", "size"])
    med = g["median"].where(g["size"] >= 5)
    return cell.map(med).astype(float)


def tower_cell(df: pd.DataFrame) -> pd.Series:
    """Whether a tower_h building stands in the building's NEIGHBOURS m grid cell."""
    if not hasattr(df, "geometry"):
        return pd.Series(False, index=df.index)
    pt = df.geometry.representative_point()
    cell = pd.Series(list(zip((pt.x // NEIGHBOURS).astype(int), (pt.y // NEIGHBOURS).astype(int))), index=df.index)
    tall = set(cell[df["h"] >= TOWER_H])
    return cell.isin(tall)


def period_year(df: pd.DataFrame) -> pd.Series:
    """A year for a period code ([buildings.kinds] periods: {field = {code = year}}; APUR's c_perconst, 98 % filled
    where an_const is 63 %), NaN where the code is unknown."""
    y = pd.Series(np.nan, index=df.index)
    for c, table in KINDS.get("periods", {}).items():
        if c in df:
            code = pd.to_numeric(df[c], errors="coerce")
            y = y.fillna(code.map({int(k): float(v) for k, v in table.items()}))
    return y


def building_kind(df: pd.DataFrame) -> pd.Series:
    """Kind per building (04_buildings) from its height h, footprint area, aspect, width, year and the source
    fields named in the module's docstring."""
    h, a = df["h"], df["area"]
    own = year_of(df)
    none = own.isna()
    # no year of its own: the median year of the dated buildings around it (La Défense's undated buildings
    # among its towers are not Haussmann's; the Marais's among its old houses are old)
    year = own.fillna(neighbour_year(df, own))
    old_h = KINDS.get("haussmann_min_h", 15.0)
    kind = pd.Series("faubourg", index=df.index, dtype=object)
    # 1. the period
    kind[(year >= 1850) & (year <= 1914) & (h >= old_h)] = "haussmann"
    kind[(year > 1914) & (year < 1945)] = "interwar"
    kind[(year >= 1945) & (year < 1982)] = "postwar"
    kind[year >= 1982] = "modern"
    # 2. no year at all: height; and for any undated building, its roof and form (APUR) over the neighbours'
    guess = year.isna()
    kind[guess & (h >= old_h) & (h < 25)] = "haussmann"
    kind[guess & (h >= 25)] = "postwar"
    # ... among towers (a tower_h building in the same grid cell: La Défense, where BD TOPO dates few buildings),
    # or an office building undated: modern
    among = tower_cell(df) | col(df, "usage_1").eq("Commercial et services")
    kind[guess & among & (h >= 5)] = "modern"
    roof = pd.to_numeric(col(df, "c_forme_toit"), errors="coerce")
    morpho = pd.to_numeric(col(df, "c_morpho"), errors="coerce")
    tissu = col(df, "c_tissu").fillna("").astype(str)
    pitched = roof.isin([2, 3, 4])
    old = year.isna() | (year < 1945)
    kind[none & old & pitched & (h >= old_h) & (h < 32)] = "haussmann"
    kind[none & old & pitched & (h < old_h)] = "faubourg"
    flat = none & ((roof == 1) | morpho.isin([5, 6, 7])) & (h >= 9)
    kind[flat] = np.where(year[flat] >= 1982, "modern", "postwar")
    # small houses: APUR's small-scale fabric (c_tissu TPE: Montmartre's and the 20e's houses and villas) under
    # 15 m. APUR's individual-house form (c_morpho 1) elsewhere is a low building in a continuous block (a
    # courtyard wing, a workshop): faubourg from 9 m, a shed under (M2 critic: 6,400 such "houses")
    kind[tissu.eq("TPE") & (h >= 5) & (h < 15) & ~(year >= 1945)] = "house"
    one = morpho.eq(1) & ~tissu.eq("TPE") & (h < 15) & ~(year >= 1945)
    kind[one & (h >= 9)] = "faubourg"
    kind[one & (h < 9)] = "shed"
    # the HBM: APUR's c_tissu HBM; without that field, interwar housing within hbm.ring m of the city's edge
    # (the fortifications' belt)
    kind[tissu.eq("HBM") & (h >= 9)] = "hbm"
    hbm = KINDS.get("hbm")
    if hbm and "c_tissu" not in df:
        y0, y1 = hbm["years"]
        ring = edge_distance(df, hbm["city"]) <= hbm["ring"]
        use = col(df, "usage_1").fillna("")
        kind[ring & (year >= y0) & (year <= y1) & (h >= hbm["min_h"]) & ~use.isin(["Industriel", "Annexe"])] = "hbm"
    # 3. shape: big low halls, sheds and courtyard covers (APUR b_dalle: a slab or glass roof over a courtyard at
    # the ground floor), towers (tower_h; APUR's own tower forms, c_tissu IGH or c_morpho 7, from tower_form_h)
    kind[(h < 14) & (a >= 3000)] = "factory"
    # (a slice under 30 m² of a street building keeps its period's kind from 6 m up)
    kind[((a < 30) & (h < 6)) | ((h < 5) & (a < 200)) | (col(df, "b_dalle").eq("O") & (h < 6))] = "shed"
    kind[(h >= TOWER_H) | ((tissu.eq("IGH") | morpho.eq(7)) & (h >= KINDS.get("tower_form_h", 37.0)))] = "tower"
    # 4. tags
    tag = col(df, "osm_building").fillna("")
    osm_kind = tag.map(OSM_KIND)
    use = col(df, "usage_1").fillna("")
    nature = col(df, "nature").fillna("")
    light = col(df, "construction_legere").astype(str).str.lower().isin(["true", "1"])
    kind[use.isin(["Industriel", "Agricole"]) & (h < 30)] = "factory"
    kind[(light | use.eq("Annexe")) & (h < 6) & (a < 400)] = "shed"
    kind[tissu.eq("TI") & (h < 30) & ~kind.eq("tower")] = "factory"     # APUR's industrial fabric
    # OSM's tag, unless the height says tower; a shed or garage tag 9 m up is a mis-tag on a dwelling (26 m
    # "garages")
    ok = osm_kind.notna() & ((kind != "tower") | osm_kind.eq("civic")) & ~(osm_kind.eq("shed") & (h >= 9))
    kind[ok] = osm_kind[ok]
    # [buildings.kinds] field_kind = {field, map}: a source's own function code -> kind, over OSM's tag (Berlin's
    # ALKIS function on every LoD2 solid); a shed 9 m up is no shed, as for OSM's tags
    fk = KINDS.get("field_kind", {})
    if fk and fk.get("field") in df:
        fkind = df[fk["field"]].astype(str).map(fk.get("map", {}))
        ok = fkind.notna() & ((kind != "tower") | fkind.eq("civic")) & ~(fkind.eq("shed") & (h >= 9))
        kind[ok] = fkind[ok]
    kind[kind.eq("civic") & (h >= TOWER_H) & ~tag.isin(RELIGIOUS)] = "tower"    # the Tribunal, Jussieu's tower
    # remarkable buildings (APUR c_tissu ER: churches, palaces, ministries, stations), BD TOPO's religious and
    # monument natures, OSM's religious tags and the landmark list's monuments stay civic however tall
    # (not towers people live or work in: Les Gémeaux, Tour Enedis, a housing tower on the Ourcq)
    dwelling = use.eq("Résidentiel") | tag.isin(["tower", "apartments", "residential", "office"])
    # (ER is remarkable fabric, not only public buildings: the Place des Vosges' pavilions are homes; those keep
    # their period's kind)
    homes = use.eq("Résidentiel") | tag.isin(["apartments", "residential", "house", "detached", "terrace"])
    civic = tissu.eq("ER") & (h >= 5) & ~homes & ~(dwelling & (h >= TOWER_H))   # the Opéra's 58 m fly tower too
    kind[civic | nature.isin(BDTOPO_CIVIC) | use.eq("Religieux") | tag.isin(RELIGIOUS)] = "civic"
    kind[col(df, "monument", False).fillna(False).astype(bool) & ~dwelling] = "civic"
    return kind


def facade_styles(b, use: pd.Series, osm_style: dict) -> np.ndarray:
    """Facade style per building (06_tiles) from its kind (building_kind), height, year, APUR's roof form, the
    OSM tag (only on the kinds that carry no period: modern, postwar, factory, shed) and its parts.

      haussmann    haussmann kind; interwar with a mansard (APUR c_forme_toit 4): cut stone, iron balconies
      faubourg     faubourg kind: plaster, shutters
      house        small houses and villas
      hbm          HBM; interwar without a mansard, two in five (brick and concrete bands)
      postwar      postwar under 28 m; interwar without a mansard, three in five (render, loggias)
      concretepanel postwar from 28 m; towers built before 1985 in Paris (not La Défense's BD TOPO towers)
      modern       modern kind; glass the towers from 1985 on, from 100 m, and La Défense's
      limestone    civic buildings before 1915 from 10 m (palaces, ministries, churches); civic the rest
      factory, shed as their kinds, but a "shed" from 6 m (a street-front slice, Place du Tertre) takes its
                   period's style
    [facade.zones] in city.toml then sets named ensembles (Place des Vosges, Rivoli, Vendôme) and
    landmark_facades.csv the landmarks.
    """
    h, kind = b.get("h_bldg", b.h).fillna(b.h), b.kind.astype(str)
    idx = b.index
    def num(c):
        return pd.to_numeric(b[c], errors="coerce") if c in b else pd.Series(np.nan, index=idx)
    year = year_of(b)
    roof = num("c_forme_toit")
    rnd = pd.Series(np.random.default_rng(11).random(len(b)), index=idx)
    style = pd.Series("faubourg", index=idx, dtype=object)
    for k in ("haussmann", "faubourg", "house", "hbm", "postwar", "modern", "civic", "factory", "shed"):
        style[kind == k] = k
    inter = kind == "interwar"
    style[inter] = np.where(roof[inter] == 4, "haussmann", np.where(rnd[inter] < 0.4, "hbm", "postwar"))
    style[(kind == "postwar") & (h >= 28)] = "concretepanel"
    ladef = col(b, "source").eq("bdtopo") & (h >= 50)
    tower = kind == "tower"
    style[tower] = np.where(((year < 1985) & ~ladef & (h < 100))[tower], "concretepanel", "glass")
    style[(kind == "civic") & (year < 1915) & (h >= 10)] = "limestone"
    # a shed from 6 m is a street-front slice or a courtyard wing with windows: its period's style
    tall_shed = (kind == "shed") & (h >= 6)
    per = np.select([year < 1850, year < 1915, year < 1945, year < 1982, year >= 1982],
                    ["faubourg", "haussmann", "haussmann", "postwar", "modern"], "faubourg")
    per = pd.Series(per, index=idx)
    per[(per == "haussmann") & (h < 15)] = "faubourg"
    style[tall_shed] = per[tall_shed]
    # OSM's tag on the kinds without a period of their own
    tag = b.osm_building.map(osm_style) if "osm_building" in b else pd.Series(np.nan, index=idx)
    ok = tag.notna() & kind.isin(["modern", "postwar", "factory", "shed"]) & ~(tag.eq("shed") & (h >= 6))
    style[ok] = tag[ok]
    style[(col(b, "h_src").astype(str).str.startswith("landmark")) & (h >= 150)] = "glass"
    # a building made of OSM parts is one style, from the whole (its kind and tallest top); its thin parts
    # rising over the main roof (04_buildings.main_roof: where the parts from the top down add up to 60 m²)
    # are masts and spires
    if "part_of" in b:
        parts = b.part_of.notna()
        if parts.any():
            from ...stages.buildings import main_roof as roof_of
            area = b.geometry.area
            ph = b.h
            g = pd.DataFrame({"host": b.part_of, "h": ph, "a": area, "style": style})[parts]
            main_roof = b[parts].groupby("part_of").apply(roof_of)
            main_style = g.sort_values("a").groupby("host")["style"].last()
            style[parts] = b.part_of[parts].map(main_style).values
            spire = parts & (area < 120) & (ph > b.part_of.map(main_roof) + 5)
            style[spire] = "spire"
    return style.values


# roof shapes (06_tiles roof_shapes): which styles take APUR's mansard (brisis-terrasson, c_forme_toit 4) and
# pitched roofs (2, 3), and which do by default where the form is unknown (BD TOPO, OSM)
MANSARD_STYLES = {"haussmann", "faubourg", "house", "limestone", "brickstone", "hbm", "postwar", "modern", "civic", "monument"}
PITCHED_STYLES = {"faubourg", "house", "haussmann", "limestone", "brickstone", "hbm", "civic", "shed", "postwar", "modern"}
ROOF_MATERIAL = {"A": 1, "T": 2, "M": 3, "V": 3}      # APUR c_toiture_mat -> zinc/slate, tile, mineral


def roof_shapes(b, style) -> pd.DataFrame:
    """Per building: roof shape ("mansard", "pitched" or "") and material code (1 zinc or slate, 2 tile, 3 flat
    mineral or green, 0 unknown) from APUR's c_forme_toit and c_toiture_mat and the facade style. Where the form
    is unknown (La Défense, Neuilly, OSM's fill) Haussmann blocks take a mansard and faubourg houses a pitched
    roof. OSM parts and landmark rows keep their own massing (06_tiles)."""
    idx = b.index
    style = pd.Series(style, index=idx).astype(str)
    form = pd.to_numeric(col(b, "c_forme_toit"), errors="coerce")
    h, a = b.h, b.geometry.area
    shape = pd.Series("", index=idx, dtype=object)
    mans = (form == 4) & style.isin(MANSARD_STYLES)
    mans |= form.isna() & style.isin(["haussmann", "limestone", "brickstone", "monument"])
    shape[mans & (h >= 8) & (a >= 40)] = "mansard"
    pitch = form.isin([2, 3]) & style.isin(PITCHED_STYLES)
    pitch |= form.isna() & style.isin(["faubourg", "house"])
    # (a mansard under 8 m or on a small piece: a pitched roof, as a low attic)
    pitch |= mans & ((h < 8) | (a < 40))
    shape[pitch & (h >= 4) & (a >= 15) & (shape == "")] = "pitched"
    mat = col(b, "c_toiture_mat").map(ROOF_MATERIAL)
    fill = np.select([shape.eq("mansard"), shape.eq("pitched") & form.eq(2), shape.eq("pitched")], [1, 2, 1], 0)
    mat = mat.fillna(pd.Series(fill, index=idx)).astype(int)
    return pd.DataFrame({"shape": shape, "material": mat}, index=idx)
