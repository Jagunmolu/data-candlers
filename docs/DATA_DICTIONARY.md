# Data dictionary

Processed tables in `data/processed/`, all rebuilt by `python -m pipeline.build`. Keys are OCHA COD-AB P-codes (`adm1_pcode` state, `adm2_pcode` LGA).

## lga_index.parquet (774 rows, one per LGA)

| Column | Meaning | Source, year |
|---|---|---|
| adm2_pcode, adm2_name | LGA P-code and name | OCHA COD-AB |
| adm1_pcode, adm1_name | State P-code and name | OCHA COD-AB |
| area_sqkm, center_lat, center_lon | LGA area and centroid | OCHA COD-AB |
| dnemis_id, lga_name_src, match_method | Census org-unit id, its LGA name, and how it was matched (exact, alias, fuzzy:<name>) | DNEMIS 2024 |
| learners | Public-school learners, all levels | DNEMIS 2024 |
| teachers | Public-school teachers | DNEMIS 2024 |
| classrooms | Usable classrooms, public schools | DNEMIS 2024 |
| toilets | Usable toilets, public schools | DNEMIS 2024 |
| schools_public | Number of public schools | DNEMIS 2024 |
| pp_reports_actual, pp_reports_expected | Census forms returned vs expected, pre-primary and primary | DNEMIS 2024 |
| jss_reports_actual, jss_reports_expected | Same, junior secondary | DNEMIS 2024 |
| pop_total, pop_5_14 | Projected total population and ages 5-14 | UNFPA COD-PS 2020 (2006-based projection) |
| unique_lga | NMIS LGA key | NMIS 2009-2014 |
| nmis_schools | Public schools surveyed | NMIS |
| nmis_learners, nmis_teachers | Totals from public schools reporting both | NMIS |
| nmis_ltr | Learners per teacher | NMIS |
| nmis_share_water, nmis_share_sanitation, nmis_share_power | Share of public schools with improved water, improved sanitation, grid power | NMIS |
| ltr, lcr, ltor | Learners per teacher, per usable classroom, per usable toilet (ltor blank where toilet data is unusable) | derived, 2024 |
| reporting_rate | pp_reports_actual / pp_reports_expected, capped at 1 | derived, 2024 |
| coverage | learners / pop_5_14 (plausibility check only) | derived |
| confidence | A, B, C or "Not ranked" (rules in `config/settings.yaml`) | derived |
| not_ranked_reason | Why the LGA is not ranked; empty if ranked | derived |
| caveat | Ranked, but a value to verify (costs one grade) | derived |
| toilet_data_ok | False if the toilet count is missing, zero or above learners | derived |
| teachers_needed, classrooms_needed | Extra teachers or classrooms to reach 35:1 at current enrolment (0 if already at or below) | derived |
| need_score | 0-100, weighted mean of percentile ranks among ranked LGAs (higher = more need) | derived |
| rank | National rank among ranked LGAs (1 = most need) | derived |
| main_driver | "Teacher shortage" or "Classroom shortage": the dimension where the LGA is most extreme relative to others | derived |
| pct_teacher, pct_classroom, pct_toilet | Percentile of each ratio among ranked LGAs | derived |
| top20_share | Share of 1,000 random weightings with the LGA in the national top 20 | derived |
| persistent_top20 | top20_share >= 0.80 | derived |
| teachers_to_exit_top20 | Extra teachers that would move a top-20 LGA out of the top 20, other things equal (blank if teachers alone cannot) | derived |
| persistent_shortage | In the worst quarter for learners per teacher in both NMIS 2014 and DNEMIS 2024 | derived |
| hidden_demand_flag | Coverage below 0.40 where reporting is at least 90% (flag only) | derived |

### Insight columns (`pipeline/insights.py`; not part of the score)

