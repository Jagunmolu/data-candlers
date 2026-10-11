"""Smoke tests for the Dash app: every view builds for national, state and empty scopes."""
import pytest

pytest.importorskip("dash_mantine_components")

import dash_app  # noqa: E402,F401  (registers callbacks)
from dashapp import callbacks as cb  # noqa: E402
from dashapp.common import INS  # noqa: E402


@pytest.mark.parametrize("state", ["All of Nigeria", "Kano", "Rivers"])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_views_build(state, theme):
    cb.decision_view(state, ["A", "B", "C"], theme)
    cb.move_view(state, 50, theme)
    cb.women(state, ["A"], 20, theme)
    cb.jss(state, ["A", "B", "C"], 100, theme)
    cb.private(state, ["A", "B", "C"], 5, theme)
    cb.since_2014(state, ["A", "B", "C"], 20, theme)
    cb.state_view(state, theme)


def test_move_view_matches_build_summary():
    short, covered, hire, *_ = cb.move_view("All of Nigeria", 100, "light")
    r = INS["redeploy"]
    assert short == f"{r['shortfall']:,}" and covered.startswith(f"{r['covered_by_moves']:,}")


def test_budget_shows_nothing_until_costs_are_entered():
    gap, body = cb.budget_view("Kano", ["A", "B", "C"], 100, None, None, None, "top", True, True)
    assert "Enter the unit costs" in str(body)
