"""Lens 1: LGA teacher and classroom gap against the UBE 35:1 standard.

Steps: load inputs, grade data confidence, score eligible LGAs with a
transparent weighted percentile index, then compute the teachers and
classrooms each LGA needs. Every exclusion carries a plain-language reason.
"""
import math

import numpy as np
import pandas as pd
import yaml

from pipeline import sources
from pipeline.crosswalk import match_lgas
from pipeline.paths import CONFIG, DNEMIS_CONSTANTS, ROOT

COMPONENTS = {  # component -> (ratio column, standard key)
    "teacher": ("ltr", "learners_per_teacher"),
    "classroom": ("lcr", "learners_per_classroom"),
    "toilet": ("ltor", "learners_per_toilet"),
}
DRIVER_LABEL = {"teacher": "Teacher shortage", "classroom": "Classroom shortage", "toilet": "Toilet shortage"}


def load_settings():
    return yaml.safe_load(open(CONFIG / "settings.yaml", encoding="utf-8"))


def check_standards(cfg):
    """Stop if the config's standards disagree with the ones DNEMIS publishes."""
    const = pd.read_parquet(DNEMIS_CONSTANTS).set_index("id")["value"]
    published = {
        "learners_per_teacher": const["UBEstdLTR01"],
        "learners_per_classroom": const["UBEstdLCR01"],
        "learners_per_toilet": const["UBEstdLToR1"],
    }
    for k, v in published.items():
        if cfg["standards"][k] != v:
            raise ValueError(f"Standard {k}: config {cfg['standards'][k]} vs DNEMIS {v}")


def load_census(cfg):
    """Return (lga census table keyed on adm2_pcode, unmatched rows, vintage label)."""
    inp = cfg["lga_input"]
    if inp["adapter"] == "dnemis":
        census, unmatched = sources.dnemis_lga()
        return census, unmatched, "2024 Annual School Census"
    if inp["adapter"] == "csv":
        c = inp["csv"]
        raw = pd.read_csv(ROOT / c["path"])
        df = raw.rename(columns={v: k for k, v in c["columns"].items()})
        census, unmatched = match_lgas(df, "partner", "state", "lga")
        census = census.rename(
            columns={"reports_actual": "pp_reports_actual", "reports_expected": "pp_reports_expected", "lga": "lga_name_src"}
        )
        return census, unmatched, c["vintage"]
    raise ValueError(f"Unknown lga_input adapter: {inp['adapter']}")


def assemble(cfg):
    """One row per OCHA LGA (774) with census, population and 2014 NMIS fields."""
    spine = sources.boundaries()
    census, un_census, vintage = load_census(cfg)
    nmis, un_nmis = sources.nmis_lga()
    pop = sources.population_lga()
    df = (
        spine.merge(census, on="adm2_pcode", how="left")
        .merge(pop, on="adm2_pcode", how="left")
        .merge(nmis.drop(columns=["match_method"]), on="adm2_pcode", how="left")
    )
    if len(df) != 774 or df.adm2_pcode.duplicated().any():
        raise ValueError(f"Expected 774 unique LGAs, got {len(df)}")
    unmatched = pd.concat([un_census.assign(source="census"), un_nmis.assign(source="nmis")], ignore_index=True)
    return df, unmatched, vintage


def _ratio(num, den):
    return num / den.where(den > 0)


