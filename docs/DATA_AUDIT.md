# Phase 0 Data Audit

Audit date: Sunday 4 October 2026. Internet access from the build environment: **yes**. Every file below was downloaded by `scripts/fetch_data.py`; sizes and SHA-256 hashes are in `data/raw/provenance.csv`.

## Summary

| # | Source | Unit | Vintage | Go? | Role |
|---|---|---|---|---|---|
| A | FME DNEMIS Annual School Census (ASC) | **774 LGAs**, 37 states | **2024** | **GO (core)** | Lens 1: teachers, learners, classrooms, toilets, reporting completeness |
| B | NBS WAEC Results Statistics 2016-2018 | 37 states | 2016, 2017, 2018 | GO | Lens 2 target |
| C | NBS WAEC Results Statistics 2019-2021 | 6 zones only | 2019-2021 | Limited | Zone-level stability check only |
| D | UBEC Digest of Basic Education Statistics 2019 and 2020 | 37 states | 2018-2020 | GO | Lens 2 predictors; state cross-check of A |
| E | OCHA COD-AB boundaries (HDX) | 774 LGAs | valid 2019-2025 | GO | Map, join keys (P-codes) |
| F | UNFPA COD-PS population (HDX) | 773 LGAs | 2020 projection from 2006 census | GO | School-age population for hidden-demand flag |
| G | GRID3 NGA Education Facilities (HDX) | 204,513 school points | ~2020 | Cross-check only | Independent school counts; teacher/pupil fields unusable |
| H | UNICEF Nigeria Education Fact Sheets 2023 (MICS6 2021) | 37 states | 2021 | GO (validation only) | Out-of-school rate, foundational skills |
| I | HOT OpenStreetMap education facilities | points | 2026 | No-go | Volunteer coverage, too uneven to rank on |
| J | NBS 2006 National School Census microdata | LGA | 2006 | No-go | Too old, registration required |
| K | NMIS education facility survey (Kaggle mirror) | 98,667 schools, 772 LGAs | 2009-2014 | **GO (secondary)** | "Persistent shortage" signal and 2014 facility conditions |
| L | MICS6 2021 state tables workbook (Kaggle) | 37 states | 2021 | Cross-check only | Second transcription to reconcile our extraction of H |
| M | "Students Performance in 2024 JAMB" (Kaggle) | individual rows, no geography | n/a | **Rejected, deleted** | Synthetic by the author's own description |

## Source detail

### A. DNEMIS Annual School Census 2024 (Federal Ministry of Education)
- URL: https://emis.education.gov.ng/portal/ (data files listed at `/portal/data/manifest.json`, served as parquet)
- Retrieved: 2026-10-04. Format: 8 parquet tables in a star schema (`fact`, `fact_ownership`, `fact_schooltype`, `fact_typeown`, `dx` indicator names, `ou` org units, `pe` period, `constants`).
- Units: `ou` has 812 rows = 1 national + 37 states + 774 LGAs. Period: 2024 only.
- Licence: no explicit licence found. Publicly served by a federal government portal and marked `isAccessibleForFree: true` in its schema.org metadata. Aggregate counts only, no personal data. We attribute it in the README.
- Key indicators (public schools, via `fact_ownership`): learners (all levels), teachers, usable classrooms, usable toilets, school counts. UBE standards shipped in `constants`: learner-teacher 35, learner-classroom 35, learner-toilet 30.
- Coverage (public, LGA level): learners 731/774, teachers 729/774, classrooms 728/774, toilets 726/774.
- **Reporting completeness** is measured: `MD: Pre&Primary actual reports` vs `expected reports` (771 LGAs). Median LGA rate 0.94; **101 LGAs under 50%**. Near-blind states: Rivers (0.1%), Cross River (2%), Nasarawa (6%), Benue (33%).
- Quality flags found: Cross River totals only 610 public teachers; some extreme ratios (Dutsi, Katsina 453:1; Owan East, Edo 273:1) need plausibility checks; one toilet value of 211,559 is a clear entry error.
- Decision: **core of Lens 1**. Ratios are only reported where reporting completeness and plausibility checks pass; others are shown as "insufficient data" with the reason.

### B. NBS WAEC Results Statistics 2016-2018
- URL: https://nigerianstat.gov.ng/download/1001. Report date Sept 2019. PDF, 94 pages, text layer present.
- One infographic page pair per state with male, female, total for: number sat, 5 credits incl. English, incl. Maths, incl. English and Maths, and the percentage. "Public" here means school candidates (about 1.57m in 2018); "private" means private (GCE-style) candidates (about 110k).
- Extraction risk: numbers are interleaved by the layout. Mitigation: each triple must satisfy male + female = total, recomputed percentages must match published ones, and state totals must sum to the national figures in the executive summary (e.g. 2018 public: 1,571,536 sat, 756,726 with 5 credits incl. English and Maths, 48.15%).
- Decision: **Lens 2 target**, 37 states x 3 years = 111 state-years.

### C. NBS WAEC Results Statistics 2019-2021
- URL: https://nigerianstat.gov.ng/download/1241213. 21 pages, mostly images. Broken down by **geopolitical zone, not state**, and "public/private" here means school ownership, a different definition from report B.
- Decision: not usable for state modelling. At most a zone-level trend check, labelled as such.

