"""Export the processed tables to JSON for the static Wazobia Teachers site (web/).

Netlify serves static files only, so the browser app reads these JSON files and
recomputes the planner views (move or hire, budget) in web/logic.js. Every number
still comes from data/processed, built by `python -m pipeline.build`.

Usage: .venv/Scripts/python scripts/build_web.py
"""
import json
import math
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "web" / "data"

LGA_COLS = [
    "adm2_pcode", "adm2_name", "adm1_name", "learners", "teachers", "ltr", "lcr", "teachers_needed",
    "classrooms_needed", "need_score", "rank", "main_driver", "confidence", "not_ranked_reason", "caveat",
    "top20_share", "persistent_shortage", "teachers_to_exit_top20", "hidden_demand_flag", "reporting_rate",
    "nmis_share_water", "nmis_share_sanitation", "nmis_share_power", "nmis_ltr", "teachers_spare",
    "teachers_moved_in", "teachers_to_hire", "female_teacher_share", "girls_share", "jss_per_primary_cohort",
    "pry_learners", "jss_learners", "private_share", "private_reporting_rate", "ltr_change_since_2014",
    "trend_since_2014", "special_needs_share_pry", "iqte_schools", "dropout_rate_pry_all",
    "orphan_share_pry_all", "learners_per_computer_all", "learners_per_non_teaching_staff_all",
]
STATE_COLS = ["adm1_name", "waec_pass_rate", "reading", "numeracy", "oos_primary", "need_score_state", "n_ranked_lgas"]


def _clean(v):
    """JSON-safe scalar: NaN becomes null, numpy types become Python types, floats keep 6 significant digits."""
    if v is None:
        return None
    if isinstance(v, (bool,)) or type(v).__name__ == "bool_":
        return bool(v)
    if isinstance(v, str):
        return v
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None if pd.isna(v) else str(v)
    if math.isnan(f):
        return None
    return int(f) if f.is_integer() and abs(f) < 1e15 else float(f"{f:.6g}")


def records(df, cols):
    return [{c: _clean(r[c]) for c in cols} for _, r in df[cols].iterrows()]


def round_coords(obj, nd=4):
    if isinstance(obj, list):
        return [round_coords(x, nd) for x in obj]
    return round(obj, nd) if isinstance(obj, float) else obj


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    lga = pd.read_parquet(PROC / "lga_index.parquet")
    lga["caveat"] = lga.caveat.fillna("")
    states = pd.read_parquet(PROC / "state_context.parquet")
    cfg = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))

    geo = json.loads((PROC / "lga_boundaries.geojson").read_text(encoding="utf-8"))
    for f in geo["features"]:
        f["geometry"]["coordinates"] = round_coords(f["geometry"]["coordinates"])

    meta = {
        "index": json.loads((PROC / "lga_index_meta.json").read_text(encoding="utf-8")),
        "lens2": json.loads((PROC / "lens2_meta.json").read_text(encoding="utf-8")),
        "checks": json.loads((PROC / "validation.json").read_text(encoding="utf-8")),
        "insights": json.loads((PROC / "insights_meta.json").read_text(encoding="utf-8")),
        "settings": {"insights": cfg["insights"], "standards": cfg.get("standards", {})},
    }
    files = {
        "lgas.json": records(lga, LGA_COLS),
        "states.json": records(states, STATE_COLS),
        "lga_boundaries.geojson": geo,
        "meta.json": meta,
    }
    for name, obj in files.items():
        (OUT / name).write_text(json.dumps(obj, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        print(f"wrote web/data/{name} ({(OUT / name).stat().st_size / 1024:,.0f} KB)")


if __name__ == "__main__":
    main()
