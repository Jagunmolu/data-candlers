"""Data, settings and formatting shared by every part of the Dash app.

Everything is loaded once at start-up from data/processed (built by
`python -m pipeline.build`); the app makes no network calls.
"""
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import yaml

from figures import THEMES

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"

LGA = pd.read_parquet(DATA / "lga_index.parquet")
STATES = pd.read_parquet(DATA / "state_context.parquet")
GEO = json.loads((DATA / "lga_boundaries.geojson").read_text(encoding="utf-8"))
META = json.loads((DATA / "lga_index_meta.json").read_text(encoding="utf-8"))
LENS2 = json.loads((DATA / "lens2_meta.json").read_text(encoding="utf-8"))
CHECKS = json.loads((DATA / "validation.json").read_text(encoding="utf-8"))
INS = json.loads((DATA / "insights_meta.json").read_text(encoding="utf-8"))
CFG = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))["insights"]

RANKED_GRADES = ["A", "B", "C"]
RANKED = LGA[LGA.confidence.isin(RANKED_GRADES)].copy()
TOP_N = 20
ALL = "All of Nigeria"
STATE_OPTIONS = [ALL] + sorted(LGA.adm1_name.unique())
LGA_OPTIONS = [
    {"value": r.adm2_pcode, "label": f"{r.adm2_name}, {r.adm1_name}"}
    for r in LGA.sort_values(["adm1_name", "adm2_name"]).itertuples()
]

VINTAGE = "Source: Federal Ministry of Education, Annual School Census 2024 (public schools)."
GRADE_TEXT = {
    "A": "A: at least 90% of schools reported",
    "B": "B: 75-90% reported, or a data caveat",
    "C": "C: 50-75% reported",
    "Not ranked": "Not ranked: too little or implausible data",
}


def scope_view(state, grades):
    """Ranked LGAs in the selected state and grades, neediest first, and the top list."""
    view = RANKED[RANKED.confidence.isin(grades or [])]
    if state and state != ALL:
        view = view[view.adm1_name == state]
    view = view.sort_values("need_score", ascending=False)
    return view, view.head(TOP_N)


def scope_name(state):
    return "Nigeria" if not state or state == ALL else state


def slug(text):
    return text.lower().replace(" ", "_")


def fmt_int(x):
    return "n/a" if x is None or pd.isna(x) else f"{x:,.0f}"


def fmt_pct(x, digits=0):
    return "n/a" if x is None or pd.isna(x) else f"{x:.{digits}%}"


def naira(x):
    if x is None or pd.isna(x):
        return "n/a"
    for div, unit in [(1e12, " trillion"), (1e9, " billion"), (1e6, " million")]:
        if abs(x) >= div:
            return f"₦{x / div:,.1f}{unit}"
    return f"₦{x:,.0f}"


def style_fig(fig, theme):
    """Text colours and hover labels for the active theme (figures.py sets the marks)."""
    t = THEMES.get(theme, THEMES["light"])
    fig.update_layout(
        font=dict(family="Inter, Segoe UI, system-ui, sans-serif", color=t["ink2"], size=13),
        hoverlabel=dict(bgcolor=t["surface"], font_color=t["ink"], bordercolor=t["grid"]),
        legend=dict(font_color=t["ink2"]),
    )
    for tr in fig.data:
        if tr.type == "choropleth" and tr.showscale is not False:
            tr.colorbar.tickfont = dict(color=t["ink2"])
            tr.colorbar.title.font = dict(color=t["ink2"])
    return fig


def empty_fig(message, theme):
    t = THEMES.get(theme, THEMES["light"])
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font=dict(color=t["ink2"], size=14))
    fig.update_layout(height=220, xaxis_visible=False, yaxis_visible=False,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=0, b=0))
    return fig
