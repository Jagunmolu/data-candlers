"""Where Should the Next Teacher Go? Streamlit app.

Loads precomputed tables from data/processed (built by `python -m pipeline.build`),
so it starts in seconds and makes no network calls at runtime.
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from figures import need_map, state_scatter

DATA = Path(__file__).parent / "data" / "processed"
VINTAGE = "Source: Federal Ministry of Education, Annual School Census 2024 (public schools)."

GRADE_TEXT = {
    "A": "A: at least 90% of schools reported",
    "B": "B: 75-90% reported, or a data caveat",
    "C": "C: 50-75% reported",
    "Not ranked": "Not ranked: too little or implausible data",
}

st.set_page_config(page_title="Where Should the Next Teacher Go?", page_icon=":school:", layout="wide")


@st.cache_data
def load():
    lga = pd.read_parquet(DATA / "lga_index.parquet")
    states = pd.read_parquet(DATA / "state_context.parquet")
    geo = json.loads((DATA / "lga_boundaries.geojson").read_text(encoding="utf-8"))
    meta = json.loads((DATA / "lga_index_meta.json").read_text(encoding="utf-8"))
    lens2 = json.loads((DATA / "lens2_meta.json").read_text(encoding="utf-8"))
    checks = json.loads((DATA / "validation.json").read_text(encoding="utf-8"))
    return lga, states, geo, meta, lens2, checks


def fmt_int(x):
    return "n/a" if pd.isna(x) else f"{x:,.0f}"


try:
    lga, states, geo, meta, lens2, checks = load()
except FileNotFoundError:
    st.error("Processed data not found. Run `python -m pipeline.build` first, then reload this page.")
    st.stop()

TOP_N = 20
ranked = lga[lga.confidence != "Not ranked"].copy()

# ---------------------------------------------------------------- header & filters
st.title("Where should the next teacher go?")
st.markdown(
    "Nigeria's public schools, LGA by LGA, measured against the government's own "
    "**Universal Basic Education standard of 35 learners per teacher and per classroom**. "
    "Each ranking comes with a **confidence grade** showing how much of it rests on complete data."
)

demo = st.query_params.get("demo") == "1"
c1, c2, c3 = st.columns([2, 2, 1])
state_options = ["All of Nigeria"] + sorted(lga.adm1_name.unique())
state = c1.selectbox("State", state_options, index=0, help="Pick a state to see its own most-in-need LGAs.")
grades = c2.multiselect(
    "Confidence grades to include",
    ["A", "B", "C"],
    default=["A", "B", "C"],
    help="A: at least 90% of schools returned census forms. B: 75-90%, or a data caveat. C: 50-75%. "
    "LGAs below 50% are not ranked at all.",
)
c3.metric("LGAs ranked", f"{len(ranked)} of {len(lga)}", help="The rest are listed under 'Not ranked' with the reason.")

view = ranked[ranked.confidence.isin(grades)]
if state != "All of Nigeria":
    view = view[view.adm1_name == state]
view = view.sort_values("need_score", ascending=False)
top = view.head(TOP_N).copy()
top.insert(0, "Position", range(1, len(top) + 1))

tab1, tab2, tab3 = st.tabs(["Where to send teachers", "State outcome context", "Method, data and limits"])

# ---------------------------------------------------------------- tab 1: decision view
with tab1:
    scope = "Nigeria" if state == "All of Nigeria" else state
    if top.empty:
        st.info(
            f"No ranked LGAs in {scope} for the selected grades. "
            "This usually means too few schools returned census forms; see 'Not ranked' below."
        )
    else:
        need_t = top.teachers_needed.sum()
        need_c = top.classrooms_needed.sum()
        k1, k2, k3 = st.columns(3)
        k1.metric(f"Teachers needed in these {len(top)} LGAs", fmt_int(need_t),
                  help="Extra public-school teachers to reach 35 learners per teacher, at 2024 enrolment.")
        k2.metric("Classrooms needed", fmt_int(need_c),
                  help="Extra usable classrooms to reach 35 learners per classroom, at 2024 enrolment.")
        k3.metric("Learners in these LGAs", fmt_int(top.learners.sum()), help="Public-school learners, all levels, 2024.")

        st.subheader(f"The {len(top)} LGAs most in need in {scope}")
        table = pd.DataFrame({
            "#": top.Position,
            "LGA": top.adm2_name,
            "State": top.adm1_name,
            "Learners per teacher": top.ltr.round(0),
            "Learners per classroom": top.lcr.round(0),
            "Teachers needed": top.teachers_needed,
            "Classrooms needed": top.classrooms_needed,
            "Main driver": top.main_driver,
            "Confidence": top.confidence,
            "Stays in national top 20 (%)": (100 * top.top20_share).round(0),
            "Short since 2014": top.persistent_shortage.map({True: "Yes", False: ""}),
            "National rank": top["rank"].astype(int),
            "Caveat": top.caveat.fillna(""),
        })
        st.dataframe(
            table,
            hide_index=True,
            width="stretch",
            column_config={
                "Learners per teacher": st.column_config.NumberColumn(help="Standard is 35.", format="%d"),
                "Learners per classroom": st.column_config.NumberColumn(help="Standard is 35.", format="%d"),
                "Teachers needed": st.column_config.NumberColumn(format="%d"),
                "Classrooms needed": st.column_config.NumberColumn(format="%d"),
                "Main driver": st.column_config.TextColumn(
                    help="Whether this LGA is further behind other LGAs on teachers or on classrooms."),
                "Confidence": st.column_config.TextColumn(help="; ".join(GRADE_TEXT.values())),
                "Stays in national top 20 (%)": st.column_config.NumberColumn(
                    help="Share of 1,000 alternative weightings of the index in which this LGA stays in the national top 20.",
                    format="%d%%"),
                "Short since 2014": st.column_config.TextColumn(
                    help="Also in the worst quarter for learners per teacher in the independent 2014 NMIS school survey."),
            },
        )
        st.download_button(
            "Download this list (CSV)",
            table.to_csv(index=False).encode("utf-8"),
            file_name=f"priority_lgas_{scope.lower().replace(' ', '_')}.csv",
            mime="text/csv",
        )
        st.caption(VINTAGE + " Ranking compares LGAs; it does not explain causes.")

    # Map
    st.subheader("Need across LGAs")
    fig = need_map(lga, geo, view.adm2_pcode, top)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption("Darker blue = further from the 35:1 standard relative to other LGAs. Black outline = the list above. "
               "Grey = not ranked (too little or implausible data) or outside the filter. " + VINTAGE)

    # LGA detail
    st.subheader("Look at one LGA")
    options = top.adm2_name + ", " + top.adm1_name if not top.empty else pd.Series(dtype=str)
    all_opts = (lga.sort_values(["adm1_name", "adm2_name"]).adm2_name + ", " + lga.sort_values(["adm1_name", "adm2_name"]).adm1_name).tolist()
    default = options.iloc[0] if len(options) else all_opts[0]
    pick = st.selectbox("LGA", all_opts, index=all_opts.index(default))
    r = lga[(lga.adm2_name + ", " + lga.adm1_name) == pick].iloc[0]
    if r.confidence == "Not ranked":
        st.warning(f"**{pick} is not ranked.** Reason: {r.not_ranked_reason}. "
                   "Getting complete census returns from this LGA is the first action.")
    a, b, c, d = st.columns(4)
    a.metric("Learners per teacher", "n/a" if pd.isna(r.ltr) else f"{r.ltr:.0f}", help="Standard is 35.")
    b.metric("Teachers needed", fmt_int(r.teachers_needed))
    c.metric("Learners per classroom", "n/a" if pd.isna(r.lcr) else f"{r.lcr:.0f}", help="Standard is 35.")
    d.metric("Classrooms needed", fmt_int(r.classrooms_needed))
    notes = [f"**Confidence:** {GRADE_TEXT[r.confidence]}."]
    if pd.notna(r.reporting_rate):
        notes.append(f"**Census returns:** {r.reporting_rate:.0%} of expected primary-level school forms were returned.")
    if pd.notna(r.get("rank")):
        notes.append(f"**National rank:** {int(r['rank'])} of {len(ranked)}; in the national top 20 under "
                     f"{100 * r.top20_share:.0f}% of 1,000 alternative weightings.")
    if pd.notna(r.teachers_to_exit_top20):
        notes.append(f"**To leave the national top 20:** about {int(r.teachers_to_exit_top20):,} more teachers, other things equal.")
    if r.caveat:
        notes.append(f"**Caveat:** {r.caveat}.")
    if r.persistent_shortage:
        notes.append("**Long-running shortage:** also in the worst quarter for learners per teacher in the 2014 NMIS survey.")
    if r.hidden_demand_flag:
        notes.append("**Possible hidden demand:** public enrolment is under 40% of the projected school-age population, "
                     "so a ratio near the standard may hide children who are not in school (population is a 2006-based projection).")
    if pd.notna(r.nmis_share_water):
        notes.append(f"**2014 facility conditions (NMIS, public schools):** {r.nmis_share_water:.0%} had improved water, "
                     f"{r.nmis_share_sanitation:.0%} improved sanitation, {r.nmis_share_power:.0%} grid power. "
                     "These are ten years old: context, not current status.")
    st.markdown("\n\n".join(notes))

    with st.expander(f"Not ranked: {int((lga.confidence == 'Not ranked').sum())} LGAs and why"):
        nr = lga[lga.confidence == "Not ranked"]
        if state != "All of Nigeria":
            nr = nr[nr.adm1_name == state]
        st.dataframe(nr[["adm2_name", "adm1_name", "not_ranked_reason"]].rename(
            columns={"adm2_name": "LGA", "adm1_name": "State", "not_ranked_reason": "Reason"}).sort_values(["State", "LGA"]),
            hide_index=True, width="stretch")
        st.caption("These are listed rather than estimated. A planner should treat missing returns as a finding: "
                   "need here is unknown, not low.")

# ---------------------------------------------------------------- tab 2: state context
with tab2:
    st.markdown(
        "**State-level outcomes, for context only.** WAEC results are published by state, not by LGA, "
        "so they cannot rank LGAs. We show them next to independent survey measures of learning."
    )
    fig2 = state_scatter(states, highlight=state)
    st.plotly_chart(fig2, width="stretch", config={"displayModeBar": False})
    rho = checks["mics_2021"]
    st.caption("Each dot is a state. WAEC: NBS WAEC Results Statistics 2016-2018, school candidates, Taraba 2016-2017 only. "
               "Reading: UNICEF/NBS MICS6 2021.")
    st.markdown(
        f"- WAEC results and foundational reading rise and fall together across states.\n"
        f"- **We tested whether reported resources predict WAEC results. They do not, beyond the national average** "
        f"(out-of-sample error {lens2['loso_rmse_model']:.1f} points vs {lens2['loso_rmse_baseline']:.1f} for the national mean). "
        "So this tool does not label any state as over- or under-performing, and it ranks LGAs on measured gaps, not predicted results."
    )
    st.dataframe(
        states[["adm1_name", "waec_pass_rate", "reading", "numeracy", "oos_primary", "need_score_state", "n_ranked_lgas"]]
        .rename(columns={"adm1_name": "State", "waec_pass_rate": "WAEC pass rate 2016-18 (%)", "reading": "Reading 7-14 (%)",
                         "numeracy": "Numeracy 7-14 (%)", "oos_primary": "Primary out-of-school (%)",
                         "need_score_state": "Average LGA need score", "n_ranked_lgas": "LGAs ranked"})
        .round(1).sort_values("State"),
        hide_index=True, width="stretch",
    )

# ---------------------------------------------------------------- tab 3: method
with tab3:
    w = meta["weights"]
    st.markdown(f"""
