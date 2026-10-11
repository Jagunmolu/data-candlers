"""Chart builders shared by the app and the screenshot script.

Every builder takes theme="light" or "dark" and draws with that mode's colours
(dataviz reference palette: the dark column is the same hues stepped for a dark surface).
"""
import plotly.graph_objects as go

# Sequential blue ramp, light to dark.
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
THEMES = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", grid="#e1e0d9", no_data="#c3c2b7",
                  series="#2a78d6", ramp=BLUE_RAMP, bar_strong=BLUE_RAMP[5], bar_soft=BLUE_RAMP[1]),
    # On dark, "near zero" recedes toward the surface, so the ramp runs dark to light.
    "dark": dict(surface="#1a1a19", ink="#ffffff", ink2="#c3c2b7", grid="#2c2c2a", no_data="#383835",
                 series="#3987e5", ramp=BLUE_RAMP[::-1][1:], bar_strong=BLUE_RAMP[1], bar_soft=BLUE_RAMP[5]),
}
# Light-mode names kept for scripts that import them.
SERIES_1, NO_DATA, INK, SURFACE, GRID = (THEMES["light"][k] for k in ("series", "no_data", "ink", "surface", "grid"))


def _t(theme):
    return THEMES.get(theme or "light", THEMES["light"])


def need_map(lga, geo, in_scope_codes, top, height=520, theme="light"):
    t = _t(theme)
    """LGA choropleth: need score in blue for LGAs in scope, grey otherwise, top list outlined."""
    show = lga.assign(in_scope=lga.adm2_pcode.isin(in_scope_codes))
    shaded, grey = show[show.in_scope], show[~show.in_scope]
    fig = go.Figure()
    fig.add_trace(go.Choropleth(
        geojson=geo, featureidkey="properties.adm2_pcode", locations=grey.adm2_pcode, z=[0] * len(grey),
        colorscale=[[0, t['no_data']], [1, t['no_data']]], showscale=False, marker_line_width=0.3, marker_line_color=t['surface'],
        text=grey.adm2_name + ", " + grey.adm1_name + "<br>"
        + grey.confidence.where(grey.confidence == "Not ranked", "Outside current filter"),
        hovertemplate="%{text}<extra></extra>", name="Not ranked or filtered out",
    ))
    if not shaded.empty:
        fig.add_trace(go.Choropleth(
            geojson=geo, featureidkey="properties.adm2_pcode", locations=shaded.adm2_pcode, z=shaded.need_score,
            zmin=0, zmax=100, colorscale=[[i / (len(t['ramp']) - 1), c] for i, c in enumerate(t['ramp'])],
            marker_line_width=0.3, marker_line_color=t['surface'],
            colorbar=dict(title="Need score", thickness=10, len=0.6),
            text=shaded.adm2_name + ", " + shaded.adm1_name + "<br>Need score "
            + shaded.need_score.round(0).astype(int).astype(str)
            + "<br>National rank " + shaded["rank"].astype(int).astype(str) + " · Confidence " + shaded.confidence,
            hovertemplate="%{text}<extra></extra>", name="Need score",
        ))
    if not top.empty:
        fig.add_trace(go.Choropleth(
            geojson=geo, featureidkey="properties.adm2_pcode", locations=top.adm2_pcode, z=[1] * len(top),
            colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], showscale=False,
            marker_line_width=2, marker_line_color=t['ink'], hoverinfo="skip", name="Top 20",
        ))
    fig.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)")
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)")
    return fig


