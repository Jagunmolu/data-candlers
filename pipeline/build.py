"""Build every processed table the app reads, from raw data, in one run.

Usage: python -m pipeline.build
Outputs land in data/processed (loaded by the app) and reports/ (audit trail).
"""
import json
import zipfile

import geopandas as gpd
import pandas as pd
from shapely.geometry import MultiPolygon
from shapely.geometry.polygon import orient

from pipeline import extract_mics, extract_ubec, extract_waec, lens2, lga_index, validate
from pipeline.paths import CONFIG, INTERIM, PROCESSED, RAW, REPORTS


def lga_geometry():
    """Simplified LGA polygons for the map, small enough to load instantly."""
    src = RAW / "boundaries" / "geojson" / "nga_admin2.geojson"
    if not src.exists():
        with zipfile.ZipFile(RAW / "boundaries" / "nga_admin_boundaries.geojson.zip") as z:
            z.extractall(RAW / "boundaries" / "geojson")
    g = gpd.read_file(src)[["adm2_pcode", "geometry"]]
    g["geometry"] = g.geometry.simplify(0.005, preserve_topology=True).map(_clockwise)
    return g


def _clockwise(geom):
    """Plotly's geo maps want clockwise outer rings; RFC 7946 GeoJSON uses the opposite,
    which makes every polygon fill the whole world instead of the LGA."""
    if geom.geom_type == "Polygon":
        return orient(geom, sign=-1.0)
    return MultiPolygon([orient(p, sign=-1.0) for p in geom.geoms])


def state_context(lens2_df, state_need):
    """One row per state: WAEC 2016-2018, MICS 2021 and Lens 1 aggregates."""
    mics = pd.read_parquet(INTERIM / "mics_state_2021.parquet")
    adm1 = pd.read_excel(RAW / "boundaries" / "nga_admin_boundaries.xlsx", sheet_name="nga_admin1")
    cols = ["adm1_pcode", "actual", "expected", "lower", "upper", "sat", "years", "rate_2016", "rate_2017", "rate_2018"]
    out = (
        adm1[["adm1_pcode", "adm1_name"]]
        .merge(lens2_df[cols].rename(columns={"actual": "waec_pass_rate", "expected": "waec_resource_expected"}), on="adm1_pcode", how="left")
        .merge(mics, on="adm1_pcode", how="left")
        .merge(state_need, on="adm1_pcode", how="left")
    )
    return out


def main():
    # State sources first: extraction with reconciliation reports.
    extract_waec.main()
    extract_ubec.main()
    extract_mics.build()

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

    l2, l2_meta = lens2.fit()
    checks, st_need = validate.run(df)
    state_context(l2, st_need).to_parquet(PROCESSED / "state_context.parquet", index=False)
    (PROCESSED / "lens2_meta.json").write_text(json.dumps(l2_meta, indent=2), encoding="utf-8")
    (PROCESSED / "validation.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")

    print(f"LGAs: {meta['n_lgas']}, ranked: {meta['n_ranked']}, grades: {meta['grades']}")
    print(f"Persistent top 20 under weight perturbation: {meta['n_persistent_top20']}")
    print(f"Index vs PC1 Spearman: {meta['pca']['spearman_index_vs_pc1']:.3f}")
    print(f"Lens 2 LOSO RMSE: model {l2_meta['loso_rmse_model']:.1f} vs national-mean baseline {l2_meta['loso_rmse_baseline']:.1f}")
    print(f"Validation vs MICS 2021: {checks['mics_2021']}")
    print(f"Unmatched source records: {len(unmatched)} (see reports/unmatched_records.csv)")


if __name__ == "__main__":
    main()
