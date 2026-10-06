"""Chart builders shared by the app and the screenshot script."""
import plotly.graph_objects as go

# Palette (dataviz reference instance): one sequential blue ramp, neutral grey for "no data".
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SERIES_1 = "#2a78d6"
NO_DATA = "#c3c2b7"
INK = "#0b0b0b"
SURFACE = "#fcfcfb"
GRID = "#e1e0d9"


def need_map(lga, geo, in_scope_codes, top, height=520):
    """LGA choropleth: need score in blue for LGAs in scope, grey otherwise, top list outlined."""
    show = lga.assign(in_scope=lga.adm2_pcode.isin(in_scope_codes))
    shaded, grey = show[show.in_scope], show[~show.in_scope]
    fig = go.Figure()
    fig.add_trace(go.Choropleth(
        geojson=geo, featureidkey="properties.adm2_pcode", locations=grey.adm2_pcode, z=[0] * len(grey),
        colorscale=[[0, NO_DATA], [1, NO_DATA]], showscale=False, marker_line_width=0.3, marker_line_color=SURFACE,
        text=grey.adm2_name + ", " + grey.adm1_name + "<br>"
        + grey.confidence.where(grey.confidence == "Not ranked", "Outside current filter"),
        hovertemplate="%{text}<extra></extra>", name="Not ranked or filtered out",
    ))
    if not shaded.empty:
        fig.add_trace(go.Choropleth(
            geojson=geo, featureidkey="properties.adm2_pcode", locations=shaded.adm2_pcode, z=shaded.need_score,
            zmin=0, zmax=100, colorscale=[[i / (len(BLUE_RAMP) - 1), c] for i, c in enumerate(BLUE_RAMP)],
            marker_line_width=0.3, marker_line_color=SURFACE,
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
            marker_line_width=2, marker_line_color=INK, hoverinfo="skip", name="Top 20",
        ))
    fig.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)")
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)")
    return fig


def state_scatter(states, highlight=None, height=440):
    """WAEC pass rate vs MICS foundational reading, one dot per state."""
    s = states.dropna(subset=["waec_pass_rate", "reading"])
    label = s.adm1_name.where(
        s.adm1_name.eq(highlight) | s.reading.isin([s.reading.min(), s.reading.max()])
        | s.waec_pass_rate.isin([s.waec_pass_rate.min(), s.waec_pass_rate.max()]), ""
    )
    fig = go.Figure(go.Scatter(
        x=s.reading, y=s.waec_pass_rate, mode="markers+text",
        marker=dict(size=10, color=SERIES_1, line=dict(width=2, color=SURFACE)),
        text=label, textposition="top center",
        customdata=s[["adm1_name", "numeracy", "oos_primary"]],
        hovertemplate="%{customdata[0]}<br>WAEC pass rate %{y:.0f}%<br>Foundational reading %{x:.0f}%"
                      "<br>Foundational numeracy %{customdata[1]:.0f}%<br>Primary out-of-school %{customdata[2]:.0f}%<extra></extra>",
    ))
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(title="Children 7-14 with foundational reading skills (%, MICS6 2021)", gridcolor=GRID, zeroline=False),
        yaxis=dict(title="WAEC: 5 credits incl. English and Maths (%, 2016-18)", gridcolor=GRID, zeroline=False),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig
