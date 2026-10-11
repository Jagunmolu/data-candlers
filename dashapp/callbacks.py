"""All callbacks. Calculations come from pipeline/insights.py, the same code the build uses."""
import dash_mantine_components as dmc
import numpy as np
import pandas as pd
from dash import Input, Output, State, callback, clientside_callback, ctx, dcc, html, no_update

from dashapp.common import (
    ALL, CHECKS, GEO, GRADE_TEXT, INS, LENS2, LGA, META, RANKED, STATES, VINTAGE, empty_fig, fmt_int, fmt_pct, naira,
    scope_name, scope_view, slug, style_fig,
)
from dashapp.layout import GRADE_HELP, export_button, grid, grid_data, kpi
from figures import lga_scatter, moves_bar, need_map, state_scatter
from pipeline import insights

THEME_IN = Input("theme", "data")


def flag_on(x):
    return x is not None and not (isinstance(x, float) and np.isnan(x)) and bool(x)


def theme_of(data):
    return data if data in ("light", "dark") else "light"


def words(theme):
    return ("Darker blue", "Black") if theme == "light" else ("Brighter blue", "White")


# ---------------------------------------------------------------- theme switch
# First visit follows the device; afterwards the viewer's choice is remembered.
clientside_callback(
    """
    function(_, stored) {
        if (stored === 'dark' || stored === 'light') { return stored === 'dark'; }
        return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    """,
    Output("theme-switch", "checked"),
    Input("url", "pathname"),
    State("theme", "data"),
)
clientside_callback(
    """
    function(dark) {
        const mode = dark ? 'dark' : 'light';
        document.documentElement.setAttribute('data-mantine-color-scheme', mode);
        document.body.setAttribute('data-ag-theme-mode', mode);
        return mode;
    }
    """,
    Output("theme", "data"),
    Input("theme-switch", "checked"),
)


@callback(Output("demo-banner", "children"), Input("url", "search"))
def demo_banner(search):
    if "demo=1" not in (search or ""):
        return None
    steps = [
        "National top 20 and the totals.", "Map: stronger blue = more need, grey = not ranked.",
        "Pick Kano in State: a state planner's own list.",
        "Back to All of Nigeria; click Olorunsogo (Oyo) in the table, then open 'Not ranked'.",
        "Tab 'Move or hire?': moves cover only a small share; lower the slider.",
        "Tab 'Budget planner': enter your cost assumptions and a budget.",
        "Tab 'Beyond the ratio': women teachers, JSS seats, private schools, since 2014.",
        "Tab 'State outcome context'.", "Tab 'Method, data and limits'.",
    ]
    return dmc.Alert(dmc.List([dmc.ListItem(s) for s in steps], type="ordered", size="sm"),
                     title="Demo path (fixed data, same every time)", color="blue", variant="light")


# ---------------------------------------------------------------- tab 1: decision view
TOP_FORMATS = {"Stays in national top 20 (%)": "int", "Women teachers (%)": "int"}


