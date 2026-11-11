"""The static site's JavaScript planner (web/logic.js) must match pipeline/insights.py.

Runs the JS under Node on the exported web/data/lgas.json and compares with the
Python functions on data/processed/lga_index.parquet. Skipped if Node is missing.
"""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pipeline import insights

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None or not (ROOT / "web/data/lgas.json").exists(),
                                reason="needs Node and web/data (scripts/build_web.py)")

JS = r"""
const WT = require(process.argv[1] + "/web/logic.js");
const lgas = require(process.argv[1] + "/web/data/lgas.json");
const out = {};
for (const s of [1.0, 0.5, 0.0]) out["state_" + s] = WT.redeploymentByState(lgas, s);
const moves = WT.allocateMoves(lgas, 1.0);
const top = lgas.filter(WT.isRanked).sort((a, b) => b.need_score - a.need_score).slice(0, 20)
  .map((r) => Object.assign({}, r, { teachers_to_fund: moves.get(r.adm2_pcode).to_hire }));
out.budget = WT.budgetPlan(top, 1500000, 8000000, 20000000000, "teachers_to_fund");
out.jss = Object.fromEntries(lgas.map((r) => [r.adm2_pcode, WT.jssPlacesGap(r, 0.8)]));
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def js():
    res = subprocess.run([NODE, "-e", JS, str(ROOT)], capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


@pytest.fixture(scope="module")
def lga():
    return pd.read_parquet(ROOT / "data/processed/lga_index.parquet")


@pytest.mark.parametrize("share", [1.0, 0.5, 0.0])
def test_redeployment_matches(js, lga, share):
    py = insights.redeployment_by_state(lga, share).set_index("adm1_name")
    got = pd.DataFrame(js[f"state_{share:g}"]).set_index("adm1_name")
    assert set(got.index) == set(py.index)
    for col in ["lgas_ranked", "shortfall", "spare", "covered_by_moves", "to_hire"]:
        np.testing.assert_allclose(got.loc[py.index, col].astype(float), py[col].astype(float), atol=1e-6, err_msg=col)


def test_budget_matches(js, lga):
    moves = insights.allocate_moves(lga, 1.0)
    pool = lga[lga.confidence.isin(["A", "B", "C"])].join(moves).sort_values("need_score", ascending=False).head(20)
    pool = pool.assign(teachers_to_fund=pool.to_hire)
    py = insights.budget_plan(pool, 1_500_000, 8_000_000, 20_000_000_000, teachers_col="teachers_to_fund")
    got = pd.DataFrame(js["budget"])
    assert got.status.tolist() == py.status.tolist()
    np.testing.assert_allclose(got.cost_funded, py.cost_funded)
    np.testing.assert_allclose(got.teachers_funded, py.teachers_funded)


def test_jss_gap_matches(js, lga):
    py = insights.jss_places_gap(lga, 0.8)
    got = pd.Series(js["jss"]).reindex(lga.adm2_pcode).astype(float).to_numpy()
    np.testing.assert_allclose(got, py.astype(float).to_numpy(), equal_nan=True)
