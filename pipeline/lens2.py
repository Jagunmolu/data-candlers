"""Lens 2: state WAEC results, expected vs actual (state context only).

Target: share of school candidates ("public" in the NBS report) with five
credits including English and Mathematics, pooled 2016-2018 and weighted by
candidates. Predictors: 2018 public basic-education resources from the UBEC
digest. With 37 states we use ridge regression, judge it only by
leave-one-state-out (LOSO) error against a national-mean baseline, and flag a
state only when its actual result falls outside a 90% interval built from
the LOSO errors (split-conformal style).

This is a description of how results line up with reported resources, not a
causal estimate, and it says nothing about individual LGAs.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from pipeline.extract_ubec import state_resources
from pipeline.paths import INTERIM

PREDICTORS = ["ltr_jss", "share_qualified_jss", "share_good_rooms_jss", "lcr_jss", "ltr_primary", "share_qualified_primary"]
ALPHAS = np.logspace(-2, 3, 30)
INTERVAL = 0.90


def waec_target(exclude=(("Taraba", 2018),)):
    """Candidate-weighted pass rate per state, school candidates, with per-year rates kept."""
    w = pd.read_parquet(INTERIM / "waec_state_2016_2018.parquet")
    w = w[(w.unit == "state") & (w.candidate_type == "public") & w.layout_ok].copy()
    for state, year in exclude:
        w = w[~((w.state_src == state) & (w.year == year))]
    w["rate"] = 100 * w.credit5_eng_maths_total / w.sat_total
    pooled = w.groupby("adm1_pcode").agg(
        sat=("sat_total", "sum"), passes=("credit5_eng_maths_total", "sum"), years=("year", "nunique")
    )
    pooled["actual"] = 100 * pooled.passes / pooled.sat
    by_year = w.pivot_table(index="adm1_pcode", columns="year", values="rate").add_prefix("rate_")
    return pooled.join(by_year).reset_index()


def model():
    return make_pipeline(StandardScaler(), RidgeCV(alphas=ALPHAS))


def loso(df, target="actual", predictors=PREDICTORS):
    """Leave-one-state-out predictions for the model and the mean baseline."""
    X, y = df[predictors].to_numpy(), df[target].to_numpy()
    pred, base = np.empty(len(df)), np.empty(len(df))
    for i in range(len(df)):
        keep = np.arange(len(df)) != i
        pred[i] = model().fit(X[keep], y[keep]).predict(X[i : i + 1])[0]
        base[i] = y[keep].mean()
    return pred, base


def fit():
    ubec = pd.read_parquet(INTERIM / "ubec_state_2018_2020.parquet")
    df = waec_target().merge(state_resources(ubec, 2018), on="adm1_pcode", how="inner")
    if len(df) != 37:
        raise ValueError(f"Lens 2 expects 37 states, got {len(df)}")

    df["expected"], df["baseline"] = loso(df)
    df["residual"] = df.actual - df.expected
    # Interval half-width: the 90th percentile of absolute LOSO errors, with the
    # small-sample conformal correction ceil((n+1) * 0.9) / n.
    n = len(df)
    q = min(1.0, np.ceil((n + 1) * INTERVAL) / n)
    half = float(np.quantile(np.abs(df.residual), q))
    df["lower"], df["upper"] = df.expected - half, df.expected + half
    df["flag"] = np.select([df.actual < df.lower, df.actual > df.upper], ["Below expected", "Above expected"], "Within range")

    rmse = lambda e: float(np.sqrt(np.mean(np.square(e))))
    full = model().fit(df[PREDICTORS], df.actual)
    coefs = dict(zip(PREDICTORS, np.round(full[-1].coef_, 3)))

    # Stability: refit on each single year and see whether the flags hold.
    stab = {}
    for year in (2016, 2017, 2018):
        col = f"rate_{year}"
        d = df.dropna(subset=[col]).copy()
        p, _ = loso(d, target=col)
        r = d[col] - p
        h = float(np.quantile(np.abs(r), min(1.0, np.ceil((len(d) + 1) * INTERVAL) / len(d))))
        stab[year] = pd.Series(np.select([r < -h, r > h], ["Below expected", "Above expected"], "Within range"), index=d.adm1_pcode)
    stab = pd.DataFrame(stab)
    df = df.merge(stab.add_prefix("flag_").reset_index(), on="adm1_pcode", how="left")
    df["flag_years_agree"] = df.apply(
        lambda r: sum(r[f"flag_{y}"] == r.flag for y in (2016, 2017, 2018) if pd.notna(r[f"flag_{y}"])), axis=1
    )

    meta = {
        "n_states": n,
        "years": [2016, 2017, 2018],
        "excluded": ["Taraba 2018: report prints 75 school candidates vs 21,754 in 2017; national page implies about 17,581"],
        "predictors": PREDICTORS,
        "standardised_coefficients": coefs,
        "ridge_alpha": float(full[-1].alpha_),
        "loso_rmse_model": rmse(df.residual),
        "loso_rmse_baseline": rmse(df.actual - df.baseline),
        "loso_r2": float(1 - np.sum(df.residual**2) / np.sum((df.actual - df.baseline) ** 2)),
        "interval_level": INTERVAL,
        "interval_half_width": half,
        "n_flagged": int((df.flag != "Within range").sum()),
    }
    return df, meta


if __name__ == "__main__":
    import json

    d, m = fit()
    print(json.dumps(m, indent=1))
    print(d.sort_values("residual")[["adm1_pcode", "actual", "expected", "lower", "upper", "flag", "flag_years_agree"]].round(1).to_string())