@callback(
    Output("k-teachers", "children"), Output("k-rooms", "children"), Output("k-learners", "children"),
    Output("top-title", "children"), Output("top-grid", "rowData"), Output("top-grid", "columnDefs"),
    Output("top-grid", "csvExportParams"), Output("map", "figure"), Output("map-caption", "children"),
    Output("nr-title", "children"), Output("nr-grid", "rowData"), Output("nr-grid", "columnDefs"),
    Input("state", "value"), Input("grades", "value"), THEME_IN,
)
def decision_view(state, grades, theme):
    theme = theme_of(theme)
    view, top = scope_view(state, grades)
    scope = scope_name(state)
    table = pd.DataFrame({
        "#": range(1, len(top) + 1), "LGA": top.adm2_name, "State": top.adm1_name,
        "Learners per teacher": top.ltr.round(0), "Learners per classroom": top.lcr.round(0),
        "Teachers needed": top.teachers_needed, "Classrooms needed": top.classrooms_needed,
        "Main driver": top.main_driver, "Confidence": top.confidence,
        "Stays in national top 20 (%)": (100 * top.top20_share).round(0),
        "Short since 2014": top.persistent_shortage.map({True: "Yes", False: ""}),
        "Still to hire after moves": top.teachers_to_hire, "Women teachers (%)": (100 * top.female_teacher_share).round(0),
        "National rank": top["rank"], "Caveat": top.caveat.fillna(""), "pcode": top.adm2_pcode,
    })
    rows, defs = grid_data(table, TOP_FORMATS)
    defs[-1]["hide"] = True
    for d in defs:
        if d["headerName"] == "Confidence":
            d["headerTooltip"] = GRADE_HELP
    title = f"The {len(top)} LGAs most in need in {scope}" if len(top) else (
        f"No ranked LGAs in {scope} for the selected grades: too few schools returned census forms. See 'Not ranked' below.")

    fig = style_fig(need_map(LGA, GEO, view.adm2_pcode, top, height=560, theme=theme), theme)
    need_w, out_w = words(theme)
    cap = (f"{need_w} = further from the 35:1 standard relative to other LGAs. {out_w} outline = the list. Grey = not ranked "
           f"(too little or implausible data) or outside the filter. Click an LGA to open it. {VINTAGE}")

    nr = LGA[LGA.confidence == "Not ranked"]
    if state and state != ALL:
        nr = nr[nr.adm1_name == state]
    nr_rows, nr_defs = grid_data(nr.sort_values(["adm1_name", "adm2_name"])[["adm2_name", "adm1_name", "not_ranked_reason"]]
                                 .rename(columns={"adm2_name": "LGA", "adm1_name": "State", "not_ranked_reason": "Reason"}))
    return (
        fmt_int(top.teachers_needed.sum()), fmt_int(top.classrooms_needed.sum()), fmt_int(top.learners.sum()),
        title, rows, defs, {"fileName": f"priority_lgas_{slug(scope)}.csv", "columnKeys": [d["field"] for d in defs[:-1]]},
        fig, cap, f"Not ranked: {len(nr)} LGAs{'' if not state or state == ALL else ' in ' + state} and why", nr_rows, nr_defs,
    )


@callback(
    Output("lga", "value"),
    Input("state", "value"), Input("grades", "value"), Input("map", "clickData"), Input("top-grid", "cellClicked"),
    State("top-grid", "rowData"), State("top-grid", "columnDefs"),
)
def pick_lga(state, grades, click, cell, rows, defs):
    trig = ctx.triggered_id
    if trig == "map" and click:
        return click["points"][0].get("location", no_update)
    if trig == "top-grid" and cell and rows:
        pfield = next(d["field"] for d in defs if d["headerName"] == "pcode")
        return rows[cell["rowIndex"]][pfield] if cell.get("rowIndex") is not None else no_update
    _, top = scope_view(state, grades)
    return top.adm2_pcode.iloc[0] if len(top) else LGA.sort_values(["adm1_name", "adm2_name"]).adm2_pcode.iloc[0]


def metric(label, value, hint=None):
    t = dmc.Text(label, size="xs", c="dimmed")
    return dmc.Paper([dmc.Tooltip(t, label=hint) if hint else t, dmc.Text(value, fz=22, fw=650)], p="xs", withBorder=True, radius="md")


