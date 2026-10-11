"""Page layout: header with filters and theme switch, then six tabs."""
import dash_ag_grid as dag
import dash_mantine_components as dmc
from dash import dcc, html

from dashapp.common import CFG, GRADE_TEXT, LGA, LGA_OPTIONS, META, RANKED, STATE_OPTIONS

GRAPH_CONFIG = {"displayModeBar": False}

# AG Grid value formatters (d3 is available inside dash-ag-grid functions).
FORMATS = {
    "int": "params.value == null ? '' : d3.format(',.0f')(params.value)",
    "pct": "params.value == null ? '' : d3.format('.0%')(params.value)",
    "pct1": "params.value == null ? '' : d3.format('.1%')(params.value)",
    "dec1": "params.value == null ? '' : d3.format(',.1f')(params.value)",
    "dec2": "params.value == null ? '' : d3.format('.2f')(params.value)",
    "naira": "params.value == null ? '' : '₦' + d3.format(',.0f')(params.value)",
}


def grid_data(df, formats=None, pinned=("#", "Priority", "LGA")):
    """DataFrame -> (rowData, columnDefs). Fields are positional ids so headers can hold any text."""
    formats = formats or {}
    defs, rows = [], df.reset_index(drop=True)
    for i, col in enumerate(df.columns):
        d = {"field": f"c{i}", "headerName": col}
        fmt = formats.get(col)
        if fmt is None and str(df[col].dtype).startswith(("int", "float", "Int", "Float")):
            fmt = "int"
        if fmt:
            d.update(valueFormatter={"function": FORMATS[fmt]}, type="rightAligned")
        if col in pinned:
            d["pinned"] = "left"
        defs.append(d)
    data = rows.rename(columns={c: f"c{i}" for i, c in enumerate(df.columns)})
    data = data.astype(object).where(data.notna(), None)
    return data.to_dict("records"), defs


def grid(id_, height=440):
    return dag.AgGrid(
        id=id_, rowData=[], columnDefs=[],
        defaultColDef={"sortable": True, "resizable": True, "minWidth": 80},
        columnSize="autoSize",
        dashGridOptions={"animateRows": False, "tooltipShowDelay": 300},
        style={"height": height, "width": "100%"},
        csvExportParams={"fileName": f"{id_}.csv"},
    )


def kpi(label, id_, hint=None):
    title = dmc.Text(label, size="sm", c="dimmed")
    if hint:
        title = dmc.Tooltip(title, label=hint, multiline=True, w=280, withArrow=True)
    return dmc.Card([title, dmc.Text(id=id_, fz=30, fw=650, lh=1.2, mt=4)], withBorder=True, radius="md", p="md")


def export_button(id_):
    return dmc.Button("Download CSV", id=id_, variant="light", size="xs", mt="xs")


def section(title, *children, mt="xl"):
    return dmc.Stack([dmc.Title(title, order=3), *children], gap="sm", mt=mt)


def caption(text, id_=None):
    kw = {"id": id_} if id_ else {}
    return dmc.Text(text, size="xs", c="dimmed", **kw)


def pct_slider(id_, label, lo, hi, value, step, hint=None):
    return dmc.Stack([
        dmc.Text(label, size="sm", fw=500),
        dmc.Slider(id=id_, min=lo, max=hi, step=step, value=value, labelAlwaysOn=True, updatemode="mouseup",
                   marks=[{"value": v, "label": f"{v}%"} for v in (lo, round((lo + hi) / 2 / step) * step, hi)],
                   mt=30, mb="lg", maw=520),
        caption(hint) if hint else None,
    ], gap=4)


# ---------------------------------------------------------------- header
header = dmc.Stack([
    dmc.Group([
        dmc.Title("Where should the next teacher go?", order=1, fz={"base": 26, "sm": 34}),
        dmc.Switch(id="theme-switch", label="Dark mode", size="md", checked=False),
    ], justify="space-between", align="center", wrap="wrap"),
    dmc.Text([
        "Nigeria's public schools, LGA by LGA, measured against the government's own ",
        html.B("Universal Basic Education standard of 35 learners per teacher and per classroom"),
        ". Each ranking comes with a ", html.B("confidence grade"), " showing how much of it rests on complete data.",
    ], c="dimmed", maw=980),
    html.Div(id="demo-banner"),
    dmc.Grid([
        dmc.GridCol(dmc.Select(id="state", label="State", data=STATE_OPTIONS, value=STATE_OPTIONS[0], searchable=True,
                               allowDeselect=False), span={"base": 12, "sm": 5}),
        dmc.GridCol(dmc.MultiSelect(id="grades", label="Confidence grades to include", data=["A", "B", "C"],
                                    value=["A", "B", "C"]), span={"base": 12, "sm": 4}),
        dmc.GridCol(dmc.Stack([dmc.Text("LGAs ranked", size="sm", c="dimmed"),
                               dmc.Text(f"{len(RANKED)} of {len(LGA)}", fz=26, fw=650)], gap=0),
                    span={"base": 12, "sm": 3}),
    ], align="end"),
], gap="sm")

