# Where Should the Next Teacher Go?

**YDP Community Datathon 2026 · Education track · Solo entry** · App: [LIVE_APP_URL] · Repo: [REPO_URL]

## 1. The problem and why it matters

State Universal Basic Education Boards (SUBEBs) and federal planners decide every year where to post teachers and build classrooms. The data exists but is scattered, and two traps make it hard to use. **First, reporting is uneven.** In the 2024 Annual School Census, 101 of 774 LGAs returned fewer than half their expected school forms, and Rivers, Cross River and Nasarawa are almost blank. A naive ranking rewards LGAs for not reporting. **Second, levels don't match.** WAEC results are published by state, but teachers are posted by LGA. **The gap is large:** two in three ranked LGAs have more than the UBE standard of 35 learners per public-school teacher, and reaching the standard would take about 380,000 more teachers. The 20 neediest LGAs alone serve 1.49 million learners at ratios up to 224:1. These are not only in the far north: three are in Oyo and two in Imo.

[EVIDENCE_BLOCK]

## 2. Approach and data

**Lens 1, measured, LGA level (2024).** For each LGA we take public-school learners per teacher, per usable classroom and per usable toilet from the Federal Ministry of Education's 2024 Annual School Census (DNEMIS). We compare them with the government's own UBE standard (35:1). Each LGA gets a **confidence grade** from its census return rate plus plausibility checks against UNFPA population projections. LGAs under 50% returns or with implausible counts are **not ranked but listed with the reason**: 132 LGAs, treated as a finding (need unknown, not low). Ranked LGAs get a transparent need score: a weighted average of percentiles (teachers 50%, classrooms 35%, toilets 15%). The output is the top 20, nationally or per state, with **teachers and classrooms needed to reach 35:1** and the main driver.

**Checks.** Across 1,000 random alternative weightings, 15 of the top 20 stay in the top 20 at least 80% of the time. The score agrees with a purely statistical summary (PCA, Spearman 0.99). Against independent MICS6 2021 data never used as an input, states with higher need have more children out of school (+0.46) and weaker reading (-0.49) and numeracy (-0.59). The 2024 ratios agree with UBEC 2018 (+0.61) and with the 2014 NMIS school survey (+0.57). 12 of today's top 20 were already in the worst quarter in 2014.

**Lens 2, state context (2016-2018).** We extracted WAEC results for all 37 states from NBS PDFs and reconciled them to the report's national totals (Taraba 2018 excluded as a misprint). WAEC results track MICS reading closely (+0.75). But reported resources (UBEC 2018) **did not predict WAEC results** better than the national average in leave-one-state-out tests. So we label no state as an over- or under-performer, and we rank LGAs on measured gaps, not predicted results.

**Data (all real and public; no synthetic data):** FME DNEMIS Annual School Census 2024 · OCHA boundaries · UNFPA 2020 population projections · NMIS 2014 school survey (CC BY 4.0) · NBS WAEC Results Statistics 2016-2018 · UBEC Digest 2019/2020 · UNICEF/NBS MICS6 2021 (validation only). Every extracted table is reconciled to published totals; mismatches are logged.

**Beyond the ranking (not in the score).** **Moving teachers will not close the gap.** Even if every teacher above 35:1 moved to the neediest LGA in the same state, moves would cover 6% of the 380,212-teacher shortfall; the 20 states where moves fall short hold 98% of it, so hiring is the main route. Higher-need LGAs also tend to have fewer women teachers (Spearman -0.49; under 20% in 95 LGAs), fewer junior secondary learners per primary cohort (-0.61) and smaller private-school shares (-0.57, where private returns allow). 395 of 637 LGAs measured in both 2014 and 2024 have over 20% more learners per teacher.

## 3. What works, what is a placeholder, what next

- **Working:** the full pipeline rebuilds from raw public data in one command (35 tests). The Streamlit app gives a national or per-state top 20, a map, an LGA detail view, CSV downloads, a not-ranked list, a move-or-hire view, a budget planner and the insight views above.
- **Placeholders and limits:** unit costs, budget and the share of teachers who can move are planner inputs, because no public source gives them; public schools only; counts are self-reported; population is a 2006-based projection used only for checks; positions 18-20 are close calls (4 to 7 teachers from leaving the list). The partner-data adapter is tested on a toy table, not yet on real partner data.
- **Next:** pilot with one SUBEB's 2025 census returns through the existing column mapping (no code changes); add subject specialism, official unit costs and school locations.
