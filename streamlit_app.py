"""Where Should the Next Teacher Go? Streamlit app.

Loads precomputed tables from data/processed (built by `python -m pipeline.build`),
so it starts in seconds and makes no network calls at runtime.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

import yaml

from figures import lga_scatter, moves_bar, need_map, state_scatter
from pipeline import insights

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
    ins = json.loads((DATA / "insights_meta.json").read_text(encoding="utf-8"))
    return lga, states, geo, meta, lens2, checks, ins


def fmt_int(x):
    return "n/a" if pd.isna(x) else f"{x:,.0f}"


def fmt_pct(x):
    return "n/a" if pd.isna(x) else f"{x:.0%}"


def naira(x):
    if pd.isna(x):
        return "n/a"
    for div, unit in [(1e12, " trillion"), (1e9, " billion"), (1e6, " million")]:
        if abs(x) >= div:
            return f"₦{x / div:,.1f}{unit}"
    return f"₦{x:,.0f}"


try:
    lga, states, geo, meta, lens2, checks, ins_meta = load()
    CFG = yaml.safe_load((Path(__file__).parent / "config" / "settings.yaml").read_text(encoding="utf-8"))["insights"]
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
if demo:
    st.info(
        "**Demo path** (fixed data, same every time): "
        "1. National top 20 and the totals. "
        "2. Map: dark blue = need, grey = not ranked. "
        "3. Pick **Kano** in State: a state planner's own list. "
        "4. Back to All of Nigeria; in 'Look at one LGA' read **Olorunsogo, Oyo**. "
        "5. Open 'Not ranked'. "
        "6. Tab 'State outcome context'. "
        "7. Tab 'Method, data and limits'."
    )
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

tab1, tab_move, tab_budget, tab_beyond, tab2, tab3 = st.tabs([
    "Where to send teachers", "Move or hire?", "Budget planner", "Beyond the ratio", "State outcome context",
    "Method, data and limits",
])

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
            "Still to hire after moves": top.teachers_to_hire,
            "Women teachers (%)": (100 * top.female_teacher_share).round(0),
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
                "Still to hire after moves": st.column_config.NumberColumn(format="%d",
                    help="Teachers needed after every spare teacher in the same state has moved to the neediest LGAs first. See 'Move or hire?'."),
                "Women teachers (%)": st.column_config.NumberColumn(format="%d%%", help="Share of public-school teachers who are women."),
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
    if pd.notna(r.teachers_spare) and r.teachers_needed > 0:
        notes.append(f"**Move or hire:** if every spare teacher in {r.adm1_name} moved, about {fmt_int(r.teachers_moved_in)} "
                     f"could come to this LGA; about {fmt_int(r.teachers_to_hire)} would still need to be hired.")
    elif pd.notna(r.teachers_spare) and r.teachers_spare > 0:
        notes.append(f"**Spare teachers:** about {fmt_int(r.teachers_spare)} above what 35:1 needs, so this LGA could give teachers to short LGAs in {r.adm1_name}.")
    if pd.notna(r.trend_since_2014):
        notes.append(f"**Since 2014:** learners per teacher {r.nmis_ltr:.0f} (NMIS 2014) to {r.ltr:.0f} (2024), "
                     f"{r.ltr_change_since_2014:+.0%}: {r.trend_since_2014.lower()}.")
    st.markdown("\n\n".join(notes))

    ctx = [
        ("Women among public teachers", fmt_pct(r.female_teacher_share)),
        ("Girls among public learners", fmt_pct(r.girls_share)),
        ("JSS learners per primary cohort", "n/a" if pd.isna(r.jss_per_primary_cohort) else f"{r.jss_per_primary_cohort:.2f}"),
        ("Private schools' share of learners", fmt_pct(r.private_share)),
        ("Primary learners with special needs (public)", fmt_pct(r.special_needs_share_pry)),
        ("Integrated Qur'anic (IQS/IQTE) public schools", fmt_int(r.get("iqte_schools"))),
        ("Primary dropout rate (all schools)", "n/a" if pd.isna(r.dropout_rate_pry_all) else f"{r.dropout_rate_pry_all:.1%}"),
        ("Primary learners who are orphans (all schools)", fmt_pct(r.orphan_share_pry_all)),
        ("Learners per usable computer (all schools)", fmt_int(r.learners_per_computer_all)),
        ("Learners per non-teaching staff (all schools)", fmt_int(r.learners_per_non_teaching_staff_all)),
    ]
    with st.expander("More about this LGA (2024 census)"):
        st.dataframe(pd.DataFrame(ctx, columns=["Measure", "Value"]), hide_index=True, width="stretch")
        st.caption("Context, not part of the score. 'All schools' measures are published only for public and private schools "
                   "together. JSS and private figures are shown only where enough census forms came back. " + VINTAGE)

    with st.expander(f"Not ranked: {int((lga.confidence == 'Not ranked').sum())} LGAs and why"):
        nr = lga[lga.confidence == "Not ranked"]
        if state != "All of Nigeria":
            nr = nr[nr.adm1_name == state]
        st.dataframe(nr[["adm2_name", "adm1_name", "not_ranked_reason"]].rename(
            columns={"adm2_name": "LGA", "adm1_name": "State", "not_ranked_reason": "Reason"}).sort_values(["State", "LGA"]),
            hide_index=True, width="stretch")
        st.caption("These are listed rather than estimated. A planner should treat missing returns as a finding: "
                   "need here is unknown, not low.")

# ---------------------------------------------------------------- tab: move or hire
with tab_move:
    st.markdown(
        "**Can short LGAs be fixed by moving teachers from LGAs that have more than the standard needs?** "
        "Teachers are employed by the state, so moves stay inside each state. Spare teachers go to the neediest LGAs first."
    )
    movable = st.slider(
        "Share of spare teachers who could realistically move", 0, 100, int(100 * CFG["redeploy"]["movable_share"]), 5,
        format="%d%%",
        help="Spare = teachers above what 35:1 needs at current enrolment. 100% is the theoretical upper bound: "
        "in practice subject, level, family and security limit who can move. No dataset records this, so you set it.",
    ) / 100
    moves = insights.allocate_moves(lga, movable)
    lga_m = lga.join(moves)
    by_state = insights.redeployment_by_state(lga, movable)
    scope_m = by_state if state == "All of Nigeria" else by_state[by_state.adm1_name == state]
    short, cov = scope_m.shortfall.sum(), scope_m.covered_by_moves.sum()
    if scope_m.empty:
        st.info(f"No ranked LGAs in {scope}, so moves cannot be assessed. See 'Not ranked' on the first tab.")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric(f"Teacher shortfall, {scope}", fmt_int(short), help="Ranked LGAs only (grades A-C).")
        m2.metric("Could be covered by moves", fmt_int(cov), help=f"With {movable:.0%} of spare teachers moving within the state.")
        m3.metric("Still to hire", fmt_int(short - cov), delta=f"moves cover {cov / short:.0%}" if short else None,
                  delta_color="off")
    if state == "All of Nigeria":
        rd = ins_meta["redeploy"]
        st.markdown(
            f"Even if **every** teacher above the standard moved, moves would cover **{rd['share_covered']:.0%}** of the "
            f"national shortfall ({rd['covered_by_moves']:,} of {rd['shortfall']:,}). Spare teachers sit mostly in "
            f"{', '.join(rd['top_spare_states'])}, while the shortfall is elsewhere. In {rd['states_with_spare_over_shortfall']} "
            "states, moving teachers could close the state's own gap; in the rest, **hiring is the main route**."
        )
        st.plotly_chart(moves_bar(by_state), width="stretch", config={"displayModeBar": False})
        st.caption("Ranked LGAs only. Moves never cross state lines. " + VINTAGE)
    else:
        lg = lga_m[(lga_m.adm1_name == state) & lga_m.confidence.isin(["A", "B", "C"])]
        st.subheader(f"LGAs in {state}: who gives, who receives")
        t = pd.DataFrame({
            "LGA": lg.adm2_name, "Learners per teacher": lg.ltr.round(0), "Teachers short": lg.teachers_needed,
            "Spare teachers": lg.teachers_spare, "Receives from moves": lg.moved_in,
            "Gives (approx.)": lg.moved_out.round(0), "Still to hire": lg.to_hire, "Need score": lg.need_score.round(0),
        }).sort_values("Need score", ascending=False)
        st.dataframe(t, hide_index=True, width="stretch")
        st.download_button("Download this plan (CSV)", t.to_csv(index=False).encode("utf-8"),
                           file_name=f"move_or_hire_{state.lower().replace(' ', '_')}.csv", mime="text/csv")
        st.caption("Donors give in proportion to their spare teachers and keep enough for 35:1. " + VINTAGE)
    with st.expander("All states"):
        st.dataframe(
            by_state.rename(columns={
                "adm1_name": "State", "lgas_ranked": "LGAs ranked", "shortfall": "Teachers short",
                "spare": "Spare teachers", "covered_by_moves": "Covered by moves", "to_hire": "Still to hire",
                "share_covered": "Share covered"}),
            hide_index=True, width="stretch",
            column_config={"Share covered": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1)},
        )
    st.caption("A spare teacher may teach a subject or level that a short LGA does not need, so the moves shown "
               "are an upper bound at your chosen share.")

# ---------------------------------------------------------------- tab: budget planner
with tab_budget:
    st.markdown(
        "**Turn the list into a budget line.** No public dataset gives teacher or classroom unit costs for each state, "
        "so enter your own. The planner funds LGAs in priority order until the budget runs out."
    )
    b1, b2, b3 = st.columns(3)
    t_cost = b1.number_input("Cost per new teacher (₦)", min_value=0, value=None, step=100_000, placeholder="e.g. one year's pay",
                             help="Everything a new teacher costs over the period you are budgeting for: pay, allowances, "
                             "posting and training.")
    c_cost = b2.number_input("Cost per classroom (₦)", min_value=0, value=None, step=1_000_000, placeholder="build or rehabilitate",
                             help="Average cost to add one usable classroom, from your own contract rates.")
    budget = b3.number_input("Budget available (₦)", min_value=0, value=None, step=100_000_000, placeholder="total for this scope")
    o1, o2, o3 = st.columns(3)
    which = o1.radio("LGAs to fund", [f"The top {len(top)} list", f"All {len(view)} ranked LGAs in scope"], horizontal=False)
    use_moves = o2.checkbox("Move spare teachers first", value=True,
                            help=f"Uses the share set on 'Move or hire?' ({movable:.0%}). Moved teachers cost nothing extra here.")
    with_rooms = o3.checkbox("Include classrooms", value=True)

    pool = (top if which.startswith("The top") else view).join(moves, rsuffix="_m")
    pool = pool.sort_values("need_score", ascending=False)
    pool["teachers_to_fund"] = pool.to_hire if use_moves else pool.teachers_needed
    if not with_rooms:
        pool = pool.assign(classrooms_needed=0)

    st.markdown(
        f"**What the gap is, before costs:** {fmt_int(pool.teachers_to_fund.sum())} teachers to hire"
        + (f" (after {fmt_int(pool.moved_in.sum())} moved in)" if use_moves else "")
        + (f" and {fmt_int(pool.classrooms_needed.sum())} classrooms" if with_rooms else "")
        + f" across {len(pool)} LGAs."
    )
    if pool.empty:
        st.info(f"No ranked LGAs in {scope} for the selected grades.")
    elif t_cost is None or (with_rooms and c_cost is None):
        st.info("Enter the unit costs above to see what the gap costs. Add a budget to see how far it goes.")
    else:
        c_cost = c_cost or 0
        full = pool.teachers_to_fund.sum() * t_cost + pool.classrooms_needed.sum() * c_cost
        plan = insights.budget_plan(pool, t_cost, c_cost, budget if budget is not None else full, teachers_col="teachers_to_fund")
        k1, k2, k3 = st.columns(3)
        k1.metric("Cost to close the whole gap", naira(full))
        if budget is not None:
            n_full = int((plan.status == "Fully funded").sum())
            k2.metric("LGAs fully funded", f"{n_full} of {len(pool)}")
            k3.metric("Budget covers", f"{min(budget / full, 1):.0%}" if full else "100%",
                      help="Share of the full cost this budget pays for.")
        out = pool.join(plan)
        t = pd.DataFrame({
            "Priority": range(1, len(out) + 1), "LGA": out.adm2_name, "State": out.adm1_name,
            "Teachers to hire": out.teachers_to_fund, "Teachers funded": out.teachers_funded,
            "Classrooms needed": out.classrooms_needed, "Classrooms funded": out.classrooms_funded,
            "Cost of full gap (₦)": out.cost_full_gap.round(0), "Funded (₦)": out.cost_funded.round(0), "Status": out.status,
        })
        st.dataframe(t, hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="localized") for c in ["Cost of full gap (₦)", "Funded (₦)"]})
        st.download_button("Download this budget (CSV)", t.to_csv(index=False).encode("utf-8"),
                           file_name=f"budget_{scope.lower().replace(' ', '_')}.csv", mime="text/csv")
        st.caption("Costs are your inputs, not data. Gaps: " + VINTAGE + " Each LGA's full gap is funded before the next; "
                   "the last LGA reached is funded in part, teachers first.")

# ---------------------------------------------------------------- tab: beyond the ratio
def flagged_table(d, cols, key):
    """Flagged LGAs in scope, neediest first, with a CSV download."""
    t = d.sort_values("need_score", ascending=False)
    out = pd.DataFrame({"LGA": t.adm2_name, "State": t.adm1_name, "National rank": t["rank"].astype(int),
                        "Learners per teacher": t.ltr.round(0), **{k: f(t) for k, f in cols.items()},
                        "Confidence": t.confidence})
    st.dataframe(out, hide_index=True, width="stretch", height=min(38 * (len(out) + 1), 320))
    st.download_button("Download (CSV)", out.to_csv(index=False).encode("utf-8"), file_name=f"{key}_{scope.lower().replace(' ', '_')}.csv",
                       mime="text/csv", key=f"dl_{key}")


with tab_beyond:
    st.markdown(
        f"**What else the census says about the LGAs on the list** ({scope}, ranked LGAs in the selected grades). "
        "Each section has its own threshold, which you can change. These describe where gaps sit together; they do not explain causes."
    )
    top_codes = top.adm2_pcode

    # Female teachers
    st.subheader("1. Where are there few women teachers?")
    ft = st.slider("Flag LGAs where women are fewer than", 5, 50, int(100 * CFG["female_teachers"]["share_below"]), 5,
                   format="%d%% of public teachers", key="ft") / 100
    d = view[view.female_teacher_share.notna()]
    flag = d[d.female_teacher_share < ft]
    fm = ins_meta["female_teachers"]
    st.markdown(
        f"**{len(flag)} of {len(d)}** LGAs in scope are below {ft:.0%} ({flag.adm2_pcode.isin(top_codes).sum()} of the top {len(top)}). "
        f"Nationally the median LGA has {fm['median_share']:.0%} women teachers, and LGAs with higher need tend to have fewer "
        f"(Spearman {fm['need_vs_female_share']['rho']:+.2f}, {fm['need_vs_female_share']['n']} LGAs). "
        "Where the list sends new teachers to these LGAs, recruiting women is worth planning for."
    )
    st.plotly_chart(lga_scatter(d, "female_teacher_share", "need_score", "Women among public teachers", "Need score",
                                fmt_x=".0%", fmt_y=".0f", highlight=top_codes), width="stretch", config={"displayModeBar": False})
    st.caption("Black outline = the current top list. " + VINTAGE)
    with st.expander(f"{len(flag)} LGAs below {ft:.0%}"):
        flagged_table(flag, {"Women teachers": lambda t: (100 * t.female_teacher_share).round(0),
                             "Girls among learners (%)": lambda t: (100 * t.girls_share).round(0)}, "few_women_teachers")

    # Junior secondary places
    st.subheader("2. Is there a junior secondary seat after primary?")
    target = st.slider("Target share of a primary cohort with a public JSS seat", 50, 100,
                       int(100 * CFG["jss"]["target_transition"]), 5, format="%d%%", key="jss",
                       help="UBE covers nine years, so the policy target is 100%. Lower it to plan in stages.") / 100
    d = view[view.jss_per_primary_cohort.notna()].copy()
    d["gap"] = insights.jss_places_gap(d, target)
    jm = ins_meta["jss"]
    st.markdown(
        f"For one primary grade of learners, the median LGA nationally has **{jm['median_jss_per_primary_cohort']:.2f}** learners "
        f"in one public JSS grade. LGAs with higher primary need also tend to have fewer JSS learners per cohort "
        f"(Spearman {jm['need_vs_jss']['rho']:+.2f}, {jm['need_vs_jss']['n']} LGAs). In scope, reaching {target:.0%} "
        f"would take about **{fmt_int(d.gap.sum())} more public JSS places** ({fmt_int(np.ceil(d.gap.sum() / 35))} classrooms at 35:1)."
    )
    st.plotly_chart(lga_scatter(d, "jss_per_primary_cohort", "need_score", "JSS learners per primary cohort", "Need score",
                                fmt_x=".2f", highlight=top_codes), width="stretch", config={"displayModeBar": False})
    st.caption("Shown only where at least 75% of JSS census forms were returned. Public schools only: private JSS places, "
               "over-age primary learners and children schooling in a neighbouring LGA all affect this ratio. " + VINTAGE)
    with st.expander(f"LGAs in scope by JSS places needed at {target:.0%}"):
        flagged_table(d[d.gap > 0], {"JSS per primary cohort": lambda t: t.jss_per_primary_cohort.round(2),
                                     "JSS places needed": lambda t: t.gap}, "jss_places")

    # Private alternative
    st.subheader("3. Is there a private-school alternative?")
    pt = st.slider("Flag LGAs where private schools hold fewer than", 1, 30, int(100 * CFG["private"]["share_below"]), 1,
                   format="%d%% of learners", key="prv") / 100
    d = view[view.private_share.notna()]
    flag = d[d.private_share < pt]
    pm = ins_meta["private"]
    st.markdown(
        f"Only **{pm['national_private_return_rate']:.0%}** of expected private-school census forms were returned nationally, "
        f"so this is shown for the {len(d)} LGAs in scope where at least half came back. Of these, **{len(flag)}** have private "
        f"schools holding under {pt:.0%} of learners: public schools are effectively the only option there. LGAs with higher "
        f"need tend to have smaller private shares (Spearman {pm['need_vs_private_share']['rho']:+.2f}, {pm['need_vs_private_share']['n']} LGAs)."
    )
    st.plotly_chart(lga_scatter(d, "private_share", "need_score", "Private schools' share of learners", "Need score",
                                highlight=top_codes), width="stretch", config={"displayModeBar": False})
    st.caption("Private share = private learners / (private + public learners), all levels. " + VINTAGE)
    with st.expander(f"{len(flag)} LGAs below {pt:.0%}"):
        flagged_table(flag, {"Private share (%)": lambda t: (100 * t.private_share).round(1),
                             "Private returns (%)": lambda t: (100 * t.private_reporting_rate).round(0)}, "few_private")

    # Change since 2014
    st.subheader("4. Better or worse than in 2014?")
    ct = st.slider("Label a change only if learners per teacher moved by more than", 10, 50,
                   int(100 * CFG["change_since_2014"]["threshold"]), 5, format="%d%%", key="chg",
                   help="The 2014 NMIS survey and the 2024 census are different instruments, so small changes are not labelled.") / 100
    d = view[view.ltr_change_since_2014.notna()].copy()
    d["trend"] = np.select([d.ltr_change_since_2014 > ct, d.ltr_change_since_2014 < -ct], ["Worse", "Better"], "Similar")
    counts = d.trend.value_counts()
    st.markdown(
        f"Of {len(d)} LGAs in scope measured both times, **{counts.get('Worse', 0)} have more learners per teacher than in 2014**, "
        f"{counts.get('Similar', 0)} are similar and {counts.get('Better', 0)} improved by more than {ct:.0%}."
    )
    st.plotly_chart(lga_scatter(d, "nmis_ltr", "ltr", "Learners per teacher, 2014 (NMIS)", "Learners per teacher, 2024",
                                fmt_x=".0f", diagonal=True, highlight=top_codes), width="stretch", config={"displayModeBar": False})
    st.caption("Dots above the dotted line have more learners per teacher than in 2014. NMIS: OSSAP-MDGs and Columbia SEL, "
               "public schools surveyed 2009-2014 (CC BY 4.0). " + VINTAGE)
    with st.expander(f"{counts.get('Worse', 0)} LGAs worse than 2014"):
        flagged_table(d[d.trend == "Worse"], {"2014": lambda t: t.nmis_ltr.round(0),
                                              "Change (%)": lambda t: (100 * t.ltr_change_since_2014).round(0)}, "worse_since_2014")

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