# ---------------------------------------------------------------- tab 1
tab_decide = dmc.Stack([
    dmc.SimpleGrid([
        kpi("Teachers needed in these LGAs", "k-teachers", "Extra public-school teachers to reach 35 learners per teacher, at 2024 enrolment."),
        kpi("Classrooms needed", "k-rooms", "Extra usable classrooms to reach 35 learners per classroom, at 2024 enrolment."),
        kpi("Learners in these LGAs", "k-learners", "Public-school learners, all levels, 2024."),
    ], cols={"base": 1, "sm": 3}),
    dmc.Title(id="top-title", order=3, mt="md"),
    grid("top-grid", 470),
    dmc.Group([export_button("top-export"), caption("Click a row to open it below. " + "Ranking compares LGAs; it does not explain causes.")]),
    dmc.Grid([
        dmc.GridCol([
            dmc.Title("Need across LGAs", order=3),
            dcc.Graph(id="map", config=GRAPH_CONFIG, style={"height": 560}),
            caption("", "map-caption"),
        ], span={"base": 12, "lg": 7}),
        dmc.GridCol([
            dmc.Title("Look at one LGA", order=3),
            dmc.Select(id="lga", data=LGA_OPTIONS, searchable=True, allowDeselect=False, mt="xs",
                       description="Pick from the list, or click the map or a table row."),
            html.Div(id="lga-detail", style={"marginTop": 12}),
        ], span={"base": 12, "lg": 5}),
    ], gutter="xl", mt="lg"),
    dmc.Accordion([
        dmc.AccordionItem([
            dmc.AccordionControl(id="nr-title"),
            dmc.AccordionPanel([grid("nr-grid", 360), caption(
                "These are listed rather than estimated. Treat missing returns as a finding: need here is unknown, not low.")]),
        ], value="nr"),
    ], variant="separated", mt="lg"),
], gap="sm")

# ---------------------------------------------------------------- tab 2
tab_move = dmc.Stack([
    dcc.Markdown("**Can short LGAs be fixed by moving teachers from LGAs that have more than the standard needs?** "
                 "Teachers are employed by the state, so moves stay inside each state. Spare teachers go to the neediest LGAs first."),
    pct_slider("movable", "Share of spare teachers who could realistically move", 0, 100,
               int(100 * CFG["redeploy"]["movable_share"]), 5,
               "Spare = teachers above what 35:1 needs at current enrolment. 100% is the theoretical upper bound: subject, "
               "level, family and security all limit who can move. No dataset records this, so you set it."),
    dmc.SimpleGrid([kpi("Teacher shortfall", "m-short", "Ranked LGAs only (grades A-C)."),
                    kpi("Could be covered by moves", "m-cov"), kpi("Still to hire", "m-hire")], cols={"base": 1, "sm": 3}),
    dcc.Markdown(id="move-text"),
    html.Div(id="move-body"),
    dmc.Accordion([dmc.AccordionItem([dmc.AccordionControl("All states"),
                                      dmc.AccordionPanel([grid("states-grid", 420), export_button("states-export")])],
                                     value="s")], variant="separated"),
    caption("A spare teacher may teach a subject or level a short LGA does not need, so the moves shown are an upper bound "
            "at your chosen share."),
], gap="md")

# ---------------------------------------------------------------- tab 3
tab_budget = dmc.Stack([
    dcc.Markdown("**Turn the list into a budget line.** No public dataset gives teacher or classroom unit costs for each "
                 "state, so enter your own. LGAs are funded in priority order until the budget runs out."),
    dmc.SimpleGrid([
        dmc.NumberInput(id="t-cost", label="Cost per new teacher", prefix="₦", thousandSeparator=",", min=0,
                        placeholder="e.g. one year's pay", description="Pay, allowances, posting and training for the period"),
        dmc.NumberInput(id="c-cost", label="Cost per classroom", prefix="₦", thousandSeparator=",", min=0,
                        placeholder="build or rehabilitate", description="From your own contract rates"),
        dmc.NumberInput(id="budget", label="Budget available", prefix="₦", thousandSeparator=",", min=0,
                        placeholder="total for this scope", description="Leave empty to see the full cost only"),
    ], cols={"base": 1, "sm": 3}),
    dmc.Group([
        dmc.SegmentedControl(id="b-which", data=[{"value": "top", "label": "Top 20 list"}, {"value": "all", "label": "All ranked LGAs in scope"}],
                             value="top"),
        dmc.Switch(id="b-moves", label="Move spare teachers first", checked=True),
        dmc.Switch(id="b-rooms", label="Include classrooms", checked=True),
    ], gap="xl"),
    dcc.Markdown(id="b-gap"),
    html.Div(id="b-body"),
], gap="md")


