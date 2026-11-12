# Database

The schema is `db/schema.sql` (SQLite). `python scripts/build_db.py` loads `data/processed` into `data/processed/wazobia.sqlite` (about 1 MB). The apps still read the parquet and JSON files. The database is the data model for a pilot with a State Universal Basic Education Board (SUBEB): several census years side by side, saved planner scenarios, and a record of what was actually posted. `tests/test_database.py` checks that it holds the same numbers as `data/processed` and `pipeline/insights.py`.

## Tables

| Layer | Table | One row per | Rows now |
|---|---|---|---|
| Reference | `data_sources` | source | 7 |
| | `states` | state (OCHA P-code) | 37 |
| | `lgas` | LGA (OCHA P-code) | 774 |
| | `lga_source_names` | LGA and source: the source's spelling and how it was matched | 1,543 |
| Facts | `lga_census` | LGA, year, source: public-school counts and census returns | 1,543 (774 for 2024, 769 for NMIS 2014) |
| | `lga_population` | LGA, year, source (projection flag) | 773 |
| | `lga_facilities` | LGA, year, source: share of schools with water, sanitation, power | 769 |
| | `state_outcomes` | state, source, period, measure (WAEC, MICS6), long form | 295 |
| Assessment | `index_runs` | build of the ranking: census year, standards, weights, full settings, metadata, git commit | 1 |
| | `lga_assessment` | run and LGA: grade, caveat, ratios, gaps, score, rank, driver, stability | 774 |
| | `lga_not_ranked_reasons` | run, LGA and reason (an LGA can have several) | 180 |
| | `lga_insights` | run and LGA: move or hire, women teachers, JSS, private share, change since 2014, context | 774 |
| | `state_assessment` | run and state: learner-weighted need score | 37 |
| Planning | `scenarios` | saved planner inputs (movable share, unit costs, budget, scope) | 2 examples |
| | `scenario_lga_results` | scenario and LGA: moved in or out, to hire, funded, status | 591 |
| | `postings` | teachers posted or classrooms built, recorded during a pilot | 0 |

```
data_sources ─┬─< lga_census >─┐
              ├─< lga_population, lga_facilities, lga_source_names
              └─< state_outcomes >── states ──< lgas
index_runs ──< lga_assessment ──< lga_not_ranked_reasons
           │                  └── lga_insights
           ├─< state_assessment
           └─< scenarios ──< scenario_lga_results
                         └─< postings >── lgas
```

## Design rules

- **Every fact names its source and year.** A new census year, or a SUBEB's own returns, adds rows; nothing is overwritten.
- **Every assessment belongs to a run.** A run records the census year, standards, weights, the full `settings.yaml` and the git commit, so any ranking can be traced and compared with another.
- **The data rules are constraints**, not conventions:
  - grades are A, B, C or Not ranked;
  - a ranked LGA has a score and a rank, and a not-ranked LGA has neither;
  - gaps, counts and costs cannot be negative;
  - weights must sum to 1;
  - a budget scenario must have its costs.
- **WAEC is state level only.** It lives in `state_outcomes`, keyed by state; no LGA table has a WAEC column, and a test enforces this. Taraba 2018 is absent (excluded as a misprint).
- **Costs are planner inputs.** The two example scenarios use the demo's illustrative costs and are marked `is_example = 1`.

## Views

- `v_latest_run`: the most recent run.
- `v_lga_latest`: the latest ranking with LGA and state names.
- `v_top20_national`: the national top 20.
- `v_not_ranked_latest`: not-ranked LGAs with all their reasons.

## Example queries

```sql
-- Top 20 in one state
SELECT rank, lga, confidence, round(ltr) AS learners_per_teacher, teachers_needed
FROM v_lga_latest WHERE state = 'Kano' AND rank IS NOT NULL ORDER BY rank LIMIT 20;

-- Why LGAs in a state are not ranked
SELECT lga, reasons FROM v_not_ranked_latest WHERE state = 'Benue';

-- 2014 vs 2024 learners per teacher for one LGA
SELECT year, source_id, learners / teachers AS ltr
FROM lga_census JOIN lgas USING (adm2_pcode) WHERE adm2_name = 'Tangaza';
```

## In a pilot

1. Load the SUBEB's census returns as `lga_census` rows with their own `source_id` and year (or through the CSV adapter in `config/settings.yaml`, then rebuild).
2. Each rebuild adds an `index_runs` row with its assessment.
3. Planners save scenarios.
4. The SUBEB records actual postings in `postings`.
5. At the next census, compare the plan, the postings and the new ratios.

Moving the live app onto a hosted database (for example PostgreSQL) needs only the schema's SQLite-specific parts changed (`GLOB` checks, `group_concat`). That move is for when the app gains write features, not before.
