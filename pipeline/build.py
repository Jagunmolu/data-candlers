"""Build every processed table the app reads, from raw data, in one run.

Usage: python -m pipeline.build
Outputs land in data/processed (loaded by the app) and reports/ (audit trail).
"""
import json
import zipfile

import geopandas as gpd
import pandas as pd

from pipeline import lga_index
from pipeline.paths import CONFIG, PROCESSED, RAW, REPORTS


def lga_geometry():
    """Simplified LGA polygons for the map, small enough to load instantly."""
    src = RAW / "boundaries" / "geojson" / "nga_admin2.geojson"
    if not src.exists():
        with zipfile.ZipFile(RAW / "boundaries" / "nga_admin_boundaries.geojson.zip") as z:
            z.extractall(RAW / "boundaries" / "geojson")
    g = gpd.read_file(src)[["adm2_pcode", "geometry"]]
    g["geometry"] = g.geometry.simplify(0.005, preserve_topology=True)
    return g


def main():
    df, unmatched, meta = lga_index.build()
    df.to_parquet(PROCESSED / "lga_index.parquet", index=False)
    (PROCESSED / "lga_index_meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")

    geo = lga_geometry()
    geo.to_file(PROCESSED / "lga_boundaries.geojson", driver="GeoJSON")

    unmatched = unmatched.copy()
    unmatched["source_name"] = unmatched.get("unique_lga", unmatched["lga_name_src"]).fillna(unmatched["lga_name_src"])
    reasons = pd.read_csv(CONFIG / "unmatched_reasons.csv")
    unmatched = unmatched.merge(reasons, on=["source", "source_name"], how="left")
    unmatched["reason"] = unmatched.reason.fillna("Not yet reviewed")
    unmatched[["source", "source_name", "match_method", "reason"]].to_csv(REPORTS / "unmatched_records.csv", index=False)
    nr = df[df.confidence == "Not ranked"][["adm2_pcode", "adm2_name", "adm1_name", "not_ranked_reason"]]
    nr.sort_values(["adm1_name", "adm2_name"]).to_csv(REPORTS / "lga_not_ranked.csv", index=False)

    print(f"LGAs: {meta['n_lgas']}, ranked: {meta['n_ranked']}, grades: {meta['grades']}")
    print(f"Persistent top 20 under weight perturbation: {meta['n_persistent_top20']}")
    print(f"Index vs PC1 Spearman: {meta['pca']['spearman_index_vs_pc1']:.3f}")
    print(f"Unmatched source records: {len(unmatched)} (see reports/unmatched_records.csv)")


if __name__ == "__main__":
    main()
