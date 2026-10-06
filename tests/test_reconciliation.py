"""Reconciliation tests for every PDF extraction. Known, documented publication
errors are listed explicitly; anything new makes these tests fail."""
import pandas as pd
import pytest

from pipeline import extract_mics, extract_ubec, extract_waec, lens2


@pytest.fixture(scope="module")
def waec():
    df = extract_waec.extract()
    return df, extract_waec.reconcile(df)


def test_waec_school_candidates_parse_for_every_state_year(waec):
    df, _ = waec
    pub = df[(df.unit == "state") & (df.candidate_type == "public")]
    assert len(pub) == 37 * 3
    assert pub.layout_ok.all()
    assert pub.adm1_pcode.nunique() == 37


def test_waec_states_sum_to_national_page_2016_2017(waec):
    _, issues = waec
    bad = issues[(issues.check == "national_page_total") & (issues.candidate_type == "public")]
    assert set(bad.year) == {2018}, "only 2018 (the Taraba misprint) may fail"


def test_waec_2018_gap_is_explained_by_taraba(waec):
    df, _ = waec
    pub18 = df[(df.year == 2018) & (df.candidate_type == "public")]
    parts = pub18[pub18.unit != "national"].sat_total.sum()
    national = pub18[pub18.unit == "national"].sat_total.iloc[0]
    taraba_2017 = df[(df.state_src == "Taraba") & (df.year == 2017) & (df.candidate_type == "public")].sat_total.iloc[0]
    implied_taraba = national - (parts - 75)
    assert 0.5 * taraba_2017 < implied_taraba < 1.5 * taraba_2017


def test_waec_percentages_recompute(waec):
    _, issues = waec
    assert not (issues.check == "pct_recompute").any()


def test_taraba_2018_excluded_from_model():
    t = lens2.waec_target()
    row = t[t.adm1_pcode == "NG035"].iloc[0]
    assert row.years == 2 and pd.isna(row.rate_2018)


def test_ubec_tables_reconcile_except_known_misprint():
    _, issues = extract_ubec.extract()
    assert len(issues) == 1
    known = issues.iloc[0]
    assert (known.table, known.state, known.year) == ("enrolment_primary", "ABIA", 2020)


def test_ubec_every_table_has_37_states():
    tidy, _ = extract_ubec.extract()
    counts = tidy[tidy.measure == "total"].groupby(["table", "year"]).adm1_pcode.nunique()
    assert (counts == 37).all()


def test_mics_sources_agree():
    out, issues = extract_mics.build()
    assert len(out) == 37 and not issues
    assert out[["oos_primary", "reading", "numeracy"]].notna().all().all()
