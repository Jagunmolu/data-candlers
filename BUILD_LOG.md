# Build Log

Dated record of decisions, dead ends and reasons. Newest entries at the bottom of each day.

## Sunday 4 October 2026 (Phase 0: data audit and problem lock)

- Started the build in an empty folder. Initialised git and a dedicated virtual environment (`.venv`, Python 3.12.7). Chose 3.12 over the also-installed 3.14 for wheel availability and Streamlit Community Cloud compatibility.
- Read the brief. Its "Saturday, October 11" is a Sunday in 2026, so I planned to finish by Saturday 10 October to be safe.
- Confirmed internet access. NBS, UBEC, HDX and UNICEF downloads work. `grid3.gov.ng` timed out; its education layer is mirrored on HDX so that was not a blocker. `open.africa` returned 403.
- **Dead end:** GRID3 school points carry teacher and student fields, but only ~7.5% are filled, none in 15 states, and some are corrupt (teacher total 643 million). Not usable for ratios.
- **Dead end:** Niger State is largely missing from GRID3 (16 of 25 LGAs with zero schools). A naive access index would have flagged Niger for missing data rather than need. This is why every ranking needs a data-confidence grade.
- **Dead end:** NBS WAEC 2019-2021 is image-only and broken down by geopolitical zone, not state. State WAEC exists only for 2016-2018.
- UBEC digest 2019/2020 is state level only. Its own method note says 2019-2020 values are extrapolated from the 2018 personnel audit plus a 4.5% school sample.
- **Breakthrough:** the Federal Ministry of Education's DNEMIS portal publishes the 2024 Annual School Census as public parquet files: 774 LGAs with public-school learners, teachers, usable classrooms, toilets, and expected vs actual census returns. This gives measured LGA teacher data, fresher than every other source.
- DNEMIS quality: 101 LGAs returned under half their expected census forms; Rivers, Cross River and Nasarawa are near-blind. Decision: rank only LGAs passing completeness and plausibility checks, and list the rest as "insufficient data" with the reason, rather than imputing.
- Wrote `scripts/fetch_data.py` so all raw data can be re-downloaded, with a provenance log (URL, date, size, SHA-256).
- Proposed scope: see `docs/DATA_AUDIT.md`.
