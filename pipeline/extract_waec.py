"""Extract state WAEC results 2016-2018 from the NBS infographic PDF.

Each state page has a PRIVATE panel (left) and a PUBLIC panel (right). Under
each year label sit five rows (number sat; five credits incl. English; incl.
Maths; incl. English and Maths; percentage) by three columns (male, female,
total). We read word coordinates rather than the text stream, which the
layout scrambles.

In this report "public" means school candidates (the May/June sitting) and
"private" means private candidates, not school ownership.

Every check that fails is written to reports/waec_reconciliation.csv. Nothing
is silently corrected.
"""
import re

import pandas as pd
import pdfplumber

from pipeline.crosswalk import load_admin, state_pcode
from pipeline.paths import INTERIM, RAW, REPORTS

PDF = RAW / "nbs" / "waec_results_2016_2018.pdf"
ROWS = ["sat", "credit5_eng", "credit5_maths", "credit5_eng_maths", "pct_eng_maths"]
SEXES = ["male", "female", "total"]
PANELS = {"private": (100, 300), "public": (400, 600)}  # x ranges of value columns
YEAR_X = {"private": (20, 60), "public": (320, 360)}

# National figures quoted in the report's executive summary (page 3).
NATIONAL = {
    (2018, "public"): {"sat": 1_571_536, "credit5_eng_maths": 756_726, "pct": 48.15},
    (2018, "private"): {"sat": 109_798, "credit5_eng_maths": 37_184, "pct": 33.81},
}


def _num(text):
    if text in ("-", "–"):
        return 0.0  # the report prints a dash for zero
    t = text.replace(",", "").replace("%", "")
    try:
        return float(t)
    except ValueError:
        return None


def _state_name(words):
    head = " ".join(w["text"] for w in words if 40 < w["top"] < 75)
    head = re.sub(r"\s+State$", "", head.strip())
    return head


def parse_page(page):
    words = page.extract_words()
    state = _state_name(words)
    records = []
    for panel, (x0, x1) in PANELS.items():
        yx0, yx1 = YEAR_X[panel]
        years = sorted(
            (w for w in words if re.fullmatch(r"20(16|17|18)", w["text"]) and yx0 <= w["x0"] <= yx1 and w["top"] > 200),
            key=lambda w: w["top"],
        )
        for i, yw in enumerate(years):
            y_end = years[i + 1]["top"] if i + 1 < len(years) else page.height - 40
            vals = [
                w for w in words
                if x0 <= w["x0"] < x1 and yw["top"] + 20 < w["top"] < y_end and _num(w["text"]) is not None
            ]
            # Group into rows by vertical position, then sort each row left to right.
            rows = []
            for w in sorted(vals, key=lambda w: w["top"]):
                if rows and abs(w["top"] - rows[-1][0]["top"]) < 8:
                    rows[-1].append(w)
                else:
                    rows.append([w])
            ok = len(rows) == 5 and all(len(r) == 3 for r in rows)
            rec = {"state_src": state, "year": int(yw["text"]), "candidate_type": panel, "page": page.page_number, "layout_ok": ok}
            if ok:
                for name, row in zip(ROWS, rows):
                    for sex, w in zip(SEXES, sorted(row, key=lambda w: w["x0"])):
                        rec[f"{name}_{sex}"] = _num(w["text"])
            records.append(rec)
    return records


def extract():
    recs = []
    with pdfplumber.open(PDF) as pdf:
        for page in pdf.pages[3:]:
            recs.extend(parse_page(page))
    df = pd.DataFrame(recs)
    adm1, _ = load_admin()
    df["adm1_pcode"] = df.state_src.map(lambda s: state_pcode(s, adm1))
    df["unit"] = "state"
    df.loc[df.state_src == "Nigeria", "unit"] = "national"
    df.loc[df.state_src == "Offshore", "unit"] = "offshore"
    return df


