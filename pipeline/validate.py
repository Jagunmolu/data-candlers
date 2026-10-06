"""External checks of Lens 1 against data it never used.

1. MICS6 2021 state indicators (out-of-school, foundational reading and
   numeracy) vs the state aggregate of the LGA need score.
2. DNEMIS 2024 learner-teacher ratio vs UBEC 2018 (an older, separately
   collected census) at state level.
3. NMIS 2014 vs DNEMIS 2024 learner-teacher ratio at LGA level.
"""
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from pipeline.paths import INTERIM


def _rho(a, b):
    r = spearmanr(a, b, nan_policy="omit")
    return {"rho": round(float(r.statistic), 3), "p": float(r.pvalue), "n": int(pd.concat([a, b], axis=1).dropna().shape[0])}


def state_need(lga):
    r = lga[lga.confidence != "Not ranked"]
    return (
        r.groupby("adm1_pcode")
        .apply(lambda g: pd.Series({
            "need_score_state": np.average(g.need_score, weights=g.learners),
            "ltr_ranked_lgas": g.learners.sum() / g.teachers.sum(),
            "n_ranked_lgas": len(g),
        }), include_groups=False)
        .reset_index()
    )


def run(lga):
    st = state_need(lga)
    mics = pd.read_parquet(INTERIM / "mics_state_2021.parquet")
    d = st.merge(mics, on="adm1_pcode")
    out = {"mics_2021": {f"need_score_vs_{c}": _rho(d.need_score_state, d[c]) for c in ("oos_primary", "reading", "numeracy")}}

    t = pd.read_parquet(INTERIM / "ubec_state_2018_2020.parquet")
    w = t[(t.year == 2018) & (t.measure == "total")].pivot_table(index="adm1_pcode", columns="table", values="value")
    w["ltr_ubec_2018"] = (w.enrolment_primary + w.enrolment_jss) / (w.teachers_primary + w.teachers_jss)
    z = st.merge(w[["ltr_ubec_2018"]].reset_index(), on="adm1_pcode")
    out["ubec_2018_state_ltr"] = _rho(z.ltr_ranked_lgas, z.ltr_ubec_2018)

    r = lga[lga.confidence != "Not ranked"]
    out["nmis_2014_lga_ltr"] = _rho(r.ltr, r.nmis_ltr)
    return out, st
