"""MICS6 2021 state indicators for validation only (never a model input).

Primary out-of-school rate: extracted from the UNICEF fact sheet (p31). Only
the first number after each state name is read (the Total column), because
blank cells shift the later columns in the text layer.

Foundational reading and numeracy (ages 7-14): the fact sheet table (p23) has
no text layer, so we take these from the community Kaggle workbook, but only
after its out-of-school column agrees with our own extraction for every state,
and after a visual spot check against the rendered page (logged in BUILD_LOG).
"""
import re

import pandas as pd
import pdfplumber

from pipeline.crosswalk import load_admin, state_pcode
from pipeline.paths import CONFIG, INTERIM, RAW, REPORTS

FACT_SHEET = RAW / "mics" / "unicef_nigeria_education_fact_sheets_2023.pdf"
VISUAL_CHECK = CONFIG / "mics_p23_visual_check.csv"
WORKBOOK = RAW / "kaggle" / "nigeria-education-access-and-outcomes-by-state-2021" / "Education System Project -  Updated.xlsx"


def out_of_school_from_pdf():
    adm1, _ = load_admin()
    rows = []
    with pdfplumber.open(FACT_SHEET) as pdf:
        for line in (pdf.pages[30].extract_text() or "").splitlines():
            m = re.match(r"^([A-Z][a-z]+(?: [A-Z][a-z]+)?) (\d+)\b", line.strip())
            if m and m.group(1) not in ("STATE", "Topic", "Note"):
                rows.append({"adm1_pcode": state_pcode(m.group(1), adm1), "state_src": m.group(1), "oos_primary": float(m.group(2))})
    return pd.DataFrame(rows)


def workbook_tables():
    """Each sheet spells states differently, so resolve P-codes per sheet before joining."""
    adm1, _ = load_admin()

    def sheet(name, value_col, rename, level=None):
        d = pd.read_excel(WORKBOOK, sheet_name=name)
        if level:
            d = d[d.Level.str.lower() == level]
        d = d.assign(adm1_pcode=d.State.map(lambda s: state_pcode(str(s).strip(), adm1)))
        return d[["adm1_pcode", value_col]].rename(columns={value_col: rename})

    oos = sheet("Out of School rate (Tidy)", "Total", "oos_primary_wb", level="primary")
    read = sheet("Foundational Reading Skills", "Total", "reading")
    num = sheet("Foundational Numeracy Skills ", "Total", "numeracy")
    return oos.merge(read, on="adm1_pcode", how="outer").merge(num, on="adm1_pcode", how="outer")


def build():
    pdf = out_of_school_from_pdf()
    wb = workbook_tables()
    issues = []
    if len(pdf) != 37 or pdf.adm1_pcode.isna().any():
        issues.append({"check": "pdf_unit_count", "detail": f"{len(pdf)} rows, {pdf.adm1_pcode.isna().sum()} unresolved"})
    if wb.adm1_pcode.isna().any() or len(wb) != 37:
        issues.append({"check": "workbook_unit_count", "detail": f"{len(wb)} rows, {wb.adm1_pcode.isna().sum()} unresolved"})
    m = pdf.merge(wb, on="adm1_pcode", how="outer")
    diff = m[m.oos_primary != m.oos_primary_wb]
    for r in diff.itertuples():
        issues.append({"check": "oos_pdf_vs_workbook", "detail": f"{r.adm1_pcode}: fact sheet {r.oos_primary} vs workbook {r.oos_primary_wb}"})
    # The workbook's skills figures must match our by-eye transcription of p23.
    adm1, _ = load_admin()
    vis = pd.read_csv(VISUAL_CHECK, comment="#")
    vis["adm1_pcode"] = vis.state.map(lambda s: state_pcode(s, adm1))
    chk = m.merge(vis, on="adm1_pcode", how="outer", suffixes=("", "_visual"))
    for col in ("reading", "numeracy"):
        for r in chk[chk[col] != chk[f"{col}_visual"]].itertuples():
            issues.append({"check": f"{col}_workbook_vs_page", "detail": f"{r.adm1_pcode}: workbook {getattr(r, col)} vs page {getattr(r, col + '_visual')}"})
    out = m[["adm1_pcode", "oos_primary", "reading", "numeracy"]]
    out.to_parquet(INTERIM / "mics_state_2021.parquet", index=False)
    pd.DataFrame(issues, columns=["check", "detail"]).to_csv(REPORTS / "mics_reconciliation.csv", index=False)
    print(f"states: {len(out)}, issues: {len(issues)}")
    return out, issues


if __name__ == "__main__":
    build()