### D. UBEC Digest of Basic Education Statistics 2019 and 2020 (Vols I-III)
- URLs: https://ubec.gov.ng/wp-content/uploads/2024/04/2019-AND-2020-Digest-of-Statistics-Volume-I.pdf (and -II, -III). Text layer present.
- **State level only** (no LGA tables). Built on the 2018 National Personnel Audit plus a 4.5% sample update in 2021 with extrapolation; the digest says so itself, so 2019-2020 values are partly modelled.
- Useful tables: trend 2018-2020 in public schools, enrolment, teachers, qualified teachers, classrooms and their condition, by state.
- Decision: Lens 2 predictors (2018 values align with WAEC 2018) and a state-level sanity check on DNEMIS 2024.

### E. OCHA COD-AB administrative boundaries
- URL: https://data.humdata.org/dataset/cod-ab-nga. Licence CC BY-IGO. 37 states, 774 LGAs with P-codes. Modified 2026-08-14.
- Decision: base geography and join key. LGA names will be crosswalked to DNEMIS names (DNEMIS names carry a two-letter state prefix and an " LGA" suffix).

### F. COD-PS subnational population
- URL: https://data.humdata.org/dataset/cod-ps-nga. Licence CC BY-IGO. 2020 LGA projections by sex and five-year age band (773 LGAs; Bakassi missing, ceded territory). 2022 version is state level only.
- Caveat: projected from the 2006 census, so LGA figures are uncertain. Used only for a secondary "hidden demand" flag (public enrolment relative to school-age population), never as the headline ranking.

### G. GRID3 NGA Education Facilities
- URL: https://data.humdata.org/dataset/nigeria-education-facilities. Licence CC BY. 204,513 points with category and management.
- `no_of_teac` / `no_of_stud` are filled for only ~7.5% of schools, zero in 15 states, and contain corrupt values (teacher sum of 643 million). **Not usable** for ratios.
- Spatial join to LGAs works (155 of 202,052 points unmatched), but **Niger State is a coverage hole**: 16 of 25 LGAs have zero schools.
- Decision: independent cross-check of DNEMIS school counts per LGA only.

### H. UNICEF Nigeria Education Fact Sheets 2023 (MICS6 2021)
- URL: https://unicef.org/nigeria/media/9211/file/Nigeria%20Education%20Fact%20Sheets.pdf. 74 pages, mostly text layer.
- State tables: out-of-school rates (pp. 31-32), completion (p. 9), foundational reading and numeracy (p. 23, may need visual extraction).
- Decision: **validation only**, never a model input.

## Additions reviewed on 6 October 2026 (Kaggle leads)

All three downloaded without a Kaggle login via `https://www.kaggle.com/api/v1/datasets/download/<owner>/<slug>`.

### K. Educational facilities in Nigeria (ayeniibukun) = NMIS 2014
- Kaggle URL: https://www.kaggle.com/datasets/ayeniibukun/educational-facilities-in-nigeria (listed as Apache 2.0, no description).
- Identified as a mirror of the official **Nigeria MDG Information System (NMIS) education facility data**, collected by OSSAP-MDGs with Columbia University's Sustainable Engineering Lab. Same row count (98,667) and fields as the official release on energydata.info, licensed **CC BY 4.0**: https://energydata.info/dataset/nigeria-nmis-education-facility-data-2014. The official host returns 403 to scripts, so we keep the Kaggle bytes and cite the official release as the source.
- Survey dates 2009-2014 (mostly 2012 and 2014). 772 LGAs in 37 states. Per school: teachers, learners, classrooms, toilets, teachers with NCE, improved water, improved sanitation, grid electricity, chalkboard in every classroom, coordinates, LGA key (`state_lga`).
- Fill rates: teachers 98%, learners 95%, classrooms 97%.
- Quick test: public learner-teacher ratio by LGA in 2014 vs DNEMIS 2024, rough name match on 682 LGAs, **Spearman rho = 0.57**. Shortages persist, and an independent survey corroborates the 2024 census.
- Decision: **secondary input**. (1) A "persistent shortage" flag for LGAs short of teachers in both 2014 and 2024, which also raises the confidence grade when two independent sources agree. (2) LGA facility conditions (water, sanitation, power) shown as 2014 context in the LGA detail view, never in the headline 2024 gap.

### L. Nigeria Education Access and Outcomes by State 2021 (tinaukabi)
- Kaggle URL: https://www.kaggle.com/datasets/tinaukabi/nigeria-education-access-and-outcomes-by-state-2021 (licence unknown).
- Not a UBEC digest, despite the label it was shared under. It is a student analysis workbook transcribing MICS6 2021 state tables (out-of-school, dropout, foundational reading and numeracy by state and sex, location and wealth) plus World Bank and UNESCO national series.
- Decision: **cross-check only**. Our primary validation source stays the UNICEF fact sheet (H). We extract H ourselves and reconcile against this workbook; any disagreement is logged.

### M. Students Performance in 2024 JAMB (idowuadamo)
- Kaggle URL: https://www.kaggle.com/datasets/idowuadamo/students-performance-in-2024-jamb
- The author describes it as "synthetically generated". 5,000 rows with no state or LGA field, so it cannot attach to any geography in this tool.
- Decision: **rejected and deleted** from `data/raw`. Using it would add a synthetic input with no link to the planning question.

## Scope consequence

The recommended concept assumed LGA teacher data might be unobtainable. It is obtainable, and recent: DNEMIS 2024 gives measured public-school teachers, learners and classrooms for most LGAs. Lens 1 therefore becomes a measured **teacher and classroom gap** against the government's own UBE 35:1 standard, not an access proxy. See `BUILD_LOG.md` for the scope decision.
