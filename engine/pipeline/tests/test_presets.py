"""Region presets built on another (base/replace): uk-london and de-berlin on europe-west."""
from city3d.config import preset_table


def test_sub_presets_replace_styles_and_keep_the_rest():
    ew = preset_table("europe-west")
    for name, own, gone in (("uk-london", "georgian", "haussmann"), ("de-berlin", "altbau", "haussmann")):
        p = preset_table(name)
        styles = p["facade"]["styles"]
        assert own in styles and gone not in styles
        # the landmark styles builders use stay
        for s in ("monument", "floodlit", "brickstone", "limestone", "concretepanel", "glass", "plain", "spire"):
            assert s in styles, (name, s)
        # europe-west's other tables hold (building kinds, trees, cars)
        assert p["buildings"]["osm_kind"] == ew["buildings"]["osm_kind"]
        assert p["cars"] == ew["cars"] or name == "uk-london"
    berlin = preset_table("de-berlin")
    assert berlin["tiles"]["roof_eave"] is True
    assert "roof_eave" not in ew.get("tiles", {})
    # (06_tiles packs the style id with the seed under UV_RANGE fac's 64)
    assert len(berlin["facade"]["styles"]) < 64
