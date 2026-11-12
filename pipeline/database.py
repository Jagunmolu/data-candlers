"""Load data/processed into the SQLite database defined in db/schema.sql.

Usage: python scripts/build_db.py  (writes data/processed/wazobia.sqlite)

The database reads only data/processed and config, so it builds without the raw
downloads. It stores the same numbers the apps show: tests/test_database.py
checks them against the parquet files and pipeline/insights.py.
"""
import datetime as dt
import json
import sqlite3
import subprocess

import numpy as np
import pandas as pd
import yaml

from pipeline import insights
from pipeline.paths import CONFIG, PROCESSED, ROOT

SCHEMA = ROOT / "db" / "schema.sql"
DEFAULT_PATH = PROCESSED / "wazobia.sqlite"
CENSUS_YEAR = 2024
RANKED = ("A", "B", "C")

SOURCES = [
    # source_id, name, publisher, unit, vintage, licence, url, role
    ("dnemis_asc", "Annual School Census (DNEMIS)", "Federal Ministry of Education", "LGA", "2024",
     "No explicit licence; public government portal", "https://emis.education.gov.ng/portal/", "Ranking input"),
    ("ocha_codab", "Subnational administrative boundaries (COD-AB)", "OCHA via HDX", "LGA", "2019-2025",
     "CC BY-IGO", "https://data.humdata.org/dataset/cod-ab-nga", "Map and P-code join key"),
    ("unfpa_codps", "Subnational population statistics (COD-PS)", "UNFPA via HDX", "LGA", "2020 projection",
     "CC BY-IGO", "https://data.humdata.org/dataset/cod-ps-nga", "Plausibility checks and hidden-demand flag only"),
    ("nmis_2014", "NMIS education facility data", "OSSAP-MDGs and Columbia SEL", "School", "2009-2014",
     "CC BY 4.0", "https://energydata.info/dataset/nigeria-nmis-education-facility-data-2014",
     "Persistent shortage, change since 2014, 2014 facility conditions"),
    ("nbs_waec", "WAEC Results Statistics 2016-2018", "NBS", "State", "2016-2018",
     "NBS public release", "https://nigerianstat.gov.ng/download/1001", "State outcome context"),
    ("ubec_digest", "Digest of Basic Education Statistics 2019 and 2020", "UBEC", "State", "2018-2020",
     "UBEC public release",
     "https://ubec.gov.ng/wp-content/uploads/2024/04/2019-AND-2020-Digest-of-Statistics-Volume-I.pdf",
     "Resource test and state cross-check"),
    ("unicef_mics6", "Education Fact Sheets (MICS6 2021)", "UNICEF / NBS", "State", "2021",
     "UNICEF publication", "https://unicef.org/nigeria/media/9211/file/Nigeria%20Education%20Fact%20Sheets.pdf",
     "Validation only"),
]

CENSUS_COLS = [
    "learners", "teachers", "classrooms", "toilets", "schools", "pp_reports_actual", "pp_reports_expected",
    "jss_reports_actual", "jss_reports_expected", "pry_learners", "jss_learners", "girls", "female_teachers",
    "special_needs_pry", "iqte_schools", "private_learners", "private_reports_actual", "private_reports_expected",
    "pry_learners_all", "pry_dropouts_all", "pry_orphans_all", "learners_all", "computers_all", "non_teaching_staff_all",
]
ASSESS_COLS = [
    "confidence", "caveat", "reporting_rate", "coverage", "ltr", "lcr", "ltor", "toilet_data_ok", "teachers_needed",
    "classrooms_needed", "need_score", "rank", "main_driver", "pct_teacher", "pct_classroom", "pct_toilet",
    "top20_share", "persistent_top20", "teachers_to_exit_top20", "persistent_shortage", "hidden_demand_flag",
]
INSIGHT_COLS = [
    "teachers_spare", "teachers_moved_in", "teachers_to_hire", "female_teacher_share", "girls_share",
    "jss_reporting_rate", "jss_per_primary_cohort", "jss_places_gap", "private_reporting_rate", "private_share",
    "ltr_change_since_2014", "trend_since_2014", "special_needs_share_pry", "dropout_rate_pry_all",
    "orphan_share_pry_all", "learners_per_computer_all", "learners_per_non_teaching_staff_all",
]
# Example scenarios: the inputs used in the live demo. Costs are illustrative
# planner inputs, not official unit costs (no public source gives them).
EXAMPLE_BUDGET = {"teacher_cost": 1_500_000, "classroom_cost": 8_000_000, "budget": 20_000_000_000, "top_n": 20}