@callback(Output("lga-detail", "children"), Input("lga", "value"))
def lga_detail(pcode):
    if not pcode:
        return None
    r = LGA.set_index("adm2_pcode").loc[pcode]
    name = f"{r.adm2_name}, {r.adm1_name}"
    out = []
    if r.confidence == "Not ranked":
        out.append(dmc.Alert(f"Reason: {r.not_ranked_reason}. Getting complete census returns from this LGA is the first action.",
                             title=f"{name} is not ranked", color="yellow", variant="light", mb="sm"))
    out.append(dmc.SimpleGrid([
        metric("Learners per teacher", "n/a" if pd.isna(r.ltr) else f"{r.ltr:.0f}", "Standard is 35."),
        metric("Teachers needed", fmt_int(r.teachers_needed)),
        metric("Learners per classroom", "n/a" if pd.isna(r.lcr) else f"{r.lcr:.0f}", "Standard is 35."),
        metric("Classrooms needed", fmt_int(r.classrooms_needed)),
    ], cols=2, spacing="xs"))
    notes = [f"**Confidence:** {GRADE_TEXT[r.confidence]}."]
    if pd.notna(r.reporting_rate):
        notes.append(f"**Census returns:** {r.reporting_rate:.0%} of expected primary-level school forms were returned.")
    if pd.notna(r["rank"]):
        notes.append(f"**National rank:** {int(r['rank'])} of {len(RANKED)}; in the national top 20 under "
                     f"{100 * r.top20_share:.0f}% of 1,000 alternative weightings.")
    if pd.notna(r.teachers_to_exit_top20):
        notes.append(f"**To leave the national top 20:** about {int(r.teachers_to_exit_top20):,} more teachers, other things equal.")
    if r.caveat:
        notes.append(f"**Caveat:** {r.caveat}.")
    if flag_on(r.persistent_shortage):
        notes.append("**Long-running shortage:** also in the worst quarter for learners per teacher in the 2014 NMIS survey.")
    if flag_on(r.hidden_demand_flag):
        notes.append("**Possible hidden demand:** public enrolment is under 40% of the projected school-age population, so a "
                     "ratio near the standard may hide children who are not in school (2006-based projection).")
    if pd.notna(r.teachers_spare) and r.teachers_needed > 0 and r.teachers_moved_in > 0:
        notes.append(f"**Move or hire:** if every spare teacher in {r.adm1_name} moved, about {fmt_int(r.teachers_moved_in)} "
                     f"could come here; about {fmt_int(r.teachers_to_hire)} would still need to be hired.")
    elif pd.notna(r.teachers_spare) and r.teachers_needed > 0:
        notes.append(f"**Move or hire:** moving teachers within {r.adm1_name} would not reach this LGA (the state's spare "
                     f"teachers, if any, go to needier LGAs first), so all {fmt_int(r.teachers_to_hire)} would need to be hired.")
    elif pd.notna(r.teachers_spare) and r.teachers_spare > 0:
        notes.append(f"**Spare teachers:** about {fmt_int(r.teachers_spare)} above what 35:1 needs, so this LGA could give "
                     f"teachers to short LGAs in {r.adm1_name}.")
    if pd.notna(r.trend_since_2014):
        notes.append(f"**Since 2014:** learners per teacher {r.nmis_ltr:.0f} (NMIS 2014) to {r.ltr:.0f} (2024), "
                     f"{r.ltr_change_since_2014:+.0%}: {r.trend_since_2014.lower()}.")
    if pd.notna(r.nmis_share_water):
        notes.append(f"**2014 facility conditions (NMIS, public schools):** {r.nmis_share_water:.0%} improved water, "
                     f"{r.nmis_share_sanitation:.0%} improved sanitation, {r.nmis_share_power:.0%} grid power. Context, not current status.")
    out.append(dcc.Markdown("\n\n".join(notes), style={"marginTop": 12, "fontSize": 14}))
    ctx_rows = [
        ("Women among public teachers", fmt_pct(r.female_teacher_share)),
        ("Girls among public learners", fmt_pct(r.girls_share)),
        ("JSS learners per primary cohort", "n/a" if pd.isna(r.jss_per_primary_cohort) else f"{r.jss_per_primary_cohort:.2f}"),
        ("Private schools' share of learners", fmt_pct(r.private_share)),
        ("Primary learners with special needs (public)", fmt_pct(r.special_needs_share_pry)),
        ("Integrated Qur'anic (IQS/IQTE) public schools", fmt_int(r.iqte_schools)),
        ("Primary dropout rate (all schools)", fmt_pct(r.dropout_rate_pry_all, 1)),
        ("Primary learners who are orphans (all schools)", fmt_pct(r.orphan_share_pry_all)),
        ("Learners per usable computer (all schools)", fmt_int(r.learners_per_computer_all)),
        ("Learners per non-teaching staff (all schools)", fmt_int(r.learners_per_non_teaching_staff_all)),
    ]
    out.append(dmc.Accordion([dmc.AccordionItem([
        dmc.AccordionControl("More about this LGA (2024 census)"),
        dmc.AccordionPanel([
            dmc.Table(data={"head": ["Measure", "Value"], "body": [list(x) for x in ctx_rows]}, striped=True, fz="sm"),
            dmc.Text("Context, not part of the score. 'All schools' measures are published only for public and private "
                     "schools together. JSS and private figures appear only where enough forms came back.", size="xs", c="dimmed"),
        ]),
    ], value="more")], variant="contained", mt="xs"))
    return out