| Column | Meaning | Source, year |
|---|---|---|
| pry_learners, jss_learners | Public primary and junior secondary learners | DNEMIS 2024 |
| girls | Public-school female learners, all levels | DNEMIS 2024 |
| female_teachers | Female public-school teachers | DNEMIS 2024 |
| special_needs_pry | Public primary learners with special needs | DNEMIS 2024 |
| iqte_schools | Public integrated Qur'anic (IQS/IQTE) schools | DNEMIS 2024 |
| private_learners | Private-school learners, all levels | DNEMIS 2024 |
| private_reports_actual, private_reports_expected | Private-school census forms returned vs expected | DNEMIS 2024 |
| pry_learners_all, pry_dropouts_all, pry_orphans_all, learners_all, computers_all, non_teaching_staff_all | Published for public and private schools together only | DNEMIS 2024 |
| teachers_spare | Teachers above what 35:1 needs at current enrolment (ranked LGAs) | derived |
| teachers_moved_in, teachers_to_hire | Base case (every spare teacher moves within the state, neediest LGAs first): teachers received and still to hire | derived |
| female_teacher_share, girls_share | female_teachers / teachers; girls / learners | derived |
| few_female_teachers | female_teacher_share below the threshold in settings (default 0.20) | derived |
| jss_reporting_rate | JSS forms returned / expected | derived |
| jss_per_primary_cohort | (jss_learners / 3) / (pry_learners / 6); blank where JSS returns are under 75% | derived |
| jss_places_gap | Extra public JSS places for the target share of a primary cohort (default 1.0) | derived |
| private_reporting_rate | Private forms returned / expected | derived |
| private_share | private / (private + public) learners; blank where private returns are under 50% | derived |
| few_private_places | private_share below the threshold in settings (default 0.05) | derived |
| ltr_change_since_2014 | ltr / nmis_ltr - 1 (ranked LGAs) | derived, NMIS 2014 and DNEMIS 2024 |
| trend_since_2014 | Worse, Similar or Better, using the threshold in settings (default 0.20) | derived |
| special_needs_share_pry | special_needs_pry / pry_learners | derived |
| dropout_rate_pry_all, orphan_share_pry_all | Over pry_learners_all | derived |
| learners_per_computer_all, learners_per_non_teaching_staff_all | learners_all / computers_all; learners_all / non_teaching_staff_all | derived |

## state_context.parquet (37 rows)

| Column | Meaning | Source, year |
|---|---|---|
| waec_pass_rate | % of school candidates with 5 credits incl. English and Maths, pooled and candidate-weighted | NBS WAEC 2016-2018 (Taraba 2016-2017) |
| rate_2016, rate_2017, rate_2018 | Same, by year | NBS WAEC |
| sat, years | Candidates pooled; years used | NBS WAEC |
| waec_resource_expected, lower, upper | Leave-one-state-out prediction from UBEC 2018 resources and a 90% interval. Shown for transparency only: the model does not beat the national mean | derived |
| oos_primary | Primary out-of-school rate (%) | UNICEF/NBS MICS6 2021 |
| reading, numeracy | % of children 7-14 with foundational reading / numeracy skills | MICS6 2021 |
| need_score_state | Learner-weighted mean need score of the state's ranked LGAs | derived, 2024 |
| ltr_ranked_lgas | Learners per teacher across the state's ranked LGAs | derived, 2024 |
| n_ranked_lgas | Number of the state's LGAs that are ranked | derived |

## Other files

| File | Content |
|---|---|
| lga_boundaries.geojson | Simplified LGA polygons (clockwise rings for Plotly) |
| lga_index_meta.json | Weights, standards, grade counts, PCA check, weight-draw ranges |
| lens2_meta.json | Lens 2 model, LOSO errors, exclusions |
| validation.json | Spearman checks against MICS 2021, UBEC 2018, NMIS 2014 |
| insights_meta.json | National figures for the insight views at the default settings (quoted in the README and write-up) |

## Interim tables (`data/interim/`, not committed)

`waec_state_2016_2018.parquet`, `ubec_state_2018_2020.parquet`, `mics_state_2021.parquet`: extracted tables before modelling, with reconciliation reports in `reports/`.
