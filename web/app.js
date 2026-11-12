/* Wazobia Teachers: static front end. Reads web/data/*.json (exported by scripts/build_web.py
 * from data/processed) and recomputes planner views with logic.js. No server, no tracking. */
(function () {
  "use strict";
  const WT = window.WT;
  const VINTAGE = "Source: Federal Ministry of Education, Annual School Census 2024 (public schools).";
  const TOP_N = 20;
  const GRADE_TEXT = {
    A: "A: at least 90% of schools reported",
    B: "B: 75-90% reported, or a data caveat",
    C: "C: 50-75% reported",
    "Not ranked": "Not ranked: too little or implausible data",
  };
  const C = {
    violet: "#5b2a91", violetSoft: "#b79ad9", ink: "#1d1530", muted: "#5d5470", grid: "#ece6f3",
    noData: "#cdc8d4", yellow: "#ffc72c", green: "#008751", white: "#ffffff",
    ramp: ["#f3edf9", "#dccbef", "#c0a2e1", "#9e74cd", "#7d4bb5", "#5e2b95", "#3d1868"],
  };
  const TITLES = {
    where: "Where to send teachers", move: "Move or hire?", budget: "Budget planner",
    beyond: "Beyond the ratio", context: "State outcome context", method: "Method, data and limits",
  };

  // ---------------------------------------------------------------- state
  const S = {
    lgas: [], states: [], geo: null, meta: null,
    state: "All of Nigeria", grades: new Set(["A", "B", "C"]), route: "where",
    movable: 1, pickLga: null,
    budget: { t: "", c: "", b: "", which: "top", useMoves: true, rooms: true },
    beyond: { ft: null, jss: null, prv: null, chg: null },
  };

  // ---------------------------------------------------------------- helpers
  const $ = (sel, el = document) => el.querySelector(sel);
  const nf0 = new Intl.NumberFormat("en-NG", { maximumFractionDigits: 0 });
  const isNum = (v) => typeof v === "number" && !Number.isNaN(v);
  const fmtInt = (v) => (isNum(v) ? nf0.format(Math.round(v)) : "n/a");
  const fmtPct = (v, d = 0) => (isNum(v) ? (100 * v).toFixed(d) + "%" : "n/a");
  const fmtSigned = (v, d = 2) => (isNum(v) ? (v >= 0 ? "+" : "") + v.toFixed(d) : "n/a");
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const sum = (arr, f) => arr.reduce((s, r) => s + (isNum(f(r)) ? f(r) : 0), 0);
  const median = (xs) => { const a = xs.filter(isNum).sort((x, y) => x - y); if (!a.length) return null; const m = a.length >> 1; return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2; };
  const scopeName = () => (S.state === "All of Nigeria" ? "Nigeria" : S.state);
  const slug = (s) => s.toLowerCase().replace(/\s+/g, "_");
  function naira(x) {
    if (!isNum(x)) return "n/a";
    for (const [div, unit] of [[1e12, " trillion"], [1e9, " billion"], [1e6, " million"]]) {
      if (Math.abs(x) >= div) return "₦" + (x / div).toLocaleString("en-NG", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + unit;
    }
    return "₦" + nf0.format(x);
  }
  const ranked = () => S.lgas.filter(WT.isRanked);
  function view() {
    let v = ranked().filter((r) => S.grades.has(r.confidence));
    if (S.state !== "All of Nigeria") v = v.filter((r) => r.adm1_name === S.state);
    return v.sort((a, b) => b.need_score - a.need_score);
  }
  const top = () => view().slice(0, TOP_N);

  function kpi(label, value, sub = "", accent = false) {
    return `<div class="kpi${accent ? " accent" : ""}"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div>${sub ? `<div class="sub">${esc(sub)}</div>` : ""}</div>`;
  }

  /** cols: [{key, label, num?, fmt?(v,row), html?(v,row)}]. Returns HTML and remembers rows for CSV.
   * csv = [filename, label?] puts a download button above the table, on the left. */
  const tables = {};
  const ARROW = (d) => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${d < 0 ? "M15.4 7.4 14 6l-6 6 6 6 1.4-1.4-4.6-4.6z" : "M8.6 16.6 10 18l6-6-6-6-1.4 1.4 4.6 4.6z"}"/></svg>`;
  const FREEZE = new Set(["pos", "pri", "adm2_name", "adm1_name"]);
  function table(id, rows, cols, maxH, csv) {
    tables[id] = { rows, cols };
    let nFreeze = 0;
    while (nFreeze < cols.length - 1 && FREEZE.has(cols[nFreeze].key)) nFreeze++;
    const fz = (i) => (i < nFreeze ? ` frozen${i === nFreeze - 1 ? " frozen-last" : ""}` : "");
    const head = cols.map((c, i) => `<th class="${c.num ? "num" : ""}${fz(i)}"${c.title ? ` title="${esc(c.title)}"` : ""}>${esc(c.label)}</th>`).join("");
    const body = rows.map((r) => "<tr>" + cols.map((c, i) => {
      const v = r[c.key];
      const content = c.html ? c.html(v, r) : esc(c.fmt ? c.fmt(v, r) : v ?? "");
      return `<td class="${c.num ? "num" : ""}${fz(i)}">${content}</td>`;
    }).join("") + "</tr>").join("");
    // csv = [filename, label?, heading?]: the button sits top right, on the heading's line if one is given.
    const tools = !csv ? "" : csv[2] ? `<div class="table-head"><h2>${csv[2]}</h2>${csvButton(id, csv[0], csv[1])}</div>`
      : `<div class="table-tools">${csvButton(id, csv[0], csv[1])}</div>`;
    return `${tools}<div class="table-box"><button type="button" class="scroll-btn left" data-dir="-1" aria-label="Scroll table left" hidden>${ARROW(-1)}</button><div class="table-wrap"${maxH ? ` style="max-height:${maxH}px"` : ""}><table id="${id}"><thead><tr>${head}</tr></thead><tbody>${body || `<tr><td colspan="${cols.length}">Nothing to show for this filter.</td></tr>`}</tbody></table></div><button type="button" class="scroll-btn right" data-dir="1" aria-label="Scroll table right" hidden>${ARROW(1)}</button></div>`;
  }

  // ---------------------------------------------------------------- table scroll arrows
  // Hovering an arrow glides the table sideways; clicking jumps one screen of columns.
  function updateScrollers(root = document) {
    root.querySelectorAll(".table-box").forEach((box) => {
      const w = box.querySelector(".table-wrap");
      const max = w.scrollWidth - w.clientWidth;
      freeze(box, w);
      box.querySelector(".scroll-btn.left").hidden = !(max > 2 && w.scrollLeft > 2);
      box.querySelector(".scroll-btn.right").hidden = !(max > 2 && w.scrollLeft < max - 2);
    });
  }
  // Sticky offsets for frozen columns, measured from the rendered widths.
  function freeze(box, w) {
    const ths = [...w.querySelectorAll("thead th.frozen")];
    let left = 0;
    ths.forEach((th, i) => {
      if (th.dataset.left !== String(left)) {
        th.dataset.left = left;
        w.querySelectorAll(`tr > :nth-child(${i + 1})`).forEach((c) => { c.style.left = left + "px"; });
      }
      left += th.offsetWidth;
    });
    w.classList.toggle("scrolled", w.scrollLeft > 2);
    box.querySelector(".scroll-btn.left").style.left = (ths.length ? left - 6 : -6) + "px";
  }
  let glide = null;
  function stopGlide() { if (glide) cancelAnimationFrame(glide.raf); glide = null; }
  function startGlide(btn) {
    stopGlide();
    const box = btn.parentElement;
    const w = box.querySelector(".table-wrap");
    const dir = Number(btn.dataset.dir);
    glide = { btn, raf: 0 };
    const step = () => {
      w.scrollLeft += dir * 9;
      updateScrollers(box.parentElement);
      if (glide) glide.raf = requestAnimationFrame(step);
    };
    glide.raf = requestAnimationFrame(step);
  }
  document.addEventListener("mouseover", (e) => {
    const b = e.target.closest(".scroll-btn");
    if (b && (!glide || glide.btn !== b)) startGlide(b);
  });
  document.addEventListener("mouseout", (e) => {
    const b = e.target.closest(".scroll-btn");
    if (b && !b.contains(e.relatedTarget)) stopGlide();
  });
  document.addEventListener("click", (e) => {
    const b = e.target.closest(".scroll-btn");
    if (!b) return;
    stopGlide();
    const w = b.parentElement.querySelector(".table-wrap");
    w.scrollBy({ left: Number(b.dataset.dir) * w.clientWidth * 0.8, behavior: "smooth" });
  });
  document.addEventListener("scroll", (e) => {
    if (e.target.classList && e.target.classList.contains("table-wrap")) updateScrollers(e.target.parentElement.parentElement);
  }, true);
  document.addEventListener("toggle", () => updateScrollers(), true);
  window.addEventListener("resize", () => updateScrollers());
  function csvButton(id, filename, label = "Download this list (CSV)") {
    return `<button class="btn" data-csv="${id}" data-file="${esc(filename)}"><svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M11 3h2v9.2l3.6-3.6 1.4 1.4-6 6-6-6 1.4-1.4 3.6 3.6V3zM4 19h16v2H4z"/></svg>${esc(label)}</button>`;
  }
  function downloadCsv(id, filename) {
    const t = tables[id];
    if (!t) return;
    const cell = (v) => { const s = v === null || v === undefined ? "" : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
    const lines = [t.cols.map((c) => cell(c.label)).join(",")];
    for (const r of t.rows) lines.push(t.cols.map((c) => cell(c.csv ? c.csv(r[c.key], r) : (c.fmt ? c.fmt(r[c.key], r) : r[c.key]))).join(","));
    const blob = new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }
  const gradeHtml = (g) => (g && g !== "Not ranked" ? `<span class="grade grade-${g}">${g}</span>` : esc(g || ""));
  const r0 = (v) => (isNum(v) ? Math.round(v) : null);

  const PLOT_CFG = { displayModeBar: false, responsive: true };
  const baseLayout = (extra = {}) => Object.assign({
    margin: { l: 10, r: 10, t: 10, b: 10 }, paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "Inter, system-ui, sans-serif", color: C.ink, size: 12 }, showlegend: false,
    hoverlabel: { bgcolor: C.white, bordercolor: C.violet, font: { color: C.ink } },
  }, extra);
  const axis = (title, extra = {}) => Object.assign({ title: { text: title, font: { size: 12, color: C.muted } }, gridcolor: C.grid, zeroline: false, automargin: true, tickfont: { color: C.muted } }, extra);

  // ---------------------------------------------------------------- charts
  function needMap(el, inScope, topRows) {
    const scopeSet = new Set(inScope.map((r) => r.adm2_pcode));
    const grey = S.lgas.filter((r) => !scopeSet.has(r.adm2_pcode));
    const shaded = S.lgas.filter((r) => scopeSet.has(r.adm2_pcode));
    const traces = [{
      type: "choropleth", geojson: S.geo, featureidkey: "properties.adm2_pcode",
      locations: grey.map((r) => r.adm2_pcode), z: grey.map(() => 0),
      colorscale: [[0, C.noData], [1, C.noData]], showscale: false, marker: { line: { width: 0.4, color: C.white } },
      text: grey.map((r) => `${r.adm2_name}, ${r.adm1_name}<br>${r.confidence === "Not ranked" ? "Not ranked: " + (r.not_ranked_reason || "") : "Outside current filter"}`),
      hovertemplate: "%{text}<extra></extra>",
    }];
    if (shaded.length) {
      traces.push({
        type: "choropleth", geojson: S.geo, featureidkey: "properties.adm2_pcode",
        locations: shaded.map((r) => r.adm2_pcode), z: shaded.map((r) => r.need_score), zmin: 0, zmax: 100,
        colorscale: C.ramp.map((c, i) => [i / (C.ramp.length - 1), c]), marker: { line: { width: 0.4, color: C.white } },
        colorbar: { title: { text: "Need score", side: "top", font: { size: 11, color: C.muted } }, thickness: 10, len: 0.55, x: 1, tickfont: { color: C.muted } },
        text: shaded.map((r) => `<b>${r.adm2_name}, ${r.adm1_name}</b><br>Need score ${Math.round(r.need_score)} · national rank ${r.rank}<br>${Math.round(r.ltr)} learners per teacher · grade ${r.confidence}`),
        hovertemplate: "%{text}<extra></extra>",
      });
    }
    if (topRows.length) {
      traces.push({
        type: "choropleth", geojson: S.geo, featureidkey: "properties.adm2_pcode",
        locations: topRows.map((r) => r.adm2_pcode), z: topRows.map(() => 1),
        colorscale: [[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], showscale: false,
        marker: { line: { width: 2.2, color: C.ink } }, hoverinfo: "skip",
      });
    }
    Plotly.react(el, traces, baseLayout({
      height: 560, geo: { fitbounds: "locations", visible: false, bgcolor: "rgba(0,0,0,0)", projection: { type: "mercator" } },
      margin: { l: 0, r: 0, t: 0, b: 0 },
    }), PLOT_CFG);
  }

  function movesBar(el, byState) {
    const s = byState.filter((r) => r.shortfall > 0).sort((a, b) => a.shortfall - b.shortfall);
    const mk = (key, name, color) => ({
      type: "bar", orientation: "h", name, y: s.map((r) => r.adm1_name), x: s.map((r) => r[key]),
      marker: { color, line: { width: 1, color: C.white } },
      customdata: s.map((r) => [r.shortfall, r.spare, r.share_covered ?? 0]),
      hovertemplate: "%{y}<br>" + name + ": %{x:,.0f}<br>Shortfall %{customdata[0]:,.0f} · spare %{customdata[1]:,.0f}<br>Moves cover %{customdata[2]:.0%}<extra></extra>",
    });
    Plotly.react(el, [mk("covered_by_moves", "Could be covered by moving spare teachers", C.green), mk("to_hire", "Still to hire", C.violetSoft)], baseLayout({
      height: Math.max(360, 22 * s.length + 90), barmode: "stack", bargap: 0.25, showlegend: true,
      legend: { orientation: "h", yanchor: "bottom", y: 1.01, x: 0, traceorder: "normal" },
      xaxis: axis("Public-school teachers short of the 35:1 standard (ranked LGAs, 2024)", { tickformat: ",d" }),
      yaxis: axis("", { gridcolor: "rgba(0,0,0,0)" }),
    }), PLOT_CFG);
  }

  function lgaScatter(el, rows, x, y, xtitle, ytitle, { fx = ".0%", fy = ".0f", diagonal = false, highlight = new Set() } = {}) {
    const d = rows.filter((r) => isNum(r[x]) && isNum(r[y]));
    const traces = [];
    if (diagonal && d.length) {
      const hi = Math.max(...d.map((r) => Math.max(r[x], r[y])));
      traces.push({ type: "scatter", mode: "lines", x: [0, hi], y: [0, hi], line: { color: C.noData, width: 1.5, dash: "dot" }, hoverinfo: "skip" });
    }
    const part = (rs, hl) => ({
      type: "scatter", mode: "markers", x: rs.map((r) => r[x]), y: rs.map((r) => r[y]),
      text: rs.map((r) => `${r.adm2_name}, ${r.adm1_name}`),
      marker: hl ? { size: 11, color: C.yellow, line: { width: 1.5, color: C.ink } } : { size: 8, color: C.violet, opacity: 0.6, line: { width: 1, color: C.white } },
      hovertemplate: "%{text}<br>" + xtitle + ": %{x:" + fx + "}<br>" + ytitle + ": %{y:" + fy + "}<extra></extra>",
    });
    traces.push(part(d.filter((r) => !highlight.has(r.adm2_pcode)), false));
    traces.push(part(d.filter((r) => highlight.has(r.adm2_pcode)), true));
    Plotly.react(el, traces, baseLayout({ height: 400, xaxis: axis(xtitle, { tickformat: fx }), yaxis: axis(ytitle, { tickformat: fy }) }), PLOT_CFG);
  }

  function stateScatter(el) {
    const s = S.states.filter((r) => isNum(r.waec_pass_rate) && isNum(r.reading));
    const ext = (k, f) => f(...s.map((r) => r[k]));
    const label = s.map((r) => (r.adm1_name === S.state || r.reading === ext("reading", Math.min) || r.reading === ext("reading", Math.max)
      || r.waec_pass_rate === ext("waec_pass_rate", Math.min) || r.waec_pass_rate === ext("waec_pass_rate", Math.max) ? r.adm1_name : ""));
    const sel = s.map((r) => r.adm1_name === S.state);
    Plotly.react(el, [{
      type: "scatter", mode: "markers+text", x: s.map((r) => r.reading), y: s.map((r) => r.waec_pass_rate), text: label,
      textposition: "top center", textfont: { color: C.ink },
      marker: { size: sel.map((v) => (v ? 15 : 11)), color: sel.map((v) => (v ? C.yellow : C.violet)), line: { width: sel.map((v) => (v ? 2 : 1.5)), color: sel.map((v) => (v ? C.ink : C.white)) } },
      customdata: s.map((r) => [r.adm1_name, r.numeracy, r.oos_primary]),
      hovertemplate: "%{customdata[0]}<br>WAEC pass rate %{y:.0f}%<br>Foundational reading %{x:.0f}%<br>Foundational numeracy %{customdata[1]:.0f}%<br>Primary out-of-school %{customdata[2]:.0f}%<extra></extra>",
    }], baseLayout({
      height: 460,
      xaxis: axis("Children 7-14 with foundational reading skills (%, MICS6 2021)"),
      yaxis: axis("WAEC: 5 credits incl. English and Maths (%, 2016-18)"),
    }), PLOT_CFG);
  }

  // ---------------------------------------------------------------- section: where
  function renderWhere(el) {
    const v = view();
    const t = top();
    const scope = scopeName();
    const topCols = [
      { key: "pos", label: "S/N", num: true },
      { key: "adm2_name", label: "LGA" },
      { key: "adm1_name", label: "State" },
      { key: "ltr", label: "Learners per teacher", num: true, fmt: (x) => fmtInt(x), csv: r0, title: "Standard is 35." },
      { key: "lcr", label: "Learners per classroom", num: true, fmt: (x) => fmtInt(x), csv: r0, title: "Standard is 35." },
      { key: "teachers_needed", label: "Teachers needed", num: true, fmt: fmtInt, csv: r0 },
      { key: "classrooms_needed", label: "Classrooms needed", num: true, fmt: fmtInt, csv: r0 },
      { key: "main_driver", label: "Main driver", title: "Whether this LGA is further behind other LGAs on teachers or on classrooms." },
      { key: "confidence", label: "Confidence", html: gradeHtml, csv: (x) => x, title: Object.values(GRADE_TEXT).join("; ") },
      { key: "top20_share", label: "Stays in national top 20", num: true, fmt: (x) => fmtPct(x), csv: (x) => (isNum(x) ? Math.round(100 * x) : ""), title: "Share of 1,000 alternative weightings in which this LGA stays in the national top 20." },
      { key: "persistent_shortage", label: "Short since 2014", fmt: (x) => (x ? "Yes" : ""), title: "Also in the worst quarter for learners per teacher in the 2014 NMIS survey." },
      { key: "teachers_to_hire", label: "Still to hire after moves", num: true, fmt: fmtInt, csv: r0 },
      { key: "female_teacher_share", label: "Women teachers", num: true, fmt: (x) => fmtPct(x), csv: (x) => (isNum(x) ? Math.round(100 * x) : "") },
      { key: "rank", label: "National rank", num: true },
      { key: "caveat", label: "Caveat" },
    ];
    const rows = t.map((r, i) => Object.assign({ pos: i + 1 }, r));

    let html = `<p class="lede">Nigeria's public schools, LGA by LGA, measured against the government's own <strong>Universal Basic Education standard of 35 learners per teacher and per classroom</strong>. Every ranking carries a <strong>confidence grade</strong> showing how much of it rests on complete data.</p>`;
    if (!t.length) {
      html += `<p class="warn">No ranked LGAs in ${esc(scope)} for the selected grades. This usually means too few schools returned census forms; see "Not ranked" below.</p>`;
    } else {
      html += `<div class="kpis">
        ${kpi(`Teachers needed in these ${t.length} LGAs`, fmtInt(sum(t, (r) => r.teachers_needed)), "to reach 35 learners per teacher", true)}
        ${kpi("Classrooms needed", fmtInt(sum(t, (r) => r.classrooms_needed)), "to reach 35 learners per classroom")}
        ${kpi("Learners in these LGAs", fmtInt(sum(t, (r) => r.learners)), "public schools, 2024")}
      </div>
      ${table("t-top", rows, topCols, null, [`priority_lgas_${slug(scope)}.csv`, undefined, `The ${t.length} LGAs most in need in ${esc(scope)}`])}
      <p class="caption">${VINTAGE} The ranking compares LGAs; it does not explain causes.</p>`;
    }
    html += `<h2>Need across LGAs</h2><div class="card map-card"><button type="button" id="map-reset" class="map-reset" title="Return the map to its original size and position"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5V2L7 6l5 4V7a6 6 0 1 1-6 6H4a8 8 0 1 0 8-8z"/></svg>Reset map</button><div id="map" class="chart" style="min-height:560px"></div></div>
      <p class="caption">Darker violet = further from the 35:1 standard relative to other LGAs. Dark outline = the list above. Grey = not ranked (too little or implausible data) or outside the filter. ${VINTAGE}</p>`;

    // LGA detail
    const all = S.lgas.slice().sort((a, b) => a.adm1_name.localeCompare(b.adm1_name) || a.adm2_name.localeCompare(b.adm2_name));
    if (!S.pickLga || (t.length && !S._pickTouched)) S.pickLga = (t[0] || all[0]).adm2_pcode;
    html += `<h2>Look at one LGA</h2><div class="lga-head"><label class="field"><span>LGA</span><select id="pick">${all.map((r) => `<option value="${r.adm2_pcode}"${r.adm2_pcode === S.pickLga ? " selected" : ""}>${esc(r.adm2_name)}, ${esc(r.adm1_name)}</option>`).join("")}</select></label></div><div id="lga-detail"></div>`;

    // Not ranked
    let nr = S.lgas.filter((r) => r.confidence === "Not ranked");
    const nrTotal = nr.length;
    if (S.state !== "All of Nigeria") nr = nr.filter((r) => r.adm1_name === S.state);
    nr.sort((a, b) => a.adm1_name.localeCompare(b.adm1_name) || a.adm2_name.localeCompare(b.adm2_name));
    html += `<details id="not-ranked"><summary>Not ranked: ${nrTotal} LGAs and why${S.state !== "All of Nigeria" ? ` (${nr.length} in ${esc(S.state)})` : ""}</summary>
      ${table("t-nr", nr, [{ key: "adm2_name", label: "LGA" }, { key: "adm1_name", label: "State" }, { key: "not_ranked_reason", label: "Reason" }], 420, [`not_ranked_${slug(scope)}.csv`, "Download (CSV)"])}
      <p class="caption">Listed rather than estimated. Treat missing returns as a finding: need here is unknown, not low.</p></details>`;

    el.innerHTML = html;
    needMap($("#map"), v, t);
    $("#map-reset").addEventListener("click", () => { Plotly.purge($("#map")); needMap($("#map"), v, t); });
    renderLgaDetail();
    $("#pick").addEventListener("change", (e) => { S.pickLga = e.target.value; S._pickTouched = true; renderLgaDetail(); });
  }

  function renderLgaDetail() {
    const r = S.lgas.find((x) => x.adm2_pcode === S.pickLga);
    if (!r) return;
    const name = `${r.adm2_name}, ${r.adm1_name}`;
    const nRanked = ranked().length;
    let html = "";
    if (r.confidence === "Not ranked") html += `<p class="warn"><strong>${esc(name)} is not ranked.</strong> Reason: ${esc(r.not_ranked_reason)}. Getting complete census returns from this LGA is the first action.</p>`;
    html += `<div class="kpis">
      ${kpi("Learners per teacher", isNum(r.ltr) ? fmtInt(r.ltr) : "n/a", "standard is 35")}
      ${kpi("Teachers needed", fmtInt(r.teachers_needed), "", true)}
      ${kpi("Learners per classroom", isNum(r.lcr) ? fmtInt(r.lcr) : "n/a", "standard is 35")}
      ${kpi("Classrooms needed", fmtInt(r.classrooms_needed))}
    </div>`;
    const notes = [`<strong>Confidence:</strong> ${esc(GRADE_TEXT[r.confidence])}.`];
    if (isNum(r.reporting_rate)) notes.push(`<strong>Census returns:</strong> ${fmtPct(r.reporting_rate)} of expected primary-level school forms were returned.`);
    if (isNum(r.rank)) notes.push(`<strong>National rank:</strong> ${r.rank} of ${nRanked}; in the national top 20 under ${fmtPct(r.top20_share)} of 1,000 alternative weightings.`);
    if (isNum(r.teachers_to_exit_top20)) notes.push(`<strong>To leave the national top 20:</strong> about ${fmtInt(r.teachers_to_exit_top20)} more teachers, other things equal.`);
    if (r.caveat) notes.push(`<strong>Caveat:</strong> ${esc(r.caveat)}.`);
    if (r.persistent_shortage) notes.push("<strong>Long-running shortage:</strong> also in the worst quarter for learners per teacher in the 2014 NMIS survey.");
    if (r.hidden_demand_flag) notes.push("<strong>Possible hidden demand:</strong> public enrolment is under 40% of the projected school-age population, so a ratio near the standard may hide children who are not in school (population is a 2006-based projection).");
    if (isNum(r.nmis_share_water)) notes.push(`<strong>2014 facility conditions (NMIS, public schools):</strong> ${fmtPct(r.nmis_share_water)} had improved water, ${fmtPct(r.nmis_share_sanitation)} improved sanitation, ${fmtPct(r.nmis_share_power)} grid power. Ten years old: context, not current status.`);
    if (isNum(r.teachers_spare) && r.teachers_needed > 0) notes.push(`<strong>Move or hire:</strong> if every spare teacher in ${esc(r.adm1_name)} moved, about ${fmtInt(r.teachers_moved_in)} could come to this LGA; about ${fmtInt(r.teachers_to_hire)} would still need to be hired.`);
    else if (isNum(r.teachers_spare) && r.teachers_spare > 0) notes.push(`<strong>Spare teachers:</strong> about ${fmtInt(r.teachers_spare)} above what 35:1 needs, so this LGA could give teachers to short LGAs in ${esc(r.adm1_name)}.`);
    if (r.trend_since_2014) notes.push(`<strong>Since 2014:</strong> learners per teacher ${fmtInt(r.nmis_ltr)} (NMIS 2014) to ${fmtInt(r.ltr)} (2024), ${fmtSigned(100 * r.ltr_change_since_2014, 0)}%: ${esc(r.trend_since_2014.toLowerCase())}.`);
    html += `<div class="facts">${notes.map((n) => `<p>${n}</p>`).join("")}</div>`;
    const ctx = [
      ["Women among public teachers", fmtPct(r.female_teacher_share)],
      ["Girls among public learners", fmtPct(r.girls_share)],
      ["JSS learners per primary cohort", isNum(r.jss_per_primary_cohort) ? r.jss_per_primary_cohort.toFixed(2) : "n/a"],
      ["Private schools' share of learners", fmtPct(r.private_share)],
      ["Primary learners with special needs (public)", fmtPct(r.special_needs_share_pry)],
      ["Integrated Qur'anic (IQS/IQTE) public schools", fmtInt(r.iqte_schools)],
      ["Primary dropout rate (all schools)", fmtPct(r.dropout_rate_pry_all, 1)],
      ["Primary learners who are orphans (all schools)", fmtPct(r.orphan_share_pry_all)],
      ["Learners per usable computer (all schools)", fmtInt(r.learners_per_computer_all)],
      ["Learners per non-teaching staff (all schools)", fmtInt(r.learners_per_non_teaching_staff_all)],
    ].map(([m, val]) => ({ m, val }));
    html += `<details><summary>More about this LGA (2024 census)</summary>${table("t-ctx", ctx, [{ key: "m", label: "Measure" }, { key: "val", label: "Value", num: true }])}
      <p class="caption">Context, not part of the score. "All schools" measures are published only for public and private schools together. JSS and private figures are shown only where enough census forms came back. ${VINTAGE}</p></details>`;
    $("#lga-detail").innerHTML = html;
    updateScrollers($("#lga-detail"));
  }

  // ---------------------------------------------------------------- section: move or hire
  function renderMove(el) {
    const scope = scopeName();
    const byState = WT.redeploymentByState(S.lgas, S.movable);
    const scoped = S.state === "All of Nigeria" ? byState : byState.filter((r) => r.adm1_name === S.state);
    const short = sum(scoped, (r) => r.shortfall), cov = sum(scoped, (r) => r.covered_by_moves);
    let html = `<p class="lede"><strong>Can short LGAs be fixed by moving teachers from LGAs that have more than the standard needs?</strong> Teachers are employed by the state, so moves stay inside each state. Spare teachers go to the neediest LGAs first.</p>
      <div class="controls"><label class="slider">Share of spare teachers who could realistically move <output id="mv-out">${Math.round(100 * S.movable)}%</output>
      <input id="mv" type="range" min="0" max="100" step="5" value="${Math.round(100 * S.movable)}" title="100% is the theoretical upper bound: subject, level, family and security limit who can move. No dataset records this, so you set it."></label></div>`;
    if (!scoped.length) {
      html += `<p class="warn">No ranked LGAs in ${esc(scope)}, so moves cannot be assessed. See "Not ranked" under Where to send teachers.</p>`;
    } else {
      html += `<div class="kpis">${kpi(`Teacher shortfall, ${scope}`, fmtInt(short), "ranked LGAs only")}${kpi("Could be covered by moves", fmtInt(cov), `with ${Math.round(100 * S.movable)}% of spare teachers moving`)}${kpi("Still to hire", fmtInt(short - cov), short ? `moves cover ${fmtPct(cov / short)}` : "", true)}</div>`;
    }
    if (S.state === "All of Nigeria") {
      const rd = S.meta.insights.redeploy;
      html += `<p class="note">Even if <strong>every</strong> teacher above the standard moved, moves would cover <strong>${fmtPct(rd.share_covered)}</strong> of the national shortfall (${fmtInt(rd.covered_by_moves)} of ${fmtInt(rd.shortfall)}). Spare teachers sit mostly in ${rd.top_spare_states.join(", ")}, while the shortfall is elsewhere. Moves could close the gap in ${rd.states_moves_close_gap} states. The ${rd.states_moves_fall_short} states where they fall short hold ${fmtPct(rd.shortfall_share_in_those_states)} of the shortfall: there, <strong>hiring is the main route</strong>.</p>
        <div class="card" style="margin-top:16px"><div id="moves" class="chart"></div></div><p class="caption">Ranked LGAs only. Moves never cross state lines. ${VINTAGE}</p>`;
    } else if (scoped.length) {
      const moves = WT.allocateMoves(S.lgas, S.movable);
      const lg = S.lgas.filter((r) => r.adm1_name === S.state && WT.isRanked(r)).map((r) => Object.assign({}, r, moves.get(r.adm2_pcode))).sort((a, b) => b.need_score - a.need_score);
      html += `${table("t-moves", lg, [
        { key: "adm2_name", label: "LGA" }, { key: "ltr", label: "Learners per teacher", num: true, fmt: fmtInt, csv: r0 },
        { key: "teachers_needed", label: "Teachers short", num: true, fmt: fmtInt }, { key: "teachers_spare", label: "Spare teachers", num: true, fmt: fmtInt },
        { key: "moved_in", label: "Receives from moves", num: true, fmt: fmtInt }, { key: "moved_out", label: "Gives (approx.)", num: true, fmt: fmtInt, csv: r0 },
        { key: "to_hire", label: "Still to hire", num: true, fmt: fmtInt }, { key: "need_score", label: "Need score", num: true, fmt: fmtInt, csv: r0 },
      ], null, [`move_or_hire_${slug(S.state)}.csv`, "Download this plan (CSV)", `LGAs in ${esc(S.state)}: who gives, who receives`])}
        <p class="caption">Donors give in proportion to their spare teachers and keep enough for 35:1. ${VINTAGE}</p>`;
    }
    html += `<details><summary>All states</summary>${table("t-allstates", byState, [
      { key: "adm1_name", label: "State" }, { key: "lgas_ranked", label: "LGAs ranked", num: true },
      { key: "shortfall", label: "Teachers short", num: true, fmt: fmtInt }, { key: "spare", label: "Spare teachers", num: true, fmt: fmtInt },
      { key: "covered_by_moves", label: "Covered by moves", num: true, fmt: fmtInt }, { key: "to_hire", label: "Still to hire", num: true, fmt: fmtInt },
      { key: "share_covered", label: "Share covered", html: (x) => (isNum(x) ? `<span class="bar-cell"><span class="track"><span class="fill" style="width:${Math.min(100, 100 * x)}%"></span></span>${fmtPct(x)}</span>` : ""), csv: (x) => (isNum(x) ? x.toFixed(3) : "") },
    ], 480, ["move_or_hire_all_states.csv", "Download (CSV)"])}</details>
      <p class="caption">A spare teacher may teach a subject or level that a short LGA does not need, so the moves shown are an upper bound at your chosen share.</p>`;
    el.innerHTML = html;
    if ($("#moves")) movesBar($("#moves"), byState);
    const slider = $("#mv");
    slider.addEventListener("input", () => { $("#mv-out").textContent = slider.value + "%"; });
    slider.addEventListener("change", () => { S.movable = Number(slider.value) / 100; render(); });
  }

  // ---------------------------------------------------------------- section: budget
  function renderBudget(el) {
    const B = S.budget;
    const v = view(), t = top();
    const moves = WT.allocateMoves(S.lgas, S.movable);
    const scope = scopeName();
    let html = `<p class="lede"><strong>Turn the list into a budget line.</strong> No public dataset gives teacher or classroom unit costs for each state, so enter your own. The planner funds LGAs in priority order until the budget runs out.</p>
      <div class="controls">
        <label class="field"><span>Cost per new teacher (₦)</span><input id="b-t" type="number" min="0" step="100000" placeholder="e.g. one year's pay" value="${esc(B.t)}" title="Pay, allowances, posting and training over the period you are budgeting for."></label>
        <label class="field"><span>Cost per classroom (₦)</span><input id="b-c" type="number" min="0" step="1000000" placeholder="build or rehabilitate" value="${esc(B.c)}"></label>
        <label class="field"><span>Budget available (₦)</span><input id="b-b" type="number" min="0" step="100000000" placeholder="total for this scope" value="${esc(B.b)}"></label>
      </div>
      <div class="controls">
        <div class="choice" role="radiogroup" aria-label="LGAs to fund">
          <label><input type="radio" name="which" value="top"${B.which === "top" ? " checked" : ""}> The top ${t.length} list</label>
          <label><input type="radio" name="which" value="all"${B.which === "all" ? " checked" : ""}> All ${v.length} ranked LGAs in scope</label>
        </div>
        <div class="choice">
          <label title="Uses the share set under Move or hire? (${Math.round(100 * S.movable)}%). Moved teachers cost nothing extra here."><input id="b-moves" type="checkbox"${B.useMoves ? " checked" : ""}> Move spare teachers first (${Math.round(100 * S.movable)}%)</label>
          <label><input id="b-rooms" type="checkbox"${B.rooms ? " checked" : ""}> Include classrooms</label>
        </div>
      </div><div id="b-out"></div>`;
    el.innerHTML = html;

    const update = () => {
      const pool = (B.which === "top" ? t : v).map((r) => {
        const m = moves.get(r.adm2_pcode);
        return Object.assign({}, r, { moved_in: m.moved_in, teachers_to_fund: B.useMoves ? m.to_hire : r.teachers_needed, classrooms_needed: B.rooms ? r.classrooms_needed : 0 });
      });
      const tc = B.t === "" ? null : Number(B.t), cc = B.c === "" ? null : Number(B.c), bb = B.b === "" ? null : Number(B.b);
      let out = `<p><strong>What the gap is, before costs:</strong> ${fmtInt(sum(pool, (r) => r.teachers_to_fund))} teachers to hire${B.useMoves ? ` (after ${fmtInt(sum(pool, (r) => r.moved_in))} moved in)` : ""}${B.rooms ? ` and ${fmtInt(sum(pool, (r) => r.classrooms_needed))} classrooms` : ""} across ${pool.length} LGAs.</p>`;
      if (!pool.length) out += `<p class="warn">No ranked LGAs in ${esc(scope)} for the selected grades.</p>`;
      else if (tc === null || (B.rooms && cc === null)) out += `<p class="note">Enter the unit costs above to see what the gap costs. Add a budget to see how far it goes.</p>`;
      else {
        const c2 = cc || 0;
        const full = sum(pool, (r) => r.teachers_to_fund) * tc + sum(pool, (r) => r.classrooms_needed) * c2;
        const plan = WT.budgetPlan(pool, tc, c2, bb === null ? full : bb, "teachers_to_fund");
        const nFull = plan.filter((p) => p.status === "Fully funded").length;
        out += `<div class="kpis">${kpi("Cost to close the whole gap", naira(full), "", true)}${bb !== null ? kpi("LGAs fully funded", `${nFull} of ${pool.length}`) + kpi("Budget covers", full ? fmtPct(Math.min(bb / full, 1)) : "100%", "of the full cost") : ""}</div>`;
        const rows = pool.map((r, i) => Object.assign({ pri: i + 1 }, r, plan[i]));
        const stCls = (s) => (s === "Fully funded" ? "status-full" : s === "Partly funded" ? "status-part" : "status-none");
        out += table("t-budget", rows, [
          { key: "pri", label: "Priority", num: true }, { key: "adm2_name", label: "LGA" }, { key: "adm1_name", label: "State" },
          { key: "teachers_to_fund", label: "Teachers to hire", num: true, fmt: fmtInt }, { key: "teachers_funded", label: "Teachers funded", num: true, fmt: fmtInt },
          { key: "classrooms_needed", label: "Classrooms needed", num: true, fmt: fmtInt }, { key: "classrooms_funded", label: "Classrooms funded", num: true, fmt: fmtInt },
          { key: "cost_full_gap", label: "Cost of full gap (₦)", num: true, fmt: fmtInt, csv: r0 }, { key: "cost_funded", label: "Funded (₦)", num: true, fmt: fmtInt, csv: r0 },
          { key: "status", label: "Status", html: (s) => `<span class="${stCls(s)}">${esc(s)}</span>`, csv: (s) => s },
        ], null, [`budget_${slug(scope)}.csv`, "Download this budget (CSV)"])
          + `<p class="caption">Costs are your inputs, not data. Gaps: ${VINTAGE} Each LGA's full gap is funded before the next; the last LGA reached is funded in part, teachers first.</p>`;
      }
      $("#b-out").innerHTML = out;
      updateScrollers($("#b-out"));
    };
    const bind = (id, key) => $(id).addEventListener("input", (e) => { B[key] = e.target.value; update(); });
    bind("#b-t", "t"); bind("#b-c", "c"); bind("#b-b", "b");
    el.querySelectorAll("input[name=which]").forEach((x) => x.addEventListener("change", (e) => { B.which = e.target.value; update(); }));
    $("#b-moves").addEventListener("change", (e) => { B.useMoves = e.target.checked; update(); });
    $("#b-rooms").addEventListener("change", (e) => { B.rooms = e.target.checked; update(); });
    update();
  }

  // ---------------------------------------------------------------- section: beyond the ratio
  function renderBeyond(el) {
    const cfg = S.meta.settings.insights;
    const Bz = S.beyond;
    if (Bz.ft === null) Object.assign(Bz, { ft: cfg.female_teachers.share_below, jss: cfg.jss.target_transition, prv: cfg.private.share_below, chg: cfg.change_since_2014.threshold });
    const v = view(), t = top();
    const topSet = new Set(t.map((r) => r.adm2_pcode));
    const scope = scopeName();
    const im = S.meta.insights;
    const flagged = (id, rows, extra, file) => {
      const d = rows.slice().sort((a, b) => b.need_score - a.need_score);
      return table(id, d, [{ key: "adm2_name", label: "LGA" }, { key: "adm1_name", label: "State" }, { key: "rank", label: "National rank", num: true },
        { key: "ltr", label: "Learners per teacher", num: true, fmt: fmtInt, csv: r0 }, ...extra, { key: "confidence", label: "Confidence", html: gradeHtml, csv: (x) => x }], 340,
        [`${file}_${slug(scope)}.csv`, "Download (CSV)"]);
    };
    const slider = (id, label, min, max, step, val, suffix) => `<div class="controls"><label class="slider">${label} <output id="${id}-out">${val}${suffix}</output><input id="${id}" type="range" min="${min}" max="${max}" step="${step}" value="${val}"></label></div>`;

    // 1 women teachers
    const d1 = v.filter((r) => isNum(r.female_teacher_share));
    const f1 = d1.filter((r) => r.female_teacher_share < Bz.ft);
    const fm = im.female_teachers;
    // 2 JSS
    const d2 = v.filter((r) => isNum(r.jss_per_primary_cohort)).map((r) => Object.assign({}, r, { gap: WT.jssPlacesGap(r, Bz.jss) }));
    const gap2 = sum(d2, (r) => r.gap);
    const jm = im.jss;
    // 3 private
    const d3 = v.filter((r) => isNum(r.private_share));
    const f3 = d3.filter((r) => r.private_share < Bz.prv);
    const pm = im.private;
    // 4 since 2014
    const d4 = v.filter((r) => isNum(r.ltr_change_since_2014)).map((r) => Object.assign({}, r, { trend: r.ltr_change_since_2014 > Bz.chg ? "Worse" : r.ltr_change_since_2014 < -Bz.chg ? "Better" : "Similar" }));
    const cnt = (k) => d4.filter((r) => r.trend === k).length;

    el.innerHTML = `<p class="lede"><strong>What else the census says about the LGAs on the list</strong> (${esc(scope)}, ranked LGAs in the selected grades). Each section has its own threshold, which you can change. These describe where gaps sit together; they do not explain causes.</p>
      <h2>1. Where are there few women teachers?</h2>
      ${slider("ft", "Flag LGAs where women are fewer than", 5, 50, 5, Math.round(100 * Bz.ft), "% of public teachers")}
      <p><strong>${f1.length} of ${d1.length}</strong> LGAs in scope are below ${fmtPct(Bz.ft)} (${f1.filter((r) => topSet.has(r.adm2_pcode)).length} of the top ${t.length}). Nationally the median LGA has ${fmtPct(fm.median_share)} women teachers, and LGAs with higher need tend to have fewer (Spearman ${fmtSigned(fm.need_vs_female_share.rho)}, ${fm.need_vs_female_share.n} LGAs). Where new teachers go to these LGAs, recruiting women is worth planning for.</p>
      <div class="card"><div id="c1" class="chart"></div></div><p class="caption">Yellow = the current top list. ${VINTAGE}</p>
      <details><summary>${f1.length} LGAs below ${fmtPct(Bz.ft)}</summary>${flagged("t-f1", f1, [
        { key: "female_teacher_share", label: "Women teachers", num: true, fmt: (x) => fmtPct(x) }, { key: "girls_share", label: "Girls among learners", num: true, fmt: (x) => fmtPct(x) }], "few_women_teachers")}</details>

      <h2>2. Is there a junior secondary seat after primary?</h2>
      ${slider("jss", "Target share of a primary cohort with a public JSS seat", 50, 100, 5, Math.round(100 * Bz.jss), "%")}
      <p>For one primary grade of learners, the median LGA nationally has <strong>${jm.median_jss_per_primary_cohort.toFixed(2)}</strong> learners in one public JSS grade. LGAs with higher primary need also tend to have fewer JSS learners per cohort (Spearman ${fmtSigned(jm.need_vs_jss.rho)}, ${jm.need_vs_jss.n} LGAs). In scope, reaching ${fmtPct(Bz.jss)} would take about <strong>${fmtInt(gap2)} more public JSS places</strong> (${fmtInt(Math.ceil(gap2 / 35))} classrooms at 35:1).</p>
      <div class="card"><div id="c2" class="chart"></div></div><p class="caption">Shown only where at least 75% of JSS census forms came back. Public schools only: private JSS places, over-age primary learners and children schooling in a neighbouring LGA all affect this ratio. ${VINTAGE}</p>
      <details><summary>LGAs in scope by JSS places needed at ${fmtPct(Bz.jss)}</summary>${flagged("t-f2", d2.filter((r) => r.gap > 0), [
        { key: "jss_per_primary_cohort", label: "JSS per primary cohort", num: true, fmt: (x) => x.toFixed(2) }, { key: "gap", label: "JSS places needed", num: true, fmt: fmtInt }], "jss_places")}</details>

      <h2>3. Is there a private-school alternative?</h2>
      ${slider("prv", "Flag LGAs where private schools hold fewer than", 1, 30, 1, Math.round(100 * Bz.prv), "% of learners")}
      <p>Only <strong>${fmtPct(pm.national_private_return_rate)}</strong> of expected private-school census forms were returned nationally, so this is shown for the ${d3.length} LGAs in scope where at least half came back. Of these, <strong>${f3.length}</strong> have private schools holding under ${fmtPct(Bz.prv)} of learners: public schools are effectively the only option there. LGAs with higher need tend to have smaller private shares (Spearman ${fmtSigned(pm.need_vs_private_share.rho)}, ${pm.need_vs_private_share.n} LGAs).</p>
      <div class="card"><div id="c3" class="chart"></div></div><p class="caption">Private share = private learners / (private + public learners), all levels. ${VINTAGE}</p>
      <details><summary>${f3.length} LGAs below ${fmtPct(Bz.prv)}</summary>${flagged("t-f3", f3, [
        { key: "private_share", label: "Private share", num: true, fmt: (x) => fmtPct(x, 1) }, { key: "private_reporting_rate", label: "Private returns", num: true, fmt: (x) => fmtPct(x) }], "few_private")}</details>

      <h2>4. Better or worse than in 2014?</h2>
      ${slider("chg", "Label a change only if learners per teacher moved by more than", 10, 50, 5, Math.round(100 * Bz.chg), "%")}
      <p>Of ${d4.length} LGAs in scope measured both times, <strong>${cnt("Worse")} have more learners per teacher than in 2014</strong>, ${cnt("Similar")} are similar and ${cnt("Better")} improved by more than ${fmtPct(Bz.chg)}.</p>
      <div class="card"><div id="c4" class="chart"></div></div><p class="caption">Dots above the dotted line have more learners per teacher than in 2014. NMIS: OSSAP-MDGs and Columbia SEL, public schools surveyed 2009-2014 (CC BY 4.0). ${VINTAGE}</p>
      <details><summary>${cnt("Worse")} LGAs worse than 2014</summary>${flagged("t-f4", d4.filter((r) => r.trend === "Worse"), [
        { key: "nmis_ltr", label: "2014", num: true, fmt: fmtInt, csv: r0 }, { key: "ltr_change_since_2014", label: "Change", num: true, fmt: (x) => fmtSigned(100 * x, 0) + "%", csv: (x) => Math.round(100 * x) }], "worse_since_2014")}</details>`;

    lgaScatter($("#c1"), d1, "female_teacher_share", "need_score", "Women among public teachers", "Need score", { highlight: topSet });
    lgaScatter($("#c2"), d2, "jss_per_primary_cohort", "need_score", "JSS learners per primary cohort", "Need score", { fx: ".2f", highlight: topSet });
    lgaScatter($("#c3"), d3, "private_share", "need_score", "Private schools' share of learners", "Need score", { highlight: topSet });
    lgaScatter($("#c4"), d4, "nmis_ltr", "ltr", "Learners per teacher, 2014 (NMIS)", "Learners per teacher, 2024", { fx: ".0f", diagonal: true, highlight: topSet });
    for (const [id, key] of [["ft", "ft"], ["jss", "jss"], ["prv", "prv"], ["chg", "chg"]]) {
      const s = $("#" + id);
      const suffix = $("#" + id + "-out").textContent.replace(/^\d+/, "");
      s.addEventListener("input", () => { $("#" + id + "-out").textContent = s.value + suffix; });
      s.addEventListener("change", () => { Bz[key] = Number(s.value) / 100; const y = window.scrollY; render(); window.scrollTo(0, y); });
    }
  }

  // ---------------------------------------------------------------- section: state context
  function renderContext(el) {
    const l2 = S.meta.lens2;
    const rows = S.states.slice().sort((a, b) => a.adm1_name.localeCompare(b.adm1_name));
    const f1 = (x) => (isNum(x) ? x.toFixed(1) : "");
    el.innerHTML = `<p class="lede"><strong>State-level outcomes, for context only.</strong> WAEC results are published by state, not by LGA, so they cannot rank LGAs. They are shown next to independent survey measures of learning.</p>
      <div class="card"><div id="sc" class="chart"></div></div>
      <p class="caption">Each dot is a state; the selected state is yellow. WAEC: NBS WAEC Results Statistics 2016-2018, school candidates, Taraba 2016-2017 only. Reading: UNICEF/NBS MICS6 2021.</p>
      <ul><li>WAEC results and foundational reading rise and fall together across states.</li>
      <li><strong>We tested whether reported resources predict WAEC results. They do not, beyond the national average</strong> (out-of-sample error ${l2.loso_rmse_model.toFixed(1)} points vs ${l2.loso_rmse_baseline.toFixed(1)} for the national mean). So this tool labels no state as over- or under-performing, and it ranks LGAs on measured gaps, not predicted results.</li></ul>
      ${table("t-states", rows, [
        { key: "adm1_name", label: "State" }, { key: "waec_pass_rate", label: "WAEC pass rate 2016-18 (%)", num: true, fmt: f1 },
        { key: "reading", label: "Reading 7-14 (%)", num: true, fmt: f1 }, { key: "numeracy", label: "Numeracy 7-14 (%)", num: true, fmt: f1 },
        { key: "oos_primary", label: "Primary out-of-school (%)", num: true, fmt: f1 }, { key: "need_score_state", label: "Average LGA need score", num: true, fmt: f1 },
        { key: "n_ranked_lgas", label: "LGAs ranked", num: true },
      ], 520, ["state_context.csv", "Download (CSV)"])}`;
    stateScatter($("#sc"));
  }

  // ---------------------------------------------------------------- section: method
  function renderMethod(el) {
    const m = S.meta.index, ck = S.meta.checks, im = S.meta.insights, w = m.weights;
    el.innerHTML = `<div class="method">
      <h2>Why "Wazobia Teachers"?</h2>
      <p><em>Wa</em> (Yoruba), <em>Zo</em> (Hausa) and <em>Bia</em> (Igbo) all mean <strong>come</strong>. The tool helps a state answer one call quickly and fairly: where should the next teacher come to?</p>
      <h2>How the ranking works</h2>
      <ol><li><strong>Measure.</strong> For every LGA, public-school learners per teacher, per usable classroom and per usable toilet, from the 2024 Annual School Census.</li>
      <li><strong>Grade the data.</strong> Each LGA gets a confidence grade from the share of schools that returned census forms, plus plausibility checks (for example, reported learners far above the projected school-age population). LGAs under 50% returns, or with implausible counts, are <strong>not ranked</strong> and are listed with the reason.</li>
      <li><strong>Score.</strong> Among ranked LGAs, each ratio becomes a percentile (0 = best, 1 = worst). The need score is a weighted average: teachers ${fmtPct(w.teacher)}, classrooms ${fmtPct(w.classroom)}, toilets ${fmtPct(w.toilet)}, scaled to 0-100.</li>
      <li><strong>Size the gap.</strong> Teachers and classrooms needed to reach 35:1 at current enrolment.</li></ol>
      <h2>Beyond the ranking (same census, not part of the score)</h2>
      <ul><li><strong>Move or hire?</strong> Spare teachers are those above what 35:1 needs. Within each state they go to the neediest ranked LGAs first. Even with every spare teacher moving, this covers ${fmtPct(im.redeploy.share_covered)} of the national shortfall.</li>
      <li><strong>Women teachers:</strong> female public teachers / all public teachers.</li>
      <li><strong>JSS seats:</strong> (public JSS learners / 3) / (public primary learners / 6), shown where at least 75% of JSS forms came back.</li>
      <li><strong>Private alternative:</strong> private / (private + public) learners, shown where at least 50% of private forms came back (nationally ${fmtPct(im.private.national_private_return_rate)}).</li>
      <li><strong>Since 2014:</strong> relative change in learners per teacher, NMIS 2014 vs census 2024; labelled only beyond a threshold because the instruments differ.</li></ul>
      <h2>Values you set (no dataset has them)</h2>
      <p>Share of spare teachers who can move, target JSS transition, the flag thresholds, cost per teacher, cost per classroom and the budget. Defaults (except costs, which have none) are in <code>config/settings.yaml</code>.</p>
      <h2>How we checked it</h2>
      <ul><li><strong>Weights:</strong> across 1,000 random alternative weightings, ${m.n_persistent_top20} of the national top 20 stay in the top 20 at least 80% of the time.</li>
      <li><strong>Structure:</strong> the score ranks LGAs almost identically to a purely statistical summary of the three ratios (first principal component, Spearman ${m.pca.spearman_index_vs_pc1.toFixed(2)}).</li>
      <li><strong>Independent outcomes:</strong> states with higher average need have more children out of school and fewer with basic reading and numeracy (MICS6 2021, never used as an input): out-of-school ${fmtSigned(ck.mics_2021.need_score_vs_oos_primary.rho)}, reading ${fmtSigned(ck.mics_2021.need_score_vs_reading.rho)}, numeracy ${fmtSigned(ck.mics_2021.need_score_vs_numeracy.rho)} (Spearman, 35 states).</li>
      <li><strong>Older censuses agree:</strong> 2024 vs UBEC 2018 state learner-teacher ratio ${fmtSigned(ck.ubec_2018_state_ltr.rho)}; 2024 vs NMIS 2014 at LGA level ${fmtSigned(ck.nmis_2014_lga_ltr.rho)}.</li></ul>
      <h2>Data sources</h2>
      ${table("t-src", [
        ["Federal Ministry of Education, Annual School Census (DNEMIS)", "LGA", "2024", "Ranking", "Real, public"],
        ["OCHA administrative boundaries (HDX)", "LGA", "2019-25", "Map, name matching", "Real, public, CC BY-IGO"],
        ["UNFPA population projections (HDX)", "LGA", "2020", "Plausibility checks, hidden-demand flag", "Real, public, projected"],
        ["NMIS school survey (OSSAP-MDGs, Columbia SEL)", "School", "2009-14", "Long-running shortage, 2014 facilities", "Real, public, CC BY 4.0"],
        ["NBS WAEC Results Statistics", "State", "2016-18", "State context", "Real, public"],
        ["UBEC Digest of Basic Education Statistics", "State", "2018", "Resource test, cross-check", "Real, public"],
        ["UNICEF/NBS MICS6 Education Fact Sheets", "State", "2021", "Validation only", "Real, public"],
      ].map(([s, l, y, u, st]) => ({ s, l, y, u, st })), [{ key: "s", label: "Source" }, { key: "l", label: "Level" }, { key: "y", label: "Year" }, { key: "u", label: "Use" }, { key: "st", label: "Status" }])}
      <p>No synthetic data is used anywhere.</p>
      <h2>Limits</h2>
      <ul><li>Counts are as reported by schools; the confidence grade shows where reporting is thin, but it cannot catch every error.</li>
      <li>The ranking counts public schools only. Private schools enrol many children in some LGAs, especially in cities.</li>
      <li>Population figures are projections from the 2006 census and are used only for checks and a flag, never for the score.</li>
      <li>WAEC results exist only by state; they are context, never an LGA outcome.</li>
      <li>This is a prioritisation aid. It shows where gaps are largest, not why.</li></ul>
      <p class="caption">Grades: A ${m.grades.A}, B ${m.grades.B}, C ${m.grades.C}, not ranked ${m.grades["Not ranked"]}. Code, pipeline and data audit: <a href="https://github.com/Jagunmolu/data-candlers">github.com/Jagunmolu/data-candlers</a>.</p>
    </div>`;
  }

  // ---------------------------------------------------------------- router
  const RENDER = { where: renderWhere, move: renderMove, budget: renderBudget, beyond: renderBeyond, context: renderContext, method: renderMethod };
  function render() {
    const el = $("#view");
    $("#page-title").textContent = TITLES[S.route];
    document.title = `${TITLES[S.route]} · Wazobia Teachers`;
    document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.route === S.route));
    document.querySelectorAll("#nav a").forEach((a) => (a.dataset.route === S.route ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")));
    RENDER[S.route](el);
    requestAnimationFrame(() => updateScrollers());
  }
  function routeFromHash() {
    const r = (location.hash.match(/^#\/(\w+)/) || [])[1];
    S.route = RENDER[r] ? r : "where";
  }

  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-csv]");
    if (b) downloadCsv(b.dataset.csv, b.dataset.file);
  });

  function initCollapse() {
    const shell = $(".shell"), btn = $("#collapse");
    const set = (collapsed) => {
      shell.classList.toggle("collapsed", collapsed);
      btn.setAttribute("aria-expanded", String(!collapsed));
      const label = collapsed ? "Expand menu" : "Collapse menu";
      btn.title = label;
      btn.querySelector(".sr-only").textContent = label;
    };
    let saved = false;
    try { saved = localStorage.getItem("wt-menu-collapsed") === "1"; } catch (e) { /* storage blocked */ }
    set(saved);
    btn.addEventListener("click", () => {
      const now = !shell.classList.contains("collapsed");
      set(now);
      try { localStorage.setItem("wt-menu-collapsed", now ? "1" : "0"); } catch (e) { /* storage blocked */ }
      // Charts and tables re-measure after the menu width animates.
      setTimeout(() => { document.querySelectorAll(".js-plotly-plot").forEach((el) => Plotly.Plots.resize(el)); updateScrollers(); }, 230);
    });
  }

  async function init() {
    const get = (f) => fetch("data/" + f).then((r) => { if (!r.ok) throw new Error(f + " " + r.status); return r.json(); });
    try {
      [S.lgas, S.states, S.geo, S.meta] = await Promise.all([get("lgas.json"), get("states.json"), get("lga_boundaries.geojson"), get("meta.json")]);
    } catch (err) {
      $("#view").innerHTML = `<p class="warn">Could not load the data (${esc(err.message)}). Run <code>python scripts/build_web.py</code> and serve the web/ folder.</p>`;
      return;
    }
    const states = [...new Set(S.lgas.map((r) => r.adm1_name))].sort();
    initCollapse();
    $("#state").innerHTML = ["All of Nigeria", ...states].map((s) => `<option>${esc(s)}</option>`).join("");
    $("#ranked-count").textContent = `${ranked().length} of ${S.lgas.length} LGAs ranked`;
    $("#ranked-count").title = "The rest are listed under 'Not ranked' with the reason.";
    $("#state").addEventListener("change", (e) => { S.state = e.target.value; S._pickTouched = false; render(); });
    document.querySelectorAll(".grades input").forEach((x) => x.addEventListener("change", () => {
      S.grades = new Set([...document.querySelectorAll(".grades input:checked")].map((i) => i.value));
      render();
    }));
    if (new URLSearchParams(location.search).get("demo") === "1") {
      const d = $("#demo");
      d.hidden = false;
      d.innerHTML = "<strong>Demo path</strong> (fixed data, same every time): 1. National top 20 and the totals. 2. Map: darker violet = more need, grey = not ranked. 3. Pick <strong>Kano</strong> in State. 4. Back to All of Nigeria; in 'Look at one LGA' read <strong>Olorunsogo, Oyo</strong>, then open 'Not ranked'. 5. Move or hire? 6. Budget planner. 7. Beyond the ratio. 8. State outcome context. 9. Method.";
    }
    window.addEventListener("hashchange", () => { routeFromHash(); render(); window.scrollTo(0, 0); });
    routeFromHash();
    render();
  }
  init();
})();