# ---------------------------------------------------------------- tab 2: move or hire
@callback(
    Output("m-short", "children"), Output("m-cov", "children"), Output("m-hire", "children"),
    Output("move-text", "children"), Output("move-body", "children"),
    Output("states-grid", "rowData"), Output("states-grid", "columnDefs"),
    Input("state", "value"), Input("movable", "value"), THEME_IN,
)
def move_view(state, movable, theme):
    theme, share = theme_of(theme), (movable or 0) / 100
    by_state = insights.redeployment_by_state(LGA, share)
    rows, defs = grid_data(by_state.rename(columns={
        "adm1_name": "State", "lgas_ranked": "LGAs ranked", "shortfall": "Teachers short", "spare": "Spare teachers",
        "covered_by_moves": "Covered by moves", "to_hire": "Still to hire", "share_covered": "Share covered"}),
        {"Share covered": "pct"}, pinned=("State",))
    scope_m = by_state if not state or state == ALL else by_state[by_state.adm1_name == state]
    if scope_m.empty:
        return "n/a", "n/a", "n/a", f"No ranked LGAs in {state}, so moves cannot be assessed.", None, rows, defs
    short, cov = scope_m.shortfall.sum(), scope_m.covered_by_moves.sum()
    covered = fmt_int(cov) + (f" ({cov / short:.0%})" if short else "")
    if not state or state == ALL:
        rd = INS["redeploy"]
        text = (f"At {share:.0%}, moves would cover **{cov / short:.0%}** of the national shortfall. Even if **every** teacher "
                f"above the standard moved, they would cover **{rd['share_covered']:.0%}** ({rd['covered_by_moves']:,} of "
                f"{rd['shortfall']:,}). Spare teachers sit mostly in {', '.join(rd['top_spare_states'])}. Moves could close the gap in "
                f"{rd['states_moves_close_gap']} states; the {rd['states_moves_fall_short']} states where they fall short hold "
                f"{rd['shortfall_share_in_those_states']:.0%} of the shortfall, so there **hiring is the main route**.")
        body = [dcc.Graph(figure=style_fig(moves_bar(by_state, height=720, theme=theme), theme), config={"displayModeBar": False}),
                dmc.Text("Ranked LGAs only. Moves never cross state lines. " + VINTAGE, size="xs", c="dimmed")]
    else:
        moves = insights.allocate_moves(LGA, share)
        lg = LGA.join(moves)
        lg = lg[(lg.adm1_name == state) & lg.confidence.isin(["A", "B", "C"])].sort_values("need_score", ascending=False)
        t = pd.DataFrame({
            "LGA": lg.adm2_name, "Learners per teacher": lg.ltr.round(0), "Teachers short": lg.teachers_needed,
            "Spare teachers": lg.teachers_spare, "Receives from moves": lg.moved_in, "Gives (approx.)": lg.moved_out.round(0),
            "Still to hire": lg.to_hire, "Need score": lg.need_score.round(0)})
        r2, d2 = grid_data(t)
        g = grid("move-lga-grid", 440)
        g.rowData, g.columnDefs, g.csvExportParams = r2, d2, {"fileName": f"move_or_hire_{slug(state)}.csv"}
        text = f"**LGAs in {state}: who gives, who receives.** Donors give in proportion to their spare teachers and keep enough for 35:1."
        body = [g, export_button("move-lga-export"), dmc.Text(VINTAGE, size="xs", c="dimmed")]
    return fmt_int(short), covered, fmt_int(short - cov), text, body, rows, defs


# ---------------------------------------------------------------- tab 3: budget
@callback(
    Output("b-gap", "children"), Output("b-body", "children"),
    Input("state", "value"), Input("grades", "value"), Input("movable", "value"),
    Input("t-cost", "value"), Input("c-cost", "value"), Input("budget", "value"),
    Input("b-which", "value"), Input("b-moves", "checked"), Input("b-rooms", "checked"),
)
def budget_view(state, grades, movable, t_cost, c_cost, budget, which, use_moves, with_rooms):
    view, top = scope_view(state, grades)
    share = (movable or 0) / 100
    pool = (top if which == "top" else view).join(insights.allocate_moves(LGA, share), rsuffix="_m")
    pool = pool.sort_values("need_score", ascending=False)
    pool["teachers_to_fund"] = pool.to_hire if use_moves else pool.teachers_needed
    if not with_rooms:
        pool = pool.assign(classrooms_needed=0)
    if pool.empty:
        return f"No ranked LGAs in {scope_name(state)} for the selected grades.", None
    gap = (f"**The gap before costs:** {fmt_int(pool.teachers_to_fund.sum())} teachers to hire"
           + (f" (after {fmt_int(pool.moved_in.sum())} moved in at {share:.0%})" if use_moves else "")
           + (f" and {fmt_int(pool.classrooms_needed.sum())} classrooms" if with_rooms else "") + f" across {len(pool)} LGAs.")
    if t_cost in (None, "") or (with_rooms and c_cost in (None, "")):
        return gap, dmc.Alert("Enter the unit costs above to see what the gap costs. Add a budget to see how far it goes.",
                              color="blue", variant="light")
    t_cost, c_cost = float(t_cost), float(c_cost or 0)
    full = pool.teachers_to_fund.sum() * t_cost + pool.classrooms_needed.sum() * c_cost
    has_budget = budget not in (None, "")
    plan = insights.budget_plan(pool, t_cost, c_cost, float(budget) if has_budget else full, teachers_col="teachers_to_fund")
    kpis = [kpi("Cost to close the whole gap", "b-k1")]
    kpis[0].children[1].children = naira(full)
    if has_budget:
        k2, k3 = kpi("LGAs fully funded", "b-k2"), kpi("Budget covers", "b-k3")
        k2.children[1].children = f"{int((plan.status == 'Fully funded').sum())} of {len(pool)}"
        k3.children[1].children = f"{min(float(budget) / full, 1):.0%}" if full else "100%"
        kpis += [k2, k3]
    out = pool.join(plan)
    t = pd.DataFrame({
        "Priority": range(1, len(out) + 1), "LGA": out.adm2_name, "State": out.adm1_name,
        "Teachers to hire": out.teachers_to_fund, "Teachers funded": out.teachers_funded,
        "Classrooms needed": out.classrooms_needed, "Classrooms funded": out.classrooms_funded,
        "Cost of full gap": out.cost_full_gap.round(0), "Funded": out.cost_funded.round(0), "Status": out.status})
    rows, defs = grid_data(t, {"Cost of full gap": "naira", "Funded": "naira"})
    g = grid("budget-grid", 460)
    g.rowData, g.columnDefs, g.csvExportParams = rows, defs, {"fileName": f"budget_{slug(scope_name(state))}.csv"}
    return gap, [dmc.SimpleGrid(kpis, cols={"base": 1, "sm": 3}), html.Div(g, style={"marginTop": 12}), export_button("budget-export"),
                 dmc.Text("Costs are your inputs, not data. " + VINTAGE + " Each LGA's full gap is funded before the next; the last "
                          "LGA reached is funded in part, teachers first.", size="xs", c="dimmed")]


# ---------------------------------------------------------------- tab 4: beyond the ratio
def flagged(d, cols):
    t = d.sort_values("need_score", ascending=False)
    df = pd.DataFrame({"LGA": t.adm2_name, "State": t.adm1_name, "National rank": t["rank"],
                       "Learners per teacher": t.ltr.round(0), **{k: f(t) for k, f in cols.items()}, "Confidence": t.confidence})
    return grid_data(df, {k: "dec2" for k in cols if "per primary" in k})


@callback(Output("beyond-intro", "children"), Input("state", "value"))
def beyond_intro(state):
    return (f"**What else the census says about the LGAs on the list** ({scope_name(state)}, ranked LGAs in the selected grades). "
            "Each section has its own threshold. These describe where gaps sit together; they do not explain causes.")


def scatter(d, x, y, xt, yt, theme, top, **kw):
    if d.empty:
        return empty_fig("No LGAs in scope have this measure.", theme)
    return style_fig(lga_scatter(d, x, y, xt, yt, highlight=top.adm2_pcode, theme=theme, height=420, **kw), theme)