def reconcile(df):
    """Return a table of every failed check (empty table = all passed)."""
    issues = []

    def log(row, check, detail):
        issues.append({"state": row.get("state_src"), "year": row.get("year"), "candidate_type": row.get("candidate_type"),
                       "page": row.get("page"), "check": check, "detail": detail})

    for _, r in df.iterrows():
        if not r.layout_ok:
            log(r, "layout", "could not read a 5 x 3 value grid")
            continue
        if r.unit == "state" and pd.isna(r.adm1_pcode):
            log(r, "state_name", f"unresolved state name '{r.state_src}'")
        for name in ROWS[:4]:
            m, f, t = r[f"{name}_male"], r[f"{name}_female"], r[f"{name}_total"]
            if m + f != t:
                log(r, "sum_male_female", f"{name}: {m:.0f} + {f:.0f} != {t:.0f}")
        for name in ROWS[1:4]:
            if r[f"{name}_total"] > r["sat_total"]:
                log(r, "passes_exceed_sat", f"{name} {r[f'{name}_total']:.0f} > sat {r['sat_total']:.0f}")
        for sex in SEXES:
            sat = r[f"sat_{sex}"]
            if sat > 0:
                calc = 100 * r[f"credit5_eng_maths_{sex}"] / sat
                pub = r[f"pct_eng_maths_{sex}"]
                if abs(calc - pub) > 0.15 and not (pub == 0 and r[f"credit5_eng_maths_{sex}"] == 0):
                    log(r, "pct_recompute", f"{sex}: published {pub}% vs recomputed {calc:.2f}%")

    states = df[df.unit == "state"]
    for (year, ctype), g in states.groupby(["year", "candidate_type"]):
        n = g.adm1_pcode.nunique()
        if n != 37 or len(g) != 37:
            issues.append({"year": year, "candidate_type": ctype, "check": "unit_count",
                           "detail": f"{len(g)} rows, {n} distinct states (expected 37)"})

        # States plus Offshore should add up to the report's own national page.
        parts = df[(df.year == year) & (df.candidate_type == ctype) & (df.unit != "national")]
        nat = df[(df.year == year) & (df.candidate_type == ctype) & (df.unit == "national")]
        if parts.layout_ok.all() and len(nat) == 1 and nat.layout_ok.iloc[0]:
            for k in ("sat", "credit5_eng_maths"):
                s, t = parts[f"{k}_total"].sum(), nat[f"{k}_total"].iloc[0]
                if s != t:
                    issues.append({"year": year, "candidate_type": ctype, "check": "national_page_total",
                                   "detail": f"{k}: states + offshore sum to {s:,.0f}, national page says {t:,.0f} (diff {s - t:+,.0f})"})
        else:
            issues.append({"year": year, "candidate_type": ctype, "check": "national_page_total",
                           "detail": "skipped: a state, offshore or national panel failed to parse"})
        quoted = NATIONAL.get((year, ctype))
        if quoted and len(nat) == 1 and nat.layout_ok.iloc[0]:
            for k in ("sat", "credit5_eng_maths"):
                if nat[f"{k}_total"].iloc[0] != quoted[k]:
                    issues.append({"year": year, "candidate_type": ctype, "check": "summary_vs_national_page",
                                   "detail": f"{k}: national page {nat[f'{k}_total'].iloc[0]:,.0f} vs executive summary {quoted[k]:,}"})

    # A state's school candidates should not swing by more than half from one year to the next.
    pub = states[(states.candidate_type == "public") & states.layout_ok].pivot_table(index="state_src", columns="year", values="sat_total")
    for st, row in pub.iterrows():
        for y0, y1 in ((2016, 2017), (2017, 2018)):
            if y0 in row and y1 in row and row[y0] > 0 and abs(row[y1] / row[y0] - 1) > 0.5:
                issues.append({"state": st, "year": y1, "candidate_type": "public", "check": "year_on_year",
                               "detail": f"candidates sat {row[y0]:,.0f} in {y0} vs {row[y1]:,.0f} in {y1}"})
    return pd.DataFrame(issues)


def main():
    df = extract()
    issues = reconcile(df)
    df.to_parquet(INTERIM / "waec_state_2016_2018.parquet", index=False)
    issues.to_csv(REPORTS / "waec_reconciliation.csv", index=False)
    print(f"rows: {len(df)}, layout ok: {df.layout_ok.sum()}, issues: {len(issues)}")
    if len(issues):
        print(issues.groupby("check").size().to_string())
    return df, issues


if __name__ == "__main__":
    main()