def _py(v):
    """numpy/pandas scalar to a plain Python value SQLite accepts; NaN and empty text to NULL."""
    if v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NA:
        return None
    if isinstance(v, (np.bool_, bool)):
        return int(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return None if np.isnan(v) else float(v)
    if isinstance(v, str) and v == "":
        return None
    return v


def _insert(con, table, df):
    cols = list(df.columns)
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
    con.executemany(sql, [tuple(_py(v) for v in row) for row in df.itertuples(index=False, name=None)])


def _git_commit():
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def build(path=DEFAULT_PATH):
    """Create the database at path from data/processed. Returns the path."""
    lga = pd.read_parquet(PROCESSED / "lga_index.parquet")
    st = pd.read_parquet(PROCESSED / "state_context.parquet")
    meta = json.loads((PROCESSED / "lga_index_meta.json").read_text(encoding="utf-8"))
    validation = (PROCESSED / "validation.json").read_text(encoding="utf-8")
    settings_text = (CONFIG / "settings.yaml").read_text(encoding="utf-8")
    cfg = yaml.safe_load(settings_text)
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    try:
        con.executescript(SCHEMA.read_text(encoding="utf-8"))
        con.execute("PRAGMA foreign_keys = ON")

        # reference
        con.executemany("INSERT INTO data_sources VALUES (?, ?, ?, ?, ?, ?, ?, ?)", SOURCES)
        _insert(con, "states", st[["adm1_pcode", "adm1_name"]].sort_values("adm1_pcode"))
        _insert(con, "lgas", lga[["adm2_pcode", "adm2_name", "adm1_pcode", "area_sqkm", "center_lat", "center_lon"]])
        names = lga[["adm2_pcode", "dnemis_id", "lga_name_src", "match_method"]].rename(
            columns={"dnemis_id": "source_key", "lga_name_src": "source_name"}).assign(source_id="dnemis_asc")
        nm = lga.loc[lga.unique_lga.notna(), ["adm2_pcode", "unique_lga"]].rename(columns={"unique_lga": "source_name"})
        nm = nm.assign(source_id="nmis_2014", source_key=nm.source_name, match_method="crosswalk")
        _insert(con, "lga_source_names", pd.concat([names, nm], ignore_index=True)[
            ["adm2_pcode", "source_id", "source_key", "source_name", "match_method"]])

        # facts
        census = lga.rename(columns={"schools_public": "schools"})[["adm2_pcode", *CENSUS_COLS]]
        _insert(con, "lga_census", census.assign(year=CENSUS_YEAR, source_id="dnemis_asc"))
        nmis = lga.loc[lga.nmis_schools.notna(), ["adm2_pcode", "nmis_learners", "nmis_teachers", "nmis_schools"]]
        _insert(con, "lga_census", nmis.rename(columns={"nmis_learners": "learners", "nmis_teachers": "teachers",
                                                        "nmis_schools": "schools"}).assign(year=2014, source_id="nmis_2014"))
        pop = lga.loc[lga.pop_total.notna(), ["adm2_pcode", "pop_total", "pop_5_14"]]
        _insert(con, "lga_population", pop.assign(year=2020, source_id="unfpa_codps", is_projection=1))
        fac = lga.loc[lga.nmis_schools.notna(), ["adm2_pcode", "nmis_share_water", "nmis_share_sanitation", "nmis_share_power"]]
        _insert(con, "lga_facilities", fac.rename(columns=lambda c: c.replace("nmis_", "")).assign(year=2014, source_id="nmis_2014"))
        _insert(con, "state_outcomes", _state_outcomes(st))

        # assessment
        w, s = meta["weights"], meta["standards"]
        cur = con.execute(
            """INSERT INTO index_runs (census_year, census_source_id, vintage_label, std_learners_per_teacher,
               std_learners_per_classroom, std_learners_per_toilet, w_teacher, w_classroom, w_toilet, top_n,
               settings_yaml, meta_json, validation_json, git_commit, built_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (CENSUS_YEAR, "dnemis_asc", meta["vintage"], s["learners_per_teacher"], s["learners_per_classroom"],
             s["learners_per_toilet"], w["teacher"], w["classroom"], w["toilet"], cfg["index"]["top_n"],
             settings_text, json.dumps(meta), validation, _git_commit(), now),
        )
        run_id = cur.lastrowid
        a = lga[["adm2_pcode", *ASSESS_COLS]].copy()
        a["rank"] = a["rank"].astype("Int64")
        _insert(con, "lga_assessment", a.assign(run_id=run_id))
        reasons = [
            (run_id, r.adm2_pcode, i + 1, why.strip())
            for r in lga[lga.confidence == "Not ranked"].itertuples()
            for i, why in enumerate(str(r.not_ranked_reason).split(";"))
        ]
        con.executemany("INSERT INTO lga_not_ranked_reasons VALUES (?, ?, ?, ?)", reasons)
        _insert(con, "lga_insights", lga[["adm2_pcode", *INSIGHT_COLS]].assign(run_id=run_id))
        sa = st[["adm1_pcode", "need_score_state", "ltr_ranked_lgas", "n_ranked_lgas"]].copy()
        sa["n_ranked_lgas"] = sa.n_ranked_lgas.fillna(0).astype(int)
        _insert(con, "state_assessment", sa.assign(run_id=run_id))

        # planning: the two example scenarios used in the demo
        _example_scenarios(con, run_id, lga, cfg, now)
        con.commit()
        bad = con.execute("PRAGMA foreign_key_check").fetchall()
        if bad:
            raise ValueError(f"Foreign key violations: {bad[:5]}")
    finally:
        con.close()
    return path


def _state_outcomes(st):
    rows = []
    for r in st.itertuples():
        for year in (2016, 2017, 2018):
            v = getattr(r, f"rate_{year}")
            if pd.notna(v):
                rows.append((r.adm1_pcode, "nbs_waec", str(year), "waec_5credits_eng_maths_pct", v, "percent"))
        if pd.notna(r.waec_pass_rate):
            period = "2016-2018" if r.years == 3 else "2016-2017"
            rows.append((r.adm1_pcode, "nbs_waec", period, "waec_5credits_eng_maths_pct", r.waec_pass_rate, "percent"))
            rows.append((r.adm1_pcode, "nbs_waec", period, "waec_school_candidates", r.sat, "candidates"))
        for col, measure in (("oos_primary", "out_of_school_primary_pct"), ("reading", "foundational_reading_7_14_pct"),
                             ("numeracy", "foundational_numeracy_7_14_pct")):
            v = getattr(r, col)
            if pd.notna(v):
                rows.append((r.adm1_pcode, "unicef_mics6", "2021", measure, float(v), "percent"))
    return pd.DataFrame(rows, columns=["adm1_pcode", "source_id", "period", "measure", "value", "unit"])


def _example_scenarios(con, run_id, lga, cfg, now):
    share = cfg["insights"]["redeploy"]["movable_share"]
    cur = con.execute(
        """INSERT INTO scenarios (run_id, kind, name, movable_share, is_example, notes, created_by, created_at)
           VALUES (?, 'move', ?, ?, 1, ?, 'build', ?)""",
        (run_id, "Every spare teacher moves within the state", share,
         "Upper bound: every teacher above 35:1 moves to the neediest ranked LGAs in the same state.", now),
    )
    sid = cur.lastrowid
    moves = insights.allocate_moves(lga, share)
    m = lga[["adm2_pcode"]].join(moves)[lga.confidence.isin(RANKED)]
    m = m[(m.moved_in > 0) | (m.moved_out > 0) | (m.to_hire > 0)]
    _insert(con, "scenario_lga_results", m.assign(scenario_id=sid))

    b = EXAMPLE_BUDGET
    cur = con.execute(
        """INSERT INTO scenarios (run_id, kind, name, top_n, movable_share, fund_after_moves, teacher_cost,
           classroom_cost, budget, is_example, notes, created_by, created_at)
           VALUES (?, 'budget', ?, ?, ?, 1, ?, ?, ?, 1, ?, 'build', ?)""",
        (run_id, "Demo: national top 20, NGN 20 billion", b["top_n"], share, b["teacher_cost"], b["classroom_cost"],
         b["budget"], "Illustrative planner inputs used in the live demo; not official unit costs.", now),
    )
    sid = cur.lastrowid
    pool = lga[lga.confidence.isin(RANKED)].join(moves).sort_values("need_score", ascending=False).head(b["top_n"])
    pool = pool.assign(teachers_to_fund=pool.to_hire)
    plan = insights.budget_plan(pool, b["teacher_cost"], b["classroom_cost"], b["budget"], teachers_col="teachers_to_fund")
    res = pool[["adm2_pcode"]].join(plan).assign(priority=range(1, len(pool) + 1), scenario_id=sid)
    _insert(con, "scenario_lga_results", res)
