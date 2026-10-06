"""Map state and LGA names from each source onto OCHA COD-AB P-codes.

Matching order within a state: exact match on a normalised name, then the
hand-maintained alias table (config/lga_aliases.csv), then a strict fuzzy
match. Every row records how it was matched so non-exact matches can be
reviewed, and anything left over goes to an unmatched report with a reason.
"""
import difflib
import re

import pandas as pd

from pipeline.paths import CONFIG, RAW

FUZZY_CUTOFF = 0.85


def norm(name):
    """Lowercase, drop punctuation and spaces: 'Ile-Oluji/Okeigbo' -> 'ileolujiokeigbo'."""
    return re.sub(r"[^a-z]", "", str(name).lower())


def load_admin():
    """OCHA admin 1 and admin 2 tables with normalised name keys."""
    xl = RAW / "boundaries" / "nga_admin_boundaries.xlsx"
    adm1 = pd.read_excel(xl, sheet_name="nga_admin1")[["adm1_name", "adm1_pcode"]]
    adm2 = pd.read_excel(xl, sheet_name="nga_admin2")[
        ["adm2_name", "adm2_pcode", "adm1_name", "adm1_pcode", "area_sqkm", "center_lat", "center_lon"]
    ]
    adm1["key"] = adm1.adm1_name.map(norm)
    adm2["key"] = adm2.adm2_name.map(norm)
    return adm1, adm2


def state_pcode(raw_state, adm1):
    """Resolve a state label from any source ('an Anambra state', 'akwa', 'fct') to a P-code."""
    raw = re.sub(r"^[a-z]{2} (?=[A-Z])", "", str(raw_state))  # DNEMIS prefix: 'ko Kogi State'
    s = norm(re.sub(r"(?i)\bstate\b", "", raw))
    if s in ("fct", "abuja", "federalcapitalterritory"):
        return "NG015"
    hit = adm1[adm1.key == s]
    if hit.empty:
        # Some sources keep only the first word ('akwa', 'cross').
        hit = adm1[adm1.key.str.startswith(s)] if len(s) >= 4 else hit
    return hit.adm1_pcode.iloc[0] if len(hit) == 1 else None


def load_aliases():
    path = CONFIG / "lga_aliases.csv"
    a = pd.read_csv(path, dtype=str, comment="#")
    return {(r.source, r.adm1_pcode, norm(r.source_name)): r.adm2_pcode for r in a.itertuples()}


def match_lgas(df, source, state_col, lga_col):
    """Add adm1_pcode, adm2_pcode and match_method columns to df.

    Returns (matched_df, unmatched_df). df must have one row per source LGA.
    """
    adm1, adm2 = load_admin()
    aliases = load_aliases()
    out = df.copy()
    out["adm1_pcode"] = out[state_col].map(lambda s: state_pcode(s, adm1))
    pcodes, methods = [], []
    for st, name in zip(out.adm1_pcode, out[lga_col]):
        cands = adm2[adm2.adm1_pcode == st]
        key = norm(name)
        hit = cands[cands.key == key]
        if st is None:
            pcodes.append(None)
            methods.append("unmatched: state not resolved")
        elif len(hit) == 1:
            pcodes.append(hit.adm2_pcode.iloc[0])
            methods.append("exact")
        elif (source, st, key) in aliases:
            pcodes.append(aliases[(source, st, key)])
            methods.append("alias")
        else:
            close = difflib.get_close_matches(key, cands.key.tolist(), n=2, cutoff=FUZZY_CUTOFF)
            if len(close) == 1 or (len(close) == 2 and _clear_winner(key, close)):
                pcodes.append(cands[cands.key == close[0]].adm2_pcode.iloc[0])
                methods.append(f"fuzzy:{close[0]}")
            else:
                pcodes.append(None)
                methods.append("unmatched: no name within state" if not close else "unmatched: ambiguous fuzzy")
    out["adm2_pcode"] = pcodes
    out["match_method"] = methods

    # Two source rows landing on one P-code means a bad match; unmatch both.
    dup = out.adm2_pcode.notna() & out.duplicated("adm2_pcode", keep=False)
    out.loc[dup, "match_method"] = "unmatched: duplicate target " + out.loc[dup, "adm2_pcode"]
    out.loc[dup, "adm2_pcode"] = None

    unmatched = out[out.adm2_pcode.isna()].assign(source=source)
    return out[out.adm2_pcode.notna()], unmatched


def _clear_winner(key, close):
    r = [difflib.SequenceMatcher(None, key, c).ratio() for c in close]
    return r[0] - r[1] >= 0.05