### How the ranking works
1. **Measure.** For every LGA, public-school learners per teacher, per usable classroom and per usable toilet, from the 2024 Annual School Census.
2. **Grade the data.** Each LGA gets a confidence grade from the share of schools that returned census forms, plus plausibility checks (for example, reported learners far above the projected school-age population). LGAs under 50% returns, or with implausible counts, are **not ranked** and are listed with the reason.
3. **Score.** Among ranked LGAs, each ratio becomes a percentile (0 = best, 1 = worst). The need score is a weighted average: teachers {w['teacher']:.0%}, classrooms {w['classroom']:.0%}, toilets {w['toilet']:.0%}, scaled to 0-100.
4. **Size the gap.** Teachers and classrooms needed to reach 35:1 at current enrolment.

### How we checked it
- **Weights:** across 1,000 random alternative weightings, {meta['n_persistent_top20']} of the national top 20 stay in the top 20 at least 80% of the time.
- **Structure:** the score ranks LGAs almost identically to a purely statistical summary of the three ratios (first principal component, Spearman {meta['pca']['spearman_index_vs_pc1']:.2f}).
- **Independent outcomes:** states with higher average need have more children out of school and fewer with basic reading and numeracy (MICS6 2021, never used as an input):
  out-of-school {checks['mics_2021']['need_score_vs_oos_primary']['rho']:+.2f}, reading {checks['mics_2021']['need_score_vs_reading']['rho']:+.2f}, numeracy {checks['mics_2021']['need_score_vs_numeracy']['rho']:+.2f} (Spearman, 35 states).
