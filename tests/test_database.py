"""The SQLite database (db/schema.sql, pipeline/database.py) must hold the same numbers as data/processed."""
import sqlite3

import numpy as np
import pandas as pd
import pytest

from pipeline import database, insights
from pipeline.paths import PROCESSED


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    path = database.build(tmp_path_factory.mktemp("db") / "wazobia.sqlite")
    c = sqlite3.connect(path)
    c.execute("PRAGMA foreign_keys = ON")
    yield c
    c.close()


@pytest.fixture(scope="module")
def lga():
    return pd.read_parquet(PROCESSED / "lga_index.parquet")


def q(con, sql, *args):
    return con.execute(sql, args).fetchall()


def test_integrity_and_foreign_keys(con):
    assert q(con, "PRAGMA integrity_check") == [("ok",)]
    assert q(con, "PRAGMA foreign_key_check") == []


def test_every_state_and_lga_once(con):
    assert q(con, "SELECT COUNT(*) FROM states") == [(37,)]
    assert q(con, "SELECT COUNT(*), COUNT(DISTINCT adm2_pcode) FROM lgas") == [(774, 774)]
    assert q(con, "SELECT COUNT(*) FROM lga_assessment") == [(774,)]


def test_grades_match_build(con, lga):
    got = dict(q(con, "SELECT confidence, COUNT(*) FROM lga_assessment GROUP BY confidence"))
    assert got == lga.confidence.value_counts().to_dict()


def test_top20_view_matches_parquet(con, lga):
    got = [r[0] for r in q(con, "SELECT adm2_pcode FROM v_top20_national")]
    want = lga[lga["rank"].notna()].sort_values("rank").head(20).adm2_pcode.tolist()
    assert got == want


def test_gaps_and_census_totals_match(con, lga):
    r = lga[lga.confidence != "Not ranked"]
    (t, c), = q(con, "SELECT SUM(teachers_needed), SUM(classrooms_needed) FROM lga_assessment WHERE rank IS NOT NULL")
    assert (t, c) == (r.teachers_needed.sum(), r.classrooms_needed.sum())
    (learners,), = q(con, "SELECT SUM(learners) FROM lga_census WHERE year = 2024 AND source_id = 'dnemis_asc'")
    assert learners == pytest.approx(lga.learners.sum())


def test_every_not_ranked_lga_has_a_reason_and_no_ranked_lga_does(con):
    assert q(con, "SELECT COUNT(*) FROM v_not_ranked_latest") == [(132,)]
    assert q(con, """SELECT COUNT(*) FROM lga_not_ranked_reasons n JOIN lga_assessment a USING (run_id, adm2_pcode)
                     WHERE a.confidence <> 'Not ranked'""") == [(0,)]


def test_move_scenario_matches_insights(con, lga):
    py = insights.redeployment_by_state(lga, 1.0)
    (moved, hire), = q(con, """SELECT SUM(moved_in), SUM(to_hire) FROM scenario_lga_results
                              JOIN scenarios USING (scenario_id) WHERE kind = 'move'""")
    assert moved == py.covered_by_moves.sum()
    assert hire == py.to_hire.sum()


def test_budget_scenario_matches_insights(con, lga):
    b = database.EXAMPLE_BUDGET
    moves = insights.allocate_moves(lga, 1.0)
    pool = lga[lga.confidence.isin(["A", "B", "C"])].join(moves).sort_values("need_score", ascending=False).head(b["top_n"])
    pool = pool.assign(teachers_to_fund=pool.to_hire)
    py = insights.budget_plan(pool, b["teacher_cost"], b["classroom_cost"], b["budget"], teachers_col="teachers_to_fund")
    got = pd.DataFrame(q(con, """SELECT status, cost_funded FROM scenario_lga_results JOIN scenarios USING (scenario_id)
                                 WHERE kind = 'budget' ORDER BY priority"""), columns=["status", "cost"])
    assert got.status.tolist() == py.status.tolist()
    np.testing.assert_allclose(got.cost, py.cost_funded)
    assert got.cost.sum() <= b["budget"]


def test_waec_is_state_level_only(con):
    tables = [r[0] for r in q(con, "SELECT name FROM sqlite_master WHERE type = 'table'")]
    for t in tables:
        cols = [r[1] for r in q(con, f"PRAGMA table_info({t})")]
        if "adm2_pcode" in cols:
            assert not any("waec" in c for c in cols), t
    assert q(con, "SELECT COUNT(*) FROM state_outcomes WHERE measure LIKE 'waec%' AND period = '2018' "
                  "AND adm1_pcode = (SELECT adm1_pcode FROM states WHERE adm1_name = 'Taraba')") == [(0,)]


@pytest.mark.parametrize("sql", [
    "UPDATE lga_assessment SET confidence = 'D' WHERE rowid = 1",
    "UPDATE lga_assessment SET rank = NULL WHERE rank = 1",
    "UPDATE lga_assessment SET teachers_needed = -1 WHERE rank = 1",
    "INSERT INTO scenarios (run_id, kind, name, created_at) VALUES (1, 'budget', 'no costs', 'now')",
    "INSERT INTO postings (adm2_pcode, effective_date, recorded_by, recorded_at) VALUES ('NG999999', 'x', 'x', 'x')",
])
def test_constraints_reject_bad_rows(con, sql):
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(sql)
    con.rollback()