@callback(Output("fem-text", "children"), Output("fem-fig", "figure"), Output("fem-caption", "children"),
          Output("fem-acc", "children"), Output("fem-grid", "rowData"), Output("fem-grid", "columnDefs"),
          Input("state", "value"), Input("grades", "value"), Input("fem-t", "value"), THEME_IN)
def women(state, grades, ft, theme):
    theme, ft = theme_of(theme), (ft or 20) / 100
    view, top = scope_view(state, grades)
    d = view[view.female_teacher_share.notna()]
    flag = d[d.female_teacher_share < ft]
    fm = INS["female_teachers"]
    text = (f"**{len(flag)} of {len(d)}** LGAs in scope are below {ft:.0%} ({flag.adm2_pcode.isin(top.adm2_pcode).sum()} of the "
            f"top {len(top)}). Nationally the median LGA has {fm['median_share']:.0%} women teachers, and LGAs with higher need tend "
            f"to have fewer (Spearman {fm['need_vs_female_share']['rho']:+.2f}, {fm['need_vs_female_share']['n']} LGAs). Where the list "
            "sends new teachers to these LGAs, recruiting women is worth planning for.")
    rows, defs = flagged(flag, {"Women teachers (%)": lambda t: (100 * t.female_teacher_share).round(0),
                                "Girls among learners (%)": lambda t: (100 * t.girls_share).round(0)})
    return (text, scatter(d, "female_teacher_share", "need_score", "Women among public teachers", "Need score", theme, top),
            f"{words(theme)[1]} outline = the current top list. {VINTAGE}", f"{len(flag)} LGAs below {ft:.0%}", rows, defs)


@callback(Output("jss-text", "children"), Output("jss-fig", "figure"), Output("jss-acc", "children"),
          Output("jss-grid", "rowData"), Output("jss-grid", "columnDefs"),
          Input("state", "value"), Input("grades", "value"), Input("jss-t", "value"), THEME_IN)
def jss(state, grades, target, theme):
    theme, target = theme_of(theme), (target or 100) / 100
    view, top = scope_view(state, grades)
    d = view[view.jss_per_primary_cohort.notna()].copy()
    d["gap"] = insights.jss_places_gap(d, target)
    jm = INS["jss"]
    text = (f"For one primary grade of learners, the median LGA nationally has **{jm['median_jss_per_primary_cohort']:.2f}** "
            f"learners in one public JSS grade. LGAs with higher primary need also tend to have fewer JSS learners per cohort "
            f"(Spearman {jm['need_vs_jss']['rho']:+.2f}, {jm['need_vs_jss']['n']} LGAs). In scope, reaching {target:.0%} would take "
            f"about **{fmt_int(d.gap.sum())} more public JSS places** ({fmt_int(np.ceil(d.gap.sum() / 35))} classrooms at 35:1).")
    rows, defs = flagged(d[d.gap > 0], {"JSS per primary cohort": lambda t: t.jss_per_primary_cohort.round(2),
                                        "JSS places needed": lambda t: t.gap})
    return (text, scatter(d, "jss_per_primary_cohort", "need_score", "JSS learners per primary cohort", "Need score", theme, top,
                          fmt_x=".2f"), f"LGAs in scope by JSS places needed at {target:.0%}", rows, defs)


@callback(Output("prv-text", "children"), Output("prv-fig", "figure"), Output("prv-acc", "children"),
          Output("prv-grid", "rowData"), Output("prv-grid", "columnDefs"),
          Input("state", "value"), Input("grades", "value"), Input("prv-t", "value"), THEME_IN)