def grade(df, cfg):
    """Add ratios, reporting rate, plausibility checks, confidence grade and reasons."""
    c = cfg["confidence"]
    df = df.copy()
    df["ltr"] = _ratio(df.learners, df.teachers)
    df["lcr"] = _ratio(df.learners, df.classrooms)
    df["ltor"] = _ratio(df.learners, df.toilets)
    df["reporting_rate"] = _ratio(df.pp_reports_actual, df.pp_reports_expected).clip(upper=1.0)
    df["coverage"] = _ratio(df.learners, df.pop_5_14)

    reasons, caveats, grades = [], [], []
    for r in df.itertuples():
        why, caveat = [], []
        if any(pd.isna(getattr(r, f)) or getattr(r, f) <= 0 for f in ("learners", "teachers", "classrooms")):
            why.append("No learner, teacher or classroom count reported")
        if pd.isna(r.reporting_rate):
            why.append("Census return rate not reported")
        elif r.reporting_rate < c["reporting_min_ranked"]:
            why.append(f"Only {r.reporting_rate:.0%} of schools returned census forms")
        if pd.notna(r.ltr) and not (c["ratio_min_plausible"] <= r.ltr <= c["ratio_max_plausible"]):
            why.append(f"Implausible ratio of {r.ltr:.0f} learners per teacher")
        if pd.notna(r.coverage) and r.coverage > c["coverage_max_plausible"]:
            why.append(f"Reported learners are {r.coverage:.1f}x the projected school-age population")
        elif pd.notna(r.coverage) and r.coverage > c["coverage_caveat_above"]:
            caveat.append(f"Verify learner count: {r.coverage:.1f}x the projected school-age population")
        if (
            pd.notna(r.coverage)
            and pd.notna(r.reporting_rate)
            and r.reporting_rate >= c["reporting_grade_a"]
            and r.coverage < c["coverage_min_plausible"]
        ):
            why.append(f"Reported learners are only {r.coverage:.0%} of the projected school-age population")

        if why:
            g = "Not ranked"
        elif r.reporting_rate >= c["reporting_grade_a"]:
            g = "A"
        elif r.reporting_rate >= c["reporting_grade_b"]:
            g = "B"
        else:
            g = "C"
        if caveat and g in ("A", "B"):
            g = chr(ord(g) + 1)  # a caveat costs one grade
        grades.append(g)
        reasons.append("; ".join(why))
        caveats.append("; ".join(caveat))
    df["confidence"] = grades
    df["not_ranked_reason"] = reasons
    df["caveat"] = caveats
    # A toilet count above the learner count is an entry error: drop that component only.
    bad_toilet = df.toilets.gt(df.learners) | df.toilets.isna() | df.toilets.le(0)
    df.loc[bad_toilet, "ltor"] = np.nan
    df["toilet_data_ok"] = ~bad_toilet
    return df


def percentile_scores(df):
    """Percentile rank (0-1, higher = worse) of each component among ranked LGAs."""
    out = pd.DataFrame(index=df.index)
    for comp, (col, _) in COMPONENTS.items():
        out[comp] = df[col].rank(pct=True)
    # LGAs without usable toilet data get the median toilet score, so the
    # missing field neither helps nor hurts them.
    out["toilet"] = out["toilet"].fillna(0.5)
    return out


def score(pct, weights):
    w = pd.Series(weights)[pct.columns]
    return pct.mul(w, axis=1).sum(axis=1) / w.sum() * 100


def gaps(df, std):
    """Teachers and classrooms needed to reach the standard, given current learners."""
    teachers_needed = np.ceil(df.learners / std["learners_per_teacher"]) - df.teachers
    rooms_needed = np.ceil(df.learners / std["learners_per_classroom"]) - df.classrooms
    return teachers_needed.clip(lower=0), rooms_needed.clip(lower=0)


def teachers_to_exit_top(df, pct, weights, top_n):
    """Extra teachers each top-n LGA needs before it drops out of the top n.

    Holds every other LGA and every other component fixed, raises this LGA's
    teacher count, and recomputes its teacher percentile against the rest.
    """
    s = score(pct, weights)
    order = s.sort_values(ascending=False)
    cutoff = order.iloc[top_n] if len(order) > top_n else 0
    others_ltr = df["ltr"]
    w = pd.Series(weights)
    out = {}
    for idx in order.index[:top_n]:
        row = df.loc[idx]
        rest = others_ltr.drop(idx).dropna().to_numpy()
        fixed = sum(w[k] * pct.loc[idx, k] for k in w.index if k != "teacher")

        def new_score(extra):
            ltr = row.learners / (row.teachers + extra)
            p = (np.sum(rest < ltr) + 1) / (len(rest) + 1)
            return (fixed + w["teacher"] * p) / w.sum() * 100

        if new_score(10**6) >= cutoff:
            out[idx] = np.nan  # teachers alone cannot move it out; classrooms matter too
            continue
        lo, hi = 0, 1
        while new_score(hi) >= cutoff:
            hi *= 2
        while hi - lo > 1:
            mid = (lo + hi) // 2
            lo, hi = (mid, hi) if new_score(mid) >= cutoff else (lo, mid)
        out[idx] = hi
    return pd.Series(out, dtype="float")


