"""Insights beyond the need ranking, built from the same 2024 census and the 2014 NMIS survey.

Every function takes the LGA table from lga_index.build() and returns new columns
or a summary. The app calls the same functions when a planner changes an input
(share of spare teachers who can move, target transition rate, unit costs, budget),
so the numbers on screen and in data/processed always come from one place.

All measures describe where gaps are; none says why they exist.
"""
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

RANKED = ("A", "B", "C")


def _ratio(num, den):
    return num / den.where(den > 0)


def _col(df, name):
    """Column or all-NaN, so a partner CSV without the extra fields still builds."""
    return df[name] if name in df.columns else pd.Series(np.nan, index=df.index)


# ---------------------------------------------------------------- 1. move or hire
def spare_teachers(df, std):
    """Teachers above what the standard needs at current enrolment (0 where short)."""
    return (df.teachers - np.ceil(df.learners / std["learners_per_teacher"])).clip(lower=0)


def allocate_moves(df, movable_share):
    """Within each state, move spare teachers to the neediest LGAs first.

    Teachers are employed by the state (SUBEB), so moves never cross state lines.
    Only ranked LGAs take part: their counts are graded as usable. movable_share is
    the planner's assumption of how many spare teachers could realistically move
    (1.0 = every teacher above the standard, a theoretical upper bound).
    Returns per-LGA teachers received, teachers given and teachers still to hire.
    """
    out = pd.DataFrame(0.0, index=df.index, columns=["moved_in", "moved_out"])
    r = df[df.confidence.isin(RANKED)]
    for _, g in r.groupby("adm1_name"):
        pool = np.floor(g.teachers_spare.sum() * movable_share)
        if pool <= 0:
            continue
        taken = 0.0
        for idx in g.sort_values("need_score", ascending=False).index:
            take = min(g.at[idx, "teachers_needed"], pool - taken)
            if take <= 0:
                break
            out.at[idx, "moved_in"] = take
            taken += take
        # Donors give in proportion to their spare teachers.
        donors = g.teachers_spare[g.teachers_spare > 0]
        out.loc[donors.index, "moved_out"] = taken * donors / donors.sum()
    out["to_hire"] = (df.teachers_needed - out.moved_in).where(df.confidence.isin(RANKED))
    return out


def redeployment_by_state(df, movable_share):
    """Per state: teacher shortfall, spare teachers, how much moves could cover, and what is left to hire."""
    moves = allocate_moves(df, movable_share)
    r = df[df.confidence.isin(RANKED)].join(moves)
    st = r.groupby("adm1_name").agg(
        lgas_ranked=("adm2_pcode", "size"),
        shortfall=("teachers_needed", "sum"),
        spare=("teachers_spare", "sum"),
        covered_by_moves=("moved_in", "sum"),
        to_hire=("to_hire", "sum"),
    )
    st["share_covered"] = _ratio(st.covered_by_moves, st.shortfall)
    return st.reset_index().sort_values("shortfall", ascending=False)


# ---------------------------------------------------------------- 2-4. beyond the ratio
def add_columns(df, cfg):
    """Add every insight column to the LGA table."""
    ins, std = cfg["insights"], cfg["standards"]
    df = df.copy()
    ranked = df.confidence.isin(RANKED)

    # 1. Move or hire (base case: every spare teacher could move).
    df["teachers_spare"] = spare_teachers(df, std).where(ranked)
    moves = allocate_moves(df, ins["redeploy"]["movable_share"])
    df["teachers_moved_in"] = moves.moved_in.where(ranked)
    df["teachers_to_hire"] = moves.to_hire

    # 2. Female teachers in public schools.
    df["female_teacher_share"] = _ratio(_col(df, "female_teachers"), df.teachers).clip(upper=1.0)
    df["girls_share"] = _ratio(_col(df, "girls"), df.learners).clip(upper=1.0)
    df["few_female_teachers"] = df.female_teacher_share < ins["female_teachers"]["share_below"]

    # 3. Junior secondary places per primary cohort. Primary has 6 grades and JSS 3,
    # so (JSS / 3) / (primary / 6) compares one JSS grade with one primary grade.
    jss_rep = _ratio(_col(df, "jss_reports_actual"), _col(df, "jss_reports_expected")).clip(upper=1.0)
    df["jss_reporting_rate"] = jss_rep
    ok = jss_rep >= ins["jss"]["reporting_at_least"]
    pry, jss = _col(df, "pry_learners"), _col(df, "jss_learners")
    df["jss_per_primary_cohort"] = (2 * _ratio(jss, pry)).where(ok)
    df["jss_places_gap"] = jss_places_gap(df, ins["jss"]["target_transition"])

    # 4. Is there a private alternative? Private returns are thin nationally, so the
    # share is only shown where at least half of expected private forms came back.
    prv = _col(df, "private_learners")
    df["private_reporting_rate"] = _ratio(_col(df, "private_reports_actual"), _col(df, "private_reports_expected")).clip(upper=1.0)
    share = _ratio(prv.fillna(0), prv.fillna(0) + df.learners)
    df["private_share"] = share.where(df.private_reporting_rate >= ins["private"]["reporting_at_least"])
    df["few_private_places"] = df.private_share < ins["private"]["share_below"]

    # 5. Change since 2014 (NMIS survey vs 2024 census; different instruments, so only
    # large moves are labelled).
    change = df.ltr / df.nmis_ltr - 1
    t = ins["change_since_2014"]["threshold"]
    df["ltr_change_since_2014"] = change.where(ranked)
    df["trend_since_2014"] = np.select(
        [change > t, change < -t, change.notna()], ["Worse", "Better", "Similar"], default=None
    )
    df.loc[~ranked, "trend_since_2014"] = None

    # 6. Context for the LGA detail view.
    df["special_needs_share_pry"] = _ratio(_col(df, "special_needs_pry"), pry)
    df["dropout_rate_pry_all"] = _ratio(_col(df, "pry_dropouts_all"), _col(df, "pry_learners_all"))
    df["orphan_share_pry_all"] = _ratio(_col(df, "pry_orphans_all"), _col(df, "pry_learners_all"))
    df["learners_per_computer_all"] = _ratio(_col(df, "learners_all"), _col(df, "computers_all"))
    df["learners_per_non_teaching_staff_all"] = _ratio(_col(df, "learners_all"), _col(df, "non_teaching_staff_all"))
    return df