def private(state, grades, pt, theme):
    theme, pt = theme_of(theme), (pt or 5) / 100
    view, top = scope_view(state, grades)
    d = view[view.private_share.notna()]
    flag = d[d.private_share < pt]
    pm = INS["private"]
    text = (f"Only **{pm['national_private_return_rate']:.0%}** of expected private-school census forms were returned nationally, "
            f"so this is shown for the {len(d)} LGAs in scope where at least half came back. Of these, **{len(flag)}** have private "
            f"schools holding under {pt:.0%} of learners: public schools are effectively the only option there. LGAs with higher need "
            f"tend to have smaller private shares (Spearman {pm['need_vs_private_share']['rho']:+.2f}, {pm['need_vs_private_share']['n']} LGAs).")
    rows, defs = flagged(flag, {"Private share (%)": lambda t: (100 * t.private_share).round(1),
                                "Private returns (%)": lambda t: (100 * t.private_reporting_rate).round(0)})
    return (text, scatter(d, "private_share", "need_score", "Private schools' share of learners", "Need score", theme, top),
            f"{len(flag)} LGAs below {pt:.0%}", rows, defs)


@callback(Output("chg-text", "children"), Output("chg-fig", "figure"), Output("chg-acc", "children"),
          Output("chg-grid", "rowData"), Output("chg-grid", "columnDefs"),
          Input("state", "value"), Input("grades", "value"), Input("chg-t", "value"), THEME_IN)
def since_2014(state, grades, ct, theme):
    theme, ct = theme_of(theme), (ct or 20) / 100
    view, top = scope_view(state, grades)
    d = view[view.ltr_change_since_2014.notna()].copy()
    d["trend"] = np.select([d.ltr_change_since_2014 > ct, d.ltr_change_since_2014 < -ct], ["Worse", "Better"], "Similar")
    c = d.trend.value_counts()
    text = (f"Of {len(d)} LGAs in scope measured both times, **{c.get('Worse', 0)} have more learners per teacher than in 2014**, "
            f"{c.get('Similar', 0)} are similar and {c.get('Better', 0)} improved by more than {ct:.0%}.")
    rows, defs = flagged(d[d.trend == "Worse"], {"2014": lambda t: t.nmis_ltr.round(0),
                                                  "Change (%)": lambda t: (100 * t.ltr_change_since_2014).round(0)})
    return (text, scatter(d, "nmis_ltr", "ltr", "Learners per teacher, 2014 (NMIS)", "Learners per teacher, 2024", theme, top,
                          fmt_x=".0f", diagonal=True), f"{c.get('Worse', 0)} LGAs worse than 2014", rows, defs)


# ---------------------------------------------------------------- tab 5: state context
@callback(Output("state-fig", "figure"), Output("state-text", "children"), Output("state-grid", "rowData"),
          Output("state-grid", "columnDefs"), Input("state", "value"), THEME_IN)
def state_view(state, theme):
    theme = theme_of(theme)
    fig = style_fig(state_scatter(STATES, highlight=state, height=460, theme=theme), theme)
    text = ("- WAEC results and foundational reading rise and fall together across states.\n"
            f"- **We tested whether reported resources predict WAEC results. They do not, beyond the national average** "
            f"(out-of-sample error {LENS2['loso_rmse_model']:.1f} points vs {LENS2['loso_rmse_baseline']:.1f} for the national mean). "
            "So this tool labels no state as over- or under-performing, and it ranks LGAs on measured gaps, not predicted results.")
    t = (STATES[["adm1_name", "waec_pass_rate", "reading", "numeracy", "oos_primary", "need_score_state", "n_ranked_lgas"]]
         .rename(columns={"adm1_name": "State", "waec_pass_rate": "WAEC pass rate 2016-18 (%)", "reading": "Reading 7-14 (%)",
                          "numeracy": "Numeracy 7-14 (%)", "oos_primary": "Primary out-of-school (%)",
                          "need_score_state": "Average LGA need score", "n_ranked_lgas": "LGAs ranked"})
         .round(1).sort_values("State"))
    fmts = {c: "dec1" for c in t.columns if c not in ("State", "LGAs ranked")}
    rows, defs = grid_data(t, fmts, pinned=("State",))
    return fig, text, rows, defs