- **Older censuses agree:** 2024 vs UBEC 2018 state learner-teacher ratio {checks['ubec_2018_state_ltr']['rho']:+.2f}; 2024 vs NMIS 2014 at LGA level {checks['nmis_2014_lga_ltr']['rho']:+.2f}.

### Data sources
| Source | Level | Year | Use | Status |
|---|---|---|---|---|
| Federal Ministry of Education, Annual School Census (DNEMIS) | LGA | 2024 | Ranking | Real, public |
| OCHA administrative boundaries (HDX) | LGA | 2019-25 | Map, name matching | Real, public, CC BY-IGO |
| UNFPA population projections (HDX) | LGA | 2020 | Plausibility checks, hidden-demand flag | Real, public, projected |
| NMIS school survey (OSSAP-MDGs, Columbia SEL) | School | 2009-14 | Long-running shortage, 2014 facilities | Real, public, CC BY 4.0 |
| NBS WAEC Results Statistics | State | 2016-18 | State context | Real, public |
| UBEC Digest of Basic Education Statistics | State | 2018 | Resource test, cross-check | Real, public |
| UNICEF/NBS MICS6 Education Fact Sheets | State | 2021 | Validation only | Real, public |

No synthetic data is used anywhere.

### Limits
- Counts are as reported by schools; the confidence grade shows where reporting is thin, but it cannot catch every error.
- The census counts public schools only. Private schools enrol many children in some LGAs, especially in cities.
- Population figures are projections from the 2006 census and are used only for checks and a flag, never for the score.
- WAEC results exist only by state; they are context, never an LGA outcome.
- This is a prioritisation aid. It shows where gaps are largest, not why.
""")
    st.caption(f"Grades: {meta['grades']}. Index settings live in config/settings.yaml; a partner's fresher census can be dropped in through the column map there.")

if demo:
    st.sidebar.markdown("**Demo mode**: fixed data, no filters changed. Walk the tabs left to right.")
