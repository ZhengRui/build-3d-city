"""Source adapter: CNBH-10m, a 2020 building height raster for China at 10 m (Zenodo 7923866, CC BY 4.0).

One tile ([sources.cnbh] file, e.g. CNBH10m_X113Y23.tif, UTM) is downloaded by hand into raw/. It has no
footprints: a footprint's height is the median of the pixels it covers, else the pixel under its centroid.
Used as a height source (the "cnbh" entry of [sources] heights, and the blend) and as an independent check
of GBA's heights (03_compare). China only.
"""
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.windows import from_bounds

from ..common import CFG, RAW

CNBH = RAW / CFG["sources"]["cnbh"]["file"]


def sample(g: gpd.GeoDataFrame) -> pd.Series:
    """CNBH-10m height per footprint: median of covered pixels, else the pixel under the centroid."""
    with rasterio.open(CNBH) as r:
        gg = g.to_crs(r.crs)
        win = from_bounds(*gg.total_bounds, transform=r.transform).round_offsets().round_lengths()
        arr = r.read(1, window=win)
        tr = r.window_transform(win)
    ids = rasterize(((geom, i + 1) for i, geom in enumerate(gg.geometry)),
                    out_shape=arr.shape, transform=tr, fill=0, dtype="int32")
    valid = (ids > 0) & (arr > 0) & np.isfinite(arr)
    df = pd.DataFrame({"id": ids[valid] - 1, "v": arr[valid]})
    med = df.groupby("id")["v"].median()
    out = pd.Series(np.nan, index=range(len(g)))
    out.loc[med.index] = med.values
    miss = out.isna()
    if miss.any():
        c = gg.geometry.centroid[miss.values]
        rows, cols = rasterio.transform.rowcol(tr, c.x, c.y)
        rows, cols = np.clip(rows, 0, arr.shape[0] - 1), np.clip(cols, 0, arr.shape[1] - 1)
        v = arr[rows, cols]
        out.loc[miss[miss].index] = np.where(v > 0, v, np.nan)
    return pd.Series(out.values, index=g.index)
