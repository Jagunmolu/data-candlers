"""Tests for the insight views: moves, junior secondary places, budget allocation."""
import numpy as np
import pandas as pd
import pytest

from pipeline import insights, lga_index

STD = {"learners_per_teacher": 35, "learners_per_classroom": 35, "learners_per_toilet": 30}


def toy():
    # Two states. State X: one short LGA (needs 10), one with 6 spare. State Y: 20 spare, no shortfall.
    df = pd.DataFrame({
        "adm2_pcode": ["x1", "x2", "y1"], "adm1_name": ["X", "X", "Y"], "confidence": ["A", "B", "A"],
        "learners": [3500, 350, 1400], "teachers": [90, 16, 60], "classrooms": [100, 10, 40],
        "need_score": [90.0, 10.0, 5.0],
    })
    df["teachers_needed"] = (np.ceil(df.learners / 35) - df.teachers).clip(lower=0)
    df["classrooms_needed"] = (np.ceil(df.learners / 35) - df.classrooms).clip(lower=0)
    df["teachers_spare"] = insights.spare_teachers(df, STD)
    return df


def test_spare_teachers_only_above_standard():
    df = toy()
    assert df.teachers_spare.tolist() == [0, 6, 20]
    assert df.teachers_needed.tolist() == [10, 0, 0]


def test_moves_stay_inside_the_state():
    df = toy()
    m = insights.allocate_moves(df, 1.0)
    # State Y's 20 spare teachers cannot reach state X: X gets only its own 6.
    assert m.moved_in.tolist() == [6, 0, 0]
    assert m.to_hire.iloc[0] == 4
    assert m.moved_out.sum() == pytest.approx(m.moved_in.sum())


def test_movable_share_scales_the_pool():
    m = insights.allocate_moves(toy(), 0.5)
    assert m.moved_in.iloc[0] == 3


def test_unranked_lgas_take_no_part_in_moves():
    df = toy()
    df.loc[1, "confidence"] = "Not ranked"
    m = insights.allocate_moves(df, 1.0)
    assert m.moved_in.sum() == 0


def test_budget_never_exceeds_budget_and_follows_priority():
    view = pd.DataFrame({"teachers_needed": [10, 10, 10], "classrooms_needed": [2, 2, 2]}, index=["a", "b", "c"])
    plan = insights.budget_plan(view, teacher_cost=100, classroom_cost=500, budget=2600)
    assert plan.cost_funded.sum() <= 2600
    assert plan.status.tolist() == ["Fully funded", "Partly funded", "Not reached"]
    assert plan.loc["b", "teachers_funded"] == 6  # teachers first in the partly funded LGA


def test_jss_gap_matches_formula():
    df = pd.DataFrame({"pry_learners": [600.0], "jss_learners": [150.0], "jss_per_primary_cohort": [0.5]})
    # One primary grade = 100; target 1.0 means 100 per JSS grade = 300 JSS places.
    assert insights.jss_places_gap(df, 1.0).iloc[0] == 150


@pytest.fixture(scope="module")
def built():
    df, _, _ = lga_index.build()
    cfg = lga_index.load_settings()
    return insights.add_columns(df, cfg), cfg


def test_built_shares_are_bounded(built):
    df, _ = built
    for c in ["female_teacher_share", "private_share", "girls_share", "jss_reporting_rate", "private_reporting_rate"]:
        assert df[c].dropna().between(0, 1).all(), c


def test_private_share_only_where_returns_suffice(built):
    df, cfg = built
    shown = df.private_share.notna()
    assert (df.loc[shown, "private_reporting_rate"] >= cfg["insights"]["private"]["reporting_at_least"]).all()


def test_build_summary_moves_cover_at_most_the_shortfall(built):
    df, cfg = built
    s = insights.summary(df, cfg)["redeploy"]
    assert 0 <= s["covered_by_moves"] <= s["shortfall"]
    assert s["covered_by_moves"] <= s["spare"]


def test_insights_survive_a_census_without_extra_fields(built):
    df, cfg = built
    base = df.drop(columns=["female_teachers", "pry_learners", "jss_learners", "private_learners"])
    out = insights.add_columns(base, cfg)
    assert out.female_teacher_share.isna().all()
    assert out.jss_places_gap.isna().all()
