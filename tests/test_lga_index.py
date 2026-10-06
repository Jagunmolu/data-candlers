"""Tests for the crosswalk and the Lens 1 index logic."""
import numpy as np
import pandas as pd
import pytest

from pipeline import lga_index
from pipeline.crosswalk import norm, state_pcode, load_admin


@pytest.fixture(scope="module")
def built():
    return lga_index.build()


def test_norm_strips_punctuation_and_case():
    assert norm("Ile-Oluji/Okeigbo") == "ileolujiokeigbo"
    assert norm("Mai'Adua") == "maiadua"


@pytest.mark.parametrize(
    "raw,expected",
    [("ko Kogi State", "NG023"), ("an Anambra state", "NG004"), ("akwa", "NG003"), ("fct", "NG015"), ("go Gombe", "NG016")],
)
def test_state_names_from_every_source_resolve(raw, expected):
    adm1, _ = load_admin()
    assert state_pcode(raw, adm1) == expected


def test_every_lga_present_exactly_once(built):
    df, _, _ = built
    assert len(df) == 774
    assert df.adm2_pcode.is_unique


def test_all_census_lgas_matched(built):
    _, unmatched, _ = built
    assert (unmatched.source != "dnemis").all(), "every DNEMIS LGA must map to a P-code"


def test_ranks_are_contiguous_and_only_for_ranked(built):
    df, _, _ = built
    ranked = df[df.confidence != "Not ranked"]
    assert sorted(ranked["rank"].astype(int)) == list(range(1, len(ranked) + 1))
    assert df.loc[df.confidence == "Not ranked", "rank"].isna().all()


def test_not_ranked_rows_always_explain_why(built):
    df, _, _ = built
    nr = df[df.confidence == "Not ranked"]
    assert (nr.not_ranked_reason.str.len() > 0).all()


def test_low_reporting_is_never_ranked(built):
    df, _, _ = built
    assert not ((df.reporting_rate < 0.5) & (df.confidence != "Not ranked")).any()


def test_gaps_are_non_negative_and_match_standard(built):
    df, _, meta = built
    ok = df.dropna(subset=["learners", "teachers"])
    assert (ok.teachers_needed >= 0).all()
    row = ok[ok.teachers_needed > 0].iloc[0]
    std = meta["standards"]["learners_per_teacher"]
    assert row.teachers_needed == np.ceil(row.learners / std) - row.teachers


def test_score_is_bounded_and_monotone_in_teacher_ratio():
    pct = pd.DataFrame({"teacher": [0.1, 0.9], "classroom": [0.5, 0.5], "toilet": [0.5, 0.5]})
    s = lga_index.score(pct, {"teacher": 0.5, "classroom": 0.35, "toilet": 0.15})
    assert s.between(0, 100).all()
    assert s.iloc[1] > s.iloc[0]


def test_weight_perturbation_is_reproducible():
    rng = np.random.default_rng(0)
    pct = pd.DataFrame(rng.random((50, 3)), columns=["teacher", "classroom", "toilet"])
    cfg = {"seed": 1, "draws": 200, "concentration": 20}
    a, _ = lga_index.stability(pct, {"teacher": 0.5, "classroom": 0.35, "toilet": 0.15}, cfg, 10)
    b, _ = lga_index.stability(pct, {"teacher": 0.5, "classroom": 0.35, "toilet": 0.15}, cfg, 10)
    assert a.equals(b)
    assert a.sum() == pytest.approx(10)  # exactly 10 LGAs in the top 10 on every draw


def test_teachers_to_exit_actually_exits(built):
    """Adding the reported number of teachers must push the LGA's score below the cutoff."""
    df, _, meta = built
    cfg = lga_index.load_settings()
    ranked = df[df.confidence != "Not ranked"].copy().reset_index(drop=True)
    pct = lga_index.percentile_scores(ranked)
    w = cfg["index"]["weights"]
    s = lga_index.score(pct, w).sort_values(ascending=False)
    cutoff = s.iloc[20]
    row = ranked[ranked["rank"] == 1].iloc[0]
    extra = row.teachers_to_exit_top20
    assert not np.isnan(extra)
    new_ltr = row.learners / (row.teachers + extra)
    rest = ranked.ltr.drop(row.name).dropna()
    p = ((rest < new_ltr).sum() + 1) / (len(rest) + 1)
    new = (w["teacher"] * p + w["classroom"] * pct.loc[row.name, "classroom"] + w["toilet"] * pct.loc[row.name, "toilet"]) / sum(w.values()) * 100
    assert new < cutoff


def test_partner_csv_adapter_uses_column_map(tmp_path, monkeypatch):
    """A partner table with its own column names flows through the config mapping."""
    csv = tmp_path / "partner.csv"
    pd.DataFrame(
        {"state_x": ["Kano", "Lagos"], "lga_x": ["Fagge", "Ikeja"], "pupils": [1000, 2000], "tchrs": [10, 100],
         "rooms": [20, 40], "wc": [5, 50], "got": [9, 10], "want": [10, 10]}
    ).to_csv(csv, index=False)
    cfg = lga_index.load_settings()
    cfg["lga_input"]["adapter"] = "csv"
    cfg["lga_input"]["csv"].update(
        path=str(csv),
        columns={"state": "state_x", "lga": "lga_x", "learners": "pupils", "teachers": "tchrs", "classrooms": "rooms",
                 "toilets": "wc", "reports_actual": "got", "reports_expected": "want"},
    )
    census, unmatched, _ = lga_index.load_census(cfg)
    assert len(census) == 2 and unmatched.empty
    assert set(census.columns) >= {"adm2_pcode", "learners", "teachers", "pp_reports_actual"}
