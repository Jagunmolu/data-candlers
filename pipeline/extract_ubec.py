"""Extract state-level public basic-education tables (2018-2020) from the UBEC digest.

Source: UBEC Digest of Basic Education Statistics 2019 and 2020, Volume I
(public schools), section "Trends in public basic education data". Each
trend table is one line per state followed by numbers, split across two
pages and closed by a TOTAL row.

Checks written to reports/ubec_reconciliation.csv:
- 37 states per table;
- part + part = total within each year block (male/female, qualified/unqualified, good/bad);
- the 37 state rows sum to the published TOTAL row.
"""
import re

import pandas as pd
import pdfplumber

from pipeline.crosswalk import load_admin, state_pcode
from pipeline.paths import INTERIM, RAW, REPORTS

PDF = RAW / "ubec" / "ubec_digest_2019_2020_vol_I.pdf"
YEARS = (2018, 2019, 2020)

# name -> (first PDF page, last PDF page, part labels; None = single count per year)
TABLES = {
    "schools_primary": (141, 141, None),
    "schools_jss": (142, 143, None),
    "enrolment_primary": (146, 147, ("male", "female")),
    "enrolment_jss": (148, 149, ("male", "female")),
    "teachers_primary": (152, 153, ("male", "female")),
    "teachers_jss": (154, 155, ("male", "female")),
    "qualified_primary": (158, 159, ("qualified", "unqualified")),
    "qualified_jss": (160, 161, ("qualified", "unqualified")),
    "classrooms_primary": (164, 165, ("good", "bad")),
    "classrooms_jss": (166, 167, ("good", "bad")),
}
LINE = re.compile(r"^([A-Z][A-Z .\-]+?)\s+((?:[\d,]+\s*)+)$")


def _numbers(s):
    return [float(x.replace(",", "")) for x in s.split()]


def parse_table(pdf, first, last, parts):
    width = 3 if parts is None else 9
    rows = []
    for i in range(first, last + 1):
        for line in (pdf.pages[i - 1].extract_text() or "").splitlines():
            m = LINE.match(line.strip())
            if not m:
                continue
            nums = _numbers(m.group(2))
            if len(nums) != width or m.group(1).strip() == "STATE":
                continue
            rows.append((m.group(1).strip(), nums))
    return rows


def extract():
    adm1, _ = load_admin()
    tidy, issues = [], []
    with pdfplumber.open(PDF) as pdf:
        for table, (first, last, parts) in TABLES.items():
            rows = parse_table(pdf, first, last, parts)
            total = [n for s, n in rows if s == "TOTAL"]
            states = [(s, n) for s, n in rows if s != "TOTAL"]
            if len(states) != 37:
                issues.append({"table": table, "check": "unit_count", "detail": f"{len(states)} state rows (expected 37)"})
            for s, nums in states:
                pcode = state_pcode(s.replace("FCT-ABUJA", "FCT").replace("-", " "), adm1)
                if pcode is None:
                    issues.append({"table": table, "state": s, "check": "state_name", "detail": "unresolved"})
                for k, year in enumerate(YEARS):
                    if parts is None:
                        value = nums[k]
                    else:
                        a, b, value = nums[3 * k : 3 * k + 3]
                        if a + b != value:
                            issues.append({"table": table, "state": s, "year": year, "check": "parts_sum",
                                           "detail": f"{parts[0]} {a:,.0f} + {parts[1]} {b:,.0f} != {value:,.0f}"})
                        tidy.append({"adm1_pcode": pcode, "state_src": s, "table": table, "year": year,
                                     "measure": parts[0], "value": a})
                    tidy.append({"adm1_pcode": pcode, "state_src": s, "table": table, "year": year,
                                 "measure": "total", "value": value})
            if len(total) == 1:
                t = total[0]
                for k, year in enumerate(YEARS):
                    published = t[k] if parts is None else t[3 * k + 2]
                    summed = sum(n[k] if parts is None else n[3 * k + 2] for _, n in states)
                    if summed != published:
                        issues.append({"table": table, "year": year, "check": "state_sum_vs_total",
                                       "detail": f"states sum to {summed:,.0f}, TOTAL row says {published:,.0f} (diff {summed - published:+,.0f})"})
            else:
                issues.append({"table": table, "check": "total_row", "detail": f"{len(total)} TOTAL rows found"})
    return pd.DataFrame(tidy), pd.DataFrame(issues, columns=["table", "state", "year", "check", "detail"])


def state_resources(tidy, year=2018):
    """Wide table of public basic-education resource indicators by state for one year."""
    w = tidy[(tidy.year == year)].pivot_table(index="adm1_pcode", columns=["table", "measure"], values="value")
    out = pd.DataFrame(index=w.index)
    for lvl in ("primary", "jss"):
        enr = w[(f"enrolment_{lvl}", "total")]
        out[f"ltr_{lvl}"] = enr / w[(f"teachers_{lvl}", "total")]
        out[f"lcr_{lvl}"] = enr / w[(f"classrooms_{lvl}", "total")]
        out[f"share_qualified_{lvl}"] = w[(f"qualified_{lvl}", "qualified")] / w[(f"qualified_{lvl}", "total")]
        out[f"share_good_rooms_{lvl}"] = w[(f"classrooms_{lvl}", "good")] / w[(f"classrooms_{lvl}", "total")]
        out[f"learners_per_school_{lvl}"] = enr / w[(f"schools_{lvl}", "total")]
        out[f"share_female_{lvl}"] = w[(f"enrolment_{lvl}", "male")].rsub(enr) / enr
        out[f"enrolment_{lvl}"] = enr
    return out.reset_index()


def main():
    tidy, issues = extract()
    tidy.to_parquet(INTERIM / "ubec_state_2018_2020.parquet", index=False)
    issues.to_csv(REPORTS / "ubec_reconciliation.csv", index=False)
    print(f"tidy rows: {len(tidy)}, issues: {len(issues)}")
    if len(issues):
        print(issues.groupby(["table", "check"]).size().to_string())
    return tidy, issues


if __name__ == "__main__":
    main()