def stability(pct, weights, cfg_stab, top_n):
    """Share of random weight draws in which each LGA lands in the top n."""
    rng = np.random.default_rng(cfg_stab["seed"])
    base = pd.Series(weights)[pct.columns].to_numpy()
    draws = rng.dirichlet(cfg_stab["concentration"] * base / base.sum(), size=cfg_stab["draws"])
    hits = pd.Series(0, index=pct.index, dtype=float)
    m = pct.to_numpy()
    for w in draws:
        s = m @ w
        top = np.argsort(-s)[:top_n]
        hits.iloc[top] += 1
    return hits / len(draws), draws


def pca_check(pct, base_score):
    """Rank agreement between the weighted index and the first principal component."""
    from scipy.stats import spearmanr

    z = (pct - pct.mean()) / pct.std()
    u, s, vt = np.linalg.svd(z.to_numpy(), full_matrices=False)
    pc1 = pd.Series(z.to_numpy() @ vt[0], index=pct.index)
    if np.corrcoef(pc1, base_score)[0, 1] < 0:
        pc1, vt[0] = -pc1, -vt[0]
    rho = spearmanr(pc1, base_score).statistic
    return {
        "pc1_loadings": dict(zip(pct.columns, np.round(vt[0], 3))),
        "pc1_variance_share": float(s[0] ** 2 / np.sum(s**2)),
        "spearman_index_vs_pc1": float(rho),
    }


def build(cfg=None):
    cfg = cfg or load_settings()
    check_standards(cfg)
    df, unmatched, vintage = assemble(cfg)
    df = grade(df, cfg)
    std = cfg["standards"]
    df["teachers_needed"], df["classrooms_needed"] = gaps(df, std)

    ranked = df[df.confidence != "Not ranked"].copy()
    pct = percentile_scores(ranked)
    weights = cfg["index"]["weights"]
    ranked["need_score"] = score(pct, weights)
    ranked["rank"] = ranked.need_score.rank(ascending=False, method="first").astype(int)
    # Main driver: the dimension on which this LGA is most extreme relative to
    # other LGAs (unweighted percentile), so a planner sees what to send first.
    # Toilets count in the score but are not something this planner deploys,
    # so the driver names teachers or classrooms only.
    ranked["main_driver"] = pct[["teacher", "classroom"]].idxmax(axis=1).map(DRIVER_LABEL)
    for comp in COMPONENTS:
        ranked[f"pct_{comp}"] = pct[comp]

    top_n = cfg["index"]["top_n"]
    share, draws = stability(pct, weights, cfg["index"]["stability"], top_n)
    ranked["top20_share"] = share
    ranked["persistent_top20"] = share >= cfg["index"]["stability"]["persistent_share"]
    ranked["teachers_to_exit_top20"] = teachers_to_exit_top(ranked, pct, weights, top_n)

    # Persistent shortage: worst quartile in both 2014 and 2024.
    q = cfg["persistence"]["quantile"]
    both = ranked.nmis_ltr.notna()
    ranked["persistent_shortage"] = (
        both & (ranked.ltr >= ranked.ltr.quantile(q)) & (ranked.nmis_ltr >= ranked.loc[both, "nmis_ltr"].quantile(q))
    )
    hd = cfg["hidden_demand"]
    ranked["hidden_demand_flag"] = (ranked.coverage < hd["coverage_below"]) & (
        ranked.reporting_rate >= hd["reporting_at_least"]
    )

    df = df.merge(
        ranked[
            [
                "adm2_pcode", "need_score", "rank", "main_driver", "pct_teacher", "pct_classroom", "pct_toilet",
                "top20_share", "persistent_top20", "teachers_to_exit_top20", "persistent_shortage", "hidden_demand_flag",
            ]
        ],
        on="adm2_pcode",
        how="left",
    )
    meta = {
        "vintage": vintage,
        "weights": weights,
        "standards": std,
        "n_lgas": int(len(df)),
        "n_ranked": int(len(ranked)),
        "grades": df.confidence.value_counts().to_dict(),
        "pca": pca_check(pct, ranked.need_score),
        "weight_draws_summary": {
            k: [float(np.percentile(draws[:, i], 5)), float(np.percentile(draws[:, i], 95))]
            for i, k in enumerate(pct.columns)
        },
        "n_persistent_top20": int(ranked.persistent_top20.sum()),
    }
    return df, unmatched, meta