def jss_places_gap(df, target_transition):
    """Extra public JSS places needed for target_transition of a primary cohort to have a seat in each JSS grade."""
    need = target_transition * _col(df, "pry_learners") / 2 - _col(df, "jss_learners")
    return np.ceil(need.clip(lower=0)).where(df.jss_per_primary_cohort.notna())


# ---------------------------------------------------------------- 7. budget
def budget_plan(view, teacher_cost, classroom_cost, budget, teachers_col="teachers_needed"):
    """Fund LGAs in priority order until the budget runs out.

    view must already be sorted by priority. Each LGA's full gap (teachers, then
    classrooms) is funded before the next; the last LGA reached is funded in part,
    teachers first. Costs are planner inputs: the census has no cost data.
    """
    rows, left = [], float(budget)
    for idx, r in view.iterrows():
        t_need, c_need = float(r[teachers_col] or 0), float(r.classrooms_needed or 0)
        t = min(t_need, np.floor(left / teacher_cost)) if teacher_cost > 0 else t_need
        left -= t * teacher_cost
        c = min(c_need, np.floor(left / classroom_cost)) if classroom_cost > 0 else c_need
        left -= c * classroom_cost
        full = t == t_need and c == c_need
        status = "Fully funded" if full else ("Partly funded" if t + c > 0 else "Not reached")
        rows.append((idx, t, c, t * teacher_cost + c * classroom_cost, t_need * teacher_cost + c_need * classroom_cost, status))
    out = pd.DataFrame(rows, columns=["idx", "teachers_funded", "classrooms_funded", "cost_funded", "cost_full_gap", "status"])
    return out.set_index("idx")


# ---------------------------------------------------------------- summary for the write-up
def summary(df, cfg):
    """National figures quoted in the README, write-up and app captions."""
    ins = cfg["insights"]
    r = df[df.confidence.isin(RANKED)]
    st = redeployment_by_state(df, ins["redeploy"]["movable_share"])

    def rho(a, b):
        d = r[[a, b]].dropna()
        return {"rho": round(float(spearmanr(d[a], d[b]).statistic), 2), "n": int(len(d))}

    trend = r.trend_since_2014.value_counts().to_dict()
    top20 = r.nsmallest(20, "rank")
    return {
        "scope": "Ranked LGAs (grades A-C), public schools, 2024 Annual School Census unless stated",
        "redeploy": {
            "movable_share": ins["redeploy"]["movable_share"],
            "shortfall": int(st.shortfall.sum()),
            "spare": int(st.spare.sum()),
            "covered_by_moves": int(st.covered_by_moves.sum()),
            "share_covered": round(float(st.covered_by_moves.sum() / st.shortfall.sum()), 3),
            "states_with_spare_over_shortfall": int((st.spare >= st.shortfall).sum()),
            "top_spare_states": st.sort_values("spare", ascending=False).head(3).adm1_name.tolist(),
            "top20_shortfall": int(top20.teachers_needed.sum()),
            "top20_covered_by_moves": int(top20.teachers_moved_in.sum()),
        },
        "female_teachers": {
            "median_share": round(float(r.female_teacher_share.median()), 3),
            "lgas_below_threshold": int(r.few_female_teachers.sum()),
            "threshold": ins["female_teachers"]["share_below"],
            "top20_below_threshold": int(top20.few_female_teachers.sum()),
            "need_vs_female_share": rho("need_score", "female_teacher_share"),
            "female_share_vs_girls_share": rho("female_teacher_share", "girls_share"),
        },
        "jss": {
            "lgas_measured": int(r.jss_per_primary_cohort.notna().sum()),
            "median_jss_per_primary_cohort": round(float(r.jss_per_primary_cohort.median()), 2),
            "lgas_below_half": int((r.jss_per_primary_cohort < 0.5).sum()),
            "places_gap_at_target": int(r.jss_places_gap.sum()),
            "target_transition": ins["jss"]["target_transition"],
            "need_vs_jss": rho("need_score", "jss_per_primary_cohort"),
        },
        "private": {
            "lgas_measured": int(r.private_share.notna().sum()),
            "national_private_return_rate": round(float(df.private_reports_actual.sum() / df.private_reports_expected.sum()), 3),
            "median_private_share": round(float(r.private_share.median()), 3),
            "lgas_few_private_places": int(r.few_private_places.sum()),
            "need_vs_private_share": rho("need_score", "private_share"),
        },
        "since_2014": {
            "lgas_compared": int(r.trend_since_2014.notna().sum()),
            "worse": int(trend.get("Worse", 0)),
            "similar": int(trend.get("Similar", 0)),
            "better": int(trend.get("Better", 0)),
            "threshold": ins["change_since_2014"]["threshold"],
            "top20_worse": int((top20.trend_since_2014 == "Worse").sum()),
        },
    }