def state_scatter(states, highlight=None, height=440, theme="light"):
    t = _t(theme)
    """WAEC pass rate vs MICS foundational reading, one dot per state."""
    s = states.dropna(subset=["waec_pass_rate", "reading"])
    label = s.adm1_name.where(
        s.adm1_name.eq(highlight) | s.reading.isin([s.reading.min(), s.reading.max()])
        | s.waec_pass_rate.isin([s.waec_pass_rate.min(), s.waec_pass_rate.max()]), ""
    )
    fig = go.Figure(go.Scatter(
        x=s.reading, y=s.waec_pass_rate, mode="markers+text",
        marker=dict(size=10, color=t['series'], line=dict(width=2, color=t['surface'])),
        text=label, textposition="top center",
        customdata=s[["adm1_name", "numeracy", "oos_primary"]],
        hovertemplate="%{customdata[0]}<br>WAEC pass rate %{y:.0f}%<br>Foundational reading %{x:.0f}%"
                      "<br>Foundational numeracy %{customdata[1]:.0f}%<br>Primary out-of-school %{customdata[2]:.0f}%<extra></extra>",
    ))
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(title="Children 7-14 with foundational reading skills (%, MICS6 2021)", gridcolor=t['grid'], zeroline=False),
        yaxis=dict(title="WAEC: 5 credits incl. English and Maths (%, 2016-18)", gridcolor=t['grid'], zeroline=False),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _layout(fig, height, xtitle, ytitle, theme="light", **kw):
    t = _t(theme)
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(title=xtitle, gridcolor=t['grid'], zeroline=False, **kw.get("xaxis", {})),
        yaxis=dict(title=ytitle, gridcolor=t['grid'], zeroline=False, **kw.get("yaxis", {})),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=kw.get("showlegend", False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    return fig


def moves_bar(states, height=520, theme="light"):
    t = _t(theme)
    """Per state: teacher shortfall split into what within-state moves could cover and what is left to hire."""
    s = states[states.shortfall > 0].sort_values("shortfall")
    fig = go.Figure()
    for col, name, color in [("covered_by_moves", "Could be covered by moving spare teachers", t["bar_strong"]),
                             ("to_hire", "Still to hire", t["bar_soft"])]:
        fig.add_trace(go.Bar(
            y=s.adm1_name, x=s[col], orientation="h", name=name, marker=dict(color=color, line=dict(width=1, color=t['surface'])),
            customdata=s[["shortfall", "spare", "share_covered"]].fillna(0),
            hovertemplate="%{y}<br>" + name + ": %{x:,.0f}<br>Shortfall %{customdata[0]:,.0f} · spare %{customdata[1]:,.0f}"
                          "<br>Moves cover %{customdata[2]:.0%}<extra></extra>",
        ))
    fig.update_layout(barmode="stack", bargap=0.25, legend_traceorder="normal")
    return _layout(fig, height, "Public-school teachers short of the 35:1 standard (ranked LGAs, 2024)", None, theme=theme, showlegend=True)


def lga_scatter(df, x, y, xtitle, ytitle, fmt_x=".0%", fmt_y=".0f", height=400, diagonal=False, highlight=None, theme="light"):
    t = _t(theme)
    """One dot per LGA. Optional y = x reference line and outlined highlight set."""
    d = df.dropna(subset=[x, y])
    fig = go.Figure()
    if diagonal and not d.empty:
        hi = float(max(d[x].max(), d[y].max()))
        fig.add_trace(go.Scatter(x=[0, hi], y=[0, hi], mode="lines", line=dict(color=t["no_data"], width=1, dash="dot"),
                                 hoverinfo="skip", name="No change"))
    hl = d.adm2_pcode.isin(highlight) if highlight is not None else False
    fig.add_trace(go.Scatter(
        x=d[x], y=d[y], mode="markers",
        marker=dict(size=8, color=t['series'], opacity=0.75, line=dict(width=[2 if h else 1 for h in (hl if highlight is not None else [False] * len(d))],
                                                                    color=[t['ink'] if h else t['surface'] for h in (hl if highlight is not None else [False] * len(d))])),
        text=d.adm2_name + ", " + d.adm1_name,
        hovertemplate="%{text}<br>" + xtitle + ": %{x:" + fmt_x + "}<br>" + ytitle + ": %{y:" + fmt_y + "}<extra></extra>",
    ))
    return _layout(fig, height, xtitle, ytitle, theme=theme, xaxis=dict(tickformat=fmt_x), yaxis=dict(tickformat=fmt_y))