# ---------------------------------------------------------------- tab 4
def beyond_block(key, title, slider, chart_caption):
    return section(title, slider, dcc.Markdown(id=f"{key}-text"), dcc.Graph(id=f"{key}-fig", config=GRAPH_CONFIG),
                   caption(chart_caption, f"{key}-caption"),
                   dmc.Accordion([dmc.AccordionItem([dmc.AccordionControl(id=f"{key}-acc"),
                                                     dmc.AccordionPanel([grid(f"{key}-grid", 360), export_button(f"{key}-export")])],
                                                    value=key)], variant="separated"))


tab_beyond = dmc.Stack([
    dcc.Markdown(id="beyond-intro"),
    beyond_block("fem", "1. Where are there few women teachers?",
                 pct_slider("fem-t", "Flag LGAs where women are fewer than this share of public teachers", 5, 50,
                            int(100 * CFG["female_teachers"]["share_below"]), 5), ""),
    beyond_block("jss", "2. Is there a junior secondary seat after primary?",
                 pct_slider("jss-t", "Target share of a primary cohort with a public JSS seat", 50, 100,
                            int(100 * CFG["jss"]["target_transition"]), 5,
                            "UBE covers nine years, so the policy target is 100%. Lower it to plan in stages."),
                 "Shown only where at least 75% of JSS census forms were returned. Public schools only: private JSS places, "
                 "over-age primary learners and children schooling in a neighbouring LGA all affect this ratio."),
    beyond_block("prv", "3. Is there a private-school alternative?",
                 pct_slider("prv-t", "Flag LGAs where private schools hold fewer than this share of learners", 1, 30,
                            int(100 * CFG["private"]["share_below"]), 1),
                 "Private share = private learners / (private + public learners), all levels."),
    beyond_block("chg", "4. Better or worse than in 2014?",
                 pct_slider("chg-t", "Label a change only if learners per teacher moved by more than", 10, 50,
                            int(100 * CFG["change_since_2014"]["threshold"]), 5,
                            "The 2014 NMIS survey and the 2024 census are different instruments, so small changes are not labelled."),
                 "Dots above the dotted line have more learners per teacher than in 2014. NMIS: OSSAP-MDGs and Columbia SEL, "
                 "public schools surveyed 2009-2014 (CC BY 4.0)."),
], gap="md")

# ---------------------------------------------------------------- tab 5
tab_state = dmc.Stack([
    dcc.Markdown("**State-level outcomes, for context only.** WAEC results are published by state, not by LGA, so they "
                 "cannot rank LGAs. We show them next to independent survey measures of learning."),
    dcc.Graph(id="state-fig", config=GRAPH_CONFIG),
    caption("Each dot is a state. WAEC: NBS WAEC Results Statistics 2016-2018, school candidates, Taraba 2016-2017 only. "
            "Reading: UNICEF/NBS MICS6 2021."),
    dcc.Markdown(id="state-text"),
    grid("state-grid", 420),
], gap="md")

# ---------------------------------------------------------------- tab 6 (static text, filled from the data in callbacks)
tab_method = dcc.Markdown(id="method", link_target="_blank")

layout = dmc.MantineProvider(
    theme={
        "primaryColor": "blue",
        "fontFamily": "Inter, Segoe UI, system-ui, sans-serif",
        "headings": {"fontFamily": "Inter, Segoe UI, system-ui, sans-serif"},
        # Dark shades match the chart palette's dark surface (#1a1a19).
        "colors": {"dark": ["#d6d5cf", "#c3c2b7", "#898781", "#6b6a65", "#4a4a46", "#383835", "#2c2c2a",
                            "#1a1a19", "#141413", "#0d0d0d"]},
    },
    children=[
        dcc.Location(id="url"),
        dcc.Store(id="theme", storage_type="local"),
        dmc.Container([
            header,
            dmc.Tabs([
                dmc.TabsList([
                    dmc.TabsTab("Where to send teachers", value="decide"),
                    dmc.TabsTab("Move or hire?", value="move"),
                    dmc.TabsTab("Budget planner", value="budget"),
                    dmc.TabsTab("Beyond the ratio", value="beyond"),
                    dmc.TabsTab("State outcome context", value="state"),
                    dmc.TabsTab("Method, data and limits", value="method"),
                ]),
                dmc.TabsPanel(tab_decide, value="decide", pt="lg"),
                dmc.TabsPanel(tab_move, value="move", pt="lg"),
                dmc.TabsPanel(tab_budget, value="budget", pt="lg"),
                dmc.TabsPanel(tab_beyond, value="beyond", pt="lg"),
                dmc.TabsPanel(tab_state, value="state", pt="lg"),
                dmc.TabsPanel(tab_method, value="method", pt="lg"),
            ], id="tabs", value="decide", mt="lg", keepMounted=True),
            dmc.Divider(my="xl"),
            caption(f"Grades: {META['grades']}. Built from public data; see the Method tab. Settings: config/settings.yaml."),
        ], size="xl", py="lg"),
    ],
)

GRADE_HELP = "; ".join(GRADE_TEXT.values())
