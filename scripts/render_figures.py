"""Render the app's charts to PNG for the README and write-up (needs kaleido + a local Chrome)."""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from figures import moves_bar, need_map, state_scatter  # noqa: E402
from pipeline import insights, lga_index  # noqa: E402

DATA, OUT = ROOT / "data" / "processed", ROOT / "docs" / "img"
OUT.mkdir(parents=True, exist_ok=True)

lga = pd.read_parquet(DATA / "lga_index.parquet")
states = pd.read_parquet(DATA / "state_context.parquet")
geo = json.loads((DATA / "lga_boundaries.geojson").read_text(encoding="utf-8"))
ranked = lga[lga.confidence != "Not ranked"]
top = ranked.sort_values("need_score", ascending=False).head(20)

for fig, name in ((need_map(lga, geo, ranked.adm2_pcode, top, height=700), "map_national.png"),
                  (state_scatter(states), "state_context.png"),
                  (moves_bar(insights.redeployment_by_state(lga, lga_index.load_settings()["insights"]["redeploy"]["movable_share"]), height=720),
                   "move_or_hire.png")):
    fig.update_layout(paper_bgcolor="#fcfcfb", plot_bgcolor="#fcfcfb", font=dict(family="Segoe UI, sans-serif", color="#0b0b0b"))
    fig.write_image(OUT / name, width=1000, height=fig.layout.height, scale=1.5)
    print("wrote", OUT / name)
