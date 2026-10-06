# Where Should the Next Teacher Go?

**YDP Community Datathon 2026, Education track. Status: scope approved, pipeline in progress.**

A decision tool for state and federal basic-education planners. It ranks Nigeria's Local Government Areas (LGAs) by how far their public schools fall short of the government's own Universal Basic Education standard of 35 learners per teacher and per classroom, shows how many teachers and classrooms would close each gap, and says plainly how much each ranking can be trusted.

## The problem (draft)

Nigeria publishes education data, but it is scattered across ministries, UBEC, NBS and WAEC, and rarely combined into an answer to the question a planner actually faces: *where should the next batch of teachers and classrooms go?* Two further problems make that harder:

1. **Uneven reporting.** In the 2024 Annual School Census, 101 of 774 LGAs returned fewer than half of their expected school forms. A ranking that ignores this rewards LGAs for not reporting.
2. **Mismatched levels.** Exam results (WAEC) are published by state, while deployment decisions are made by LGA. Tools that blur the two mislead.

## Approach

- **Lens 1, measured, LGA level (774 LGAs, 2024).** Public-school learner-teacher and learner-classroom ratios from the 2024 Annual School Census, compared with the UBE 35:1 standard. Output: the 20 LGAs most in need, the teachers and classrooms needed to reach the standard, the main driver, and a data-confidence grade based on census reporting completeness and plausibility checks.
- **Persistent shortage.** LGAs that were also short of teachers in the independent 2014 NMIS facility survey are flagged as long-running shortages. In a first check, 2014 and 2024 LGA ratios have a rank correlation of 0.57.
- **Lens 2, modelled, state level (37 units, 2016-2018).** Expected versus actual WAEC pass rate (five credits including English and Mathematics), predicted from state resource variables, with prediction intervals. Shown only as state context, never as an LGA outcome.
- **Validation** against independent MICS6 2021 state indicators (out-of-school rate, foundational skills).

## Data sources

| Source | Publisher | Unit | Vintage | Status | Licence |
|---|---|---|---|---|---|
| Annual School Census (DNEMIS) | Federal Ministry of Education | LGA, state | 2024 | Real, public | Public government portal, no explicit licence stated |
| WAEC Results Statistics 2016-2018 | NBS | State | 2016-2018 | Real, public | NBS public release |
| Digest of Basic Education Statistics 2019 and 2020 | UBEC | State | 2018-2020 | Real, public | UBEC public release |
| Subnational administrative boundaries (COD-AB) | OCHA via HDX | LGA | 2019-2025 | Real, public | CC BY-IGO |
| Subnational population statistics (COD-PS) | UNFPA via HDX | LGA | 2020 projection | Real, public (projected) | CC BY-IGO |
| Education facilities | GRID3 via HDX | School point | ~2020 | Real, public (cross-check only) | CC BY |
| Education Fact Sheets (MICS6 2021) | UNICEF / NBS | State | 2021 | Real, public (validation only) | UNICEF publication |
| NMIS education facility data | OSSAP-MDGs and Columbia SEL ([official release](https://energydata.info/dataset/nigeria-nmis-education-facility-data-2014)); bytes from a [Kaggle mirror](https://www.kaggle.com/datasets/ayeniibukun/educational-facilities-in-nigeria) | School, LGA | 2009-2014 | Real, public (secondary) | CC BY 4.0 |
| MICS6 2021 state tables workbook | Community transcription on [Kaggle](https://www.kaggle.com/datasets/tinaukabi/nigeria-education-access-and-outcomes-by-state-2021) | State | 2021 | Real, public (cross-check only) | Not stated |

No synthetic data is used. A synthetic Kaggle JAMB dataset was reviewed and rejected. Full audit: [`docs/DATA_AUDIT.md`](docs/DATA_AUDIT.md). Download provenance with checksums: `data/raw/provenance.csv`.

## Run it

Requires Python 3.12.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # macOS/Linux: .venv/bin/python
.venv/Scripts/python scripts/fetch_data.py                 # download raw sources (about 90 MB)
```

The app and the single reproduce-everything command will be added in the next phases.

## Limitations (known so far)

- DNEMIS 2024 reporting is incomplete in some states (Rivers, Cross River and Nasarawa are near-blind). These LGAs are listed as "insufficient data", not ranked or imputed.
- State WAEC results are only available for 2016-2018, so Lens 2 describes a past period and is labelled with its vintage.
- LGA population figures are projections from the 2006 census and are used only for a secondary flag.
- This is a prioritisation aid, not a causal analysis.

## Repository

See [`BUILD_LOG.md`](BUILD_LOG.md) for the dated record of decisions.
