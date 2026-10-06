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

## Tuesday 6 October 2026 (scope locked)

- **Scope locked:** proceed as proposed. Use DNEMIS data with attribution and a note that no explicit licence is stated.
- Evaluated three further Kaggle datasets. All downloaded without login.
  - NMIS education facilities (2009-2014): recognised as a mirror of the official NMIS release (CC BY 4.0, energydata.info). The official host blocks scripted downloads, so we keep the Kaggle copy and cite the official source. A quick check gives Spearman 0.57 between 2014 and 2024 LGA learner-teacher ratios. **Kept** as a persistent-shortage signal and 2014 facility-condition context.
  - MICS6 2021 state workbook: a community transcription of the same UNICEF tables we already hold. **Kept as a cross-check** for our own extraction, not as a primary source.
  - JAMB 2024 student performance: synthetic by the author's own description, no geography. **Rejected and deleted.**
- Added both kept Kaggle sources to `scripts/fetch_data.py` and the provenance log. Pinned scipy.
- Built the LGA name crosswalk (`pipeline/crosswalk.py`): exact normalised match within state, then a hand-checked alias table (`config/lga_aliases.csv`), then a strict fuzzy match (cutoff 0.85, must be a clear winner), with any two rows landing on one P-code both rejected. DNEMIS: 774/774 matched (743 exact, 22 fuzzy, 9 alias). NMIS: 769/772; the 3 left over are ambiguous and documented in `config/unmatched_reasons.csv`. Every fuzzy match was reviewed by eye. "Munya" to Muya is correct: Niger has 25 LGAs and Munya is a common spelling of Muya. Yewa North and South are the post-2002 names of Egbado North and South.
- **Design change:** enrolment divided by projected school-age population tracks reporting completeness (median 0.09 in LGAs under 50% reporting vs 0.70 above 90%). So "hidden demand" cannot be an index component; it is now a flag shown only where reporting is at least 90%.
- **Design change:** a first rule excluded LGAs whose learners exceeded 1.6x the projected population. That removed 45 LGAs, mostly in Kano, Katsina, Yobe and Oyo, where the 2006-based projection and the inclusion of integrated Qur'anic and senior secondary learners explain the excess. Excluding them would have quietly pushed northern LGAs out. New rule: above 2.5x is not ranked (Dutsi, Potiskum, Ibi, Tofa, Takum); 1.6x to 2.5x is ranked with a "verify learner count" caveat that costs one confidence grade.
- Index: weighted mean of percentile ranks (teacher 0.50, classroom 0.35, toilet 0.15) among ranked LGAs. Result: 642 ranked (A 398, B 156, C 88), 132 not ranked with reasons. Spearman with the first principal component 0.987. Under 1,000 Dirichlet weight draws, 15 of the top 20 stay in the top 20 at least 80% of the time.
- "Main driver" first used the largest weighted contribution, which made every LGA say "Teacher shortage". Changed to the dimension where the LGA is most extreme relative to others, restricted to teachers or classrooms (toilets stay in the score but are not what this planner deploys).
- Added `python -m pipeline.build` and 16 pytest tests (crosswalk, ranking invariants, gap arithmetic, reproducible perturbation, "teachers to exit top 20" actually exits, partner CSV adapter).
