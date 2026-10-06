"""Loaders that turn each raw source into a tidy table keyed on OCHA P-codes.

Each loader returns (table, unmatched) so the build can write one combined
unmatched-records report. Nothing here edits files in data/raw.
"""
import pandas as pd

from pipeline.crosswalk import load_admin, match_lgas, norm
from pipeline.paths import RAW

DNEMIS = RAW / "dnemis"
NMIS_CSV = RAW / "kaggle" / "educational-facilities-in-nigeria" / "educational-facilities-in-nigeria.csv"

# DNEMIS indicator ids (see dx.parquet).
DX = {
    "jwjKmtVK2wj": "learners",
    "Dw7f4gs9RcS": "teachers",
    "DvMfSq5pZSA": "classrooms",
    "vDmeu4io2Fs": "toilets",
    "U8ytqWQMFwD": "schools_public",
    "QLfdf8Jd9dc": "pp_reports_actual",
    "dh9fliYibms": "pp_reports_expected",
    "Yr6FePoHpHP": "jss_reports_actual",
    "S2cH9F1T7MU": "jss_reports_expected",
}


def dnemis_lga():
    """2024 Annual School Census, public schools, one row per LGA."""
    ou = pd.read_parquet(DNEMIS / "ou.parquet")
    lga = ou[ou.level == 3].copy()
    lga["lga_name_src"] = lga.name.str[3:].str.replace(r" LGA$", "", regex=True)

    own = pd.read_parquet(DNEMIS / "fact_ownership.parquet")
    pub = own[(own.category_name == "Public") & own.dx.isin(DX)].pivot_table(index="ou", columns="dx", values="value")
    fact = pd.read_parquet(DNEMIS / "fact.parquet")
    md = fact[fact.dx.isin(DX)].pivot_table(index="ou", columns="dx", values="value")
    vals = pub.join(md[[c for c in md.columns if c not in pub.columns]], how="outer").rename(columns=DX)

    lga = lga.join(vals, on="id")
    matched, unmatched = match_lgas(lga, "dnemis", "parent_name", "lga_name_src")
    cols = ["adm2_pcode", "id", "lga_name_src", "match_method"] + [c for c in DX.values() if c in matched.columns]
    return matched[cols].rename(columns={"id": "dnemis_id"}), unmatched


def _nmis_state_split(key, state_keys):
    """'akwa_ibom_uyo' -> ('akwa ibom', 'uyo') using the longest known state prefix."""
    for sk in state_keys:
        if key.startswith(sk + "_"):
            return sk.replace("_", " "), key[len(sk) + 1 :].replace("_", " ")
    return None, key.replace("_", " ")


def nmis_lga():
    """NMIS 2009-2014 facility survey, public schools aggregated to LGA."""
    df = pd.read_csv(NMIS_CSV, low_memory=False, encoding="latin-1")
    df = df[df.management == "public"].copy()
    num = ["num_tchr_full_time", "num_students_total", "num_classrms_total", "num_tchrs_with_nce"]
    for c in num:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["improved_water_supply", "improved_sanitation", "phcn_electricity"]:
        df[c] = df[c].map({True: 1.0, False: 0.0, "True": 1.0, "False": 0.0})

    # Ratios only from schools that report both learners and teachers.
    both = df.num_tchr_full_time.gt(0) & df.num_students_total.gt(0)
    g = df.groupby("unique_lga")
    agg = pd.DataFrame(
        {
            "nmis_schools": g.size(),
            "nmis_learners": df[both].groupby("unique_lga").num_students_total.sum(),
            "nmis_teachers": df[both].groupby("unique_lga").num_tchr_full_time.sum(),
            "nmis_share_water": g.improved_water_supply.mean(),
            "nmis_share_sanitation": g.improved_sanitation.mean(),
            "nmis_share_power": g.phcn_electricity.mean(),
        }
    ).reset_index()

    adm1, _ = load_admin()
    state_keys = sorted({"fct", *(a.lower().replace(" ", "_") for a in adm1.adm1_name)}, key=len, reverse=True)
    split = agg.unique_lga.map(lambda k: _nmis_state_split(k, state_keys))
    agg["state_src"] = split.str[0]
    agg["lga_name_src"] = split.str[1]
    matched, unmatched = match_lgas(agg, "nmis", "state_src", "lga_name_src")
    matched = matched.assign(nmis_ltr=matched.nmis_learners / matched.nmis_teachers.where(matched.nmis_teachers > 0))
    keep = ["adm2_pcode", "unique_lga", "match_method"] + [c for c in matched.columns if c.startswith("nmis_")]
    return matched[keep], unmatched


def population_lga():
    """COD-PS 2020 LGA projections: school-age population (ages 5-14 as the nearest bands to 6-14)."""
    pop = pd.read_excel(RAW / "population" / "nga_admpop_2020.xlsx", sheet_name="nga_admpop_adm2_2020")
    pop = pop.rename(columns={"ADM2_PCODE": "adm2_pcode"})
    pop["pop_5_14"] = pop.T_05_09 + pop.T_10_14
    return pop[["adm2_pcode", "T_TL", "pop_5_14"]].rename(columns={"T_TL": "pop_total"})


def boundaries():
    """OCHA LGA table (no geometry) used as the spine: exactly 774 rows."""
    _, adm2 = load_admin()
    return adm2.drop(columns="key")


__all__ = ["dnemis_lga", "nmis_lga", "population_lga", "boundaries", "norm"]