# ---------------------------------------------------------------- tab 6: method
@callback(Output("method", "children"), Input("url", "pathname"))
def method(_):
    w, ins = META["weights"], INS
    m = CHECKS["mics_2021"]
    return f"""
### How the ranking works
1. **Measure.** For every LGA, public-school learners per teacher, per usable classroom and per usable toilet, from the 2024 Annual School Census.
2. **Grade the data.** Each LGA gets a confidence grade from the share of schools that returned census forms, plus plausibility checks. LGAs under 50% returns, or with implausible counts, are **not ranked** and are listed with the reason.
3. **Score.** Among ranked LGAs, each ratio becomes a percentile (0 = best, 1 = worst). The need score is a weighted average: teachers {w['teacher']:.0%}, classrooms {w['classroom']:.0%}, toilets {w['toilet']:.0%}, scaled to 0-100.
4. **Size the gap.** Teachers and classrooms needed to reach 35:1 at current enrolment.

### Beyond the ranking (same census, not part of the score)
- **Move or hire?** Spare teachers are those above what 35:1 needs. Within each state they go to the neediest ranked LGAs first. Even with every spare teacher moving, this covers {ins['redeploy']['share_covered']:.0%} of the national shortfall.
- **Women teachers:** female public teachers / all public teachers.
- **JSS seats:** (public JSS learners / 3) / (public primary learners / 6), shown where at least 75% of JSS forms came back.
- **Private alternative:** private / (private + public) learners, shown where at least 50% of private forms came back (nationally {ins['private']['national_private_return_rate']:.0%}).
- **Since 2014:** relative change in learners per teacher, NMIS 2014 vs census 2024; labelled only beyond a threshold because the instruments differ.

### Values you set (no dataset has them)
Share of spare teachers who can move, target JSS transition, the flag thresholds, cost per teacher, cost per classroom and the budget. Defaults (except costs, which have none) are in `config/settings.yaml`.

### How we checked it
- **Weights:** across 1,000 random alternative weightings, {META['n_persistent_top20']} of the national top 20 stay in the top 20 at least 80% of the time.
- **Structure:** the score ranks LGAs almost identically to the first principal component of the three ratios (Spearman {META['pca']['spearman_index_vs_pc1']:.2f}).
- **Independent outcomes:** states with higher average need have more children out of school and fewer with basic reading and numeracy (MICS6 2021, never an input): out-of-school {m['need_score_vs_oos_primary']['rho']:+.2f}, reading {m['need_score_vs_reading']['rho']:+.2f}, numeracy {m['need_score_vs_numeracy']['rho']:+.2f} (Spearman, 35 states).
- **Older censuses agree:** 2024 vs UBEC 2018 state learner-teacher ratio {CHECKS['ubec_2018_state_ltr']['rho']:+.2f}; 2024 vs NMIS 2014 at LGA level {CHECKS['nmis_2014_lga_ltr']['rho']:+.2f}.

### Data sources
| Source | Level | Year | Use | Status |
|---|---|---|---|---|
| Federal Ministry of Education, Annual School Census (DNEMIS) | LGA | 2024 | Ranking, insights | Real, public |
| OCHA administrative boundaries (HDX) | LGA | 2019-25 | Map, name matching | Real, public, CC BY-IGO |
| UNFPA population projections (HDX) | LGA | 2020 | Plausibility checks, hidden-demand flag | Real, public, projected |
| NMIS school survey (OSSAP-MDGs, Columbia SEL) | School | 2009-14 | Long-running shortage, change since 2014 | Real, public, CC BY 4.0 |
| NBS WAEC Results Statistics | State | 2016-18 | State context | Real, public |
| UBEC Digest of Basic Education Statistics | State | 2018 | Resource test, cross-check | Real, public |
| UNICEF/NBS MICS6 Education Fact Sheets | State | 2021 | Validation only | Real, public |

No synthetic data is used anywhere.

### Limits
- Counts are as reported by schools; the confidence grade shows where reporting is thin, but it cannot catch every error.
- The ranking counts public schools only. Private returns are too thin ({ins['private']['national_private_return_rate']:.0%} nationally) to add them.
- Population figures are projections from the 2006 census, used only for checks and a flag, never for the score.
- WAEC results exist only by state; they are context, never an LGA outcome.
- This is a prioritisation aid. It shows where gaps are largest, not why.
"""


# ---------------------------------------------------------------- CSV exports
for gid in ["top", "states", "fem", "jss", "prv", "chg", "move-lga", "budget"]:
    callback(Output(f"{gid}-grid", "exportDataAsCsv"), Input(f"{gid}-export", "n_clicks"), prevent_initial_call=True)(
        lambda n: True)
