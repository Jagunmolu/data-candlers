-- Wazobia Teachers database schema (SQLite).
--
-- Built from data/processed by `python scripts/build_db.py` into
-- data/processed/wazobia.sqlite. The apps still read the parquet and JSON files;
-- this database is the data model for a pilot: several census years, saved
-- planner scenarios and a record of actual postings.
--
-- Layers:
--   reference    data_sources, states, lgas
--   facts        lga_census, lga_population, lga_facilities, state_outcomes
--   assessment   index_runs, lga_assessment, lga_not_ranked_reasons, lga_insights, state_assessment
--   planning     scenarios, scenario_lga_results, postings
--
-- Keys are OCHA COD-AB P-codes. Every fact row names its source and year.
-- Every assessment row belongs to one index run, so rankings from different
-- census years or settings can sit side by side without overwriting each other.

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------------ reference

CREATE TABLE data_sources (
    source_id   TEXT PRIMARY KEY,                 -- short key, e.g. 'dnemis_asc'
    name        TEXT NOT NULL,
    publisher   TEXT NOT NULL,
    unit        TEXT NOT NULL CHECK (unit IN ('LGA', 'State', 'School', 'Zone')),
    vintage     TEXT NOT NULL,                    -- e.g. '2024', '2016-2018'
    licence     TEXT,
    url         TEXT,
    role        TEXT NOT NULL                     -- how the project uses it
);

CREATE TABLE states (
    adm1_pcode  TEXT PRIMARY KEY CHECK (adm1_pcode GLOB 'NG[0-9][0-9][0-9]'),
    adm1_name   TEXT NOT NULL UNIQUE
);

CREATE TABLE lgas (
    adm2_pcode  TEXT PRIMARY KEY CHECK (adm2_pcode GLOB 'NG[0-9][0-9][0-9][0-9][0-9][0-9]'),
    adm2_name   TEXT NOT NULL,
    adm1_pcode  TEXT NOT NULL REFERENCES states (adm1_pcode),
    area_sqkm   REAL CHECK (area_sqkm > 0),
    center_lat  REAL CHECK (center_lat BETWEEN 4 AND 14),
    center_lon  REAL CHECK (center_lon BETWEEN 2 AND 15),
    UNIQUE (adm1_pcode, adm2_name)
);
CREATE INDEX lgas_state ON lgas (adm1_pcode);

-- How each source spelled the LGA and how the name was matched to the P-code.
CREATE TABLE lga_source_names (
    adm2_pcode   TEXT NOT NULL REFERENCES lgas (adm2_pcode),
    source_id    TEXT NOT NULL REFERENCES data_sources (source_id),
    source_key   TEXT,                            -- the source's own id, e.g. DNEMIS org unit
    source_name  TEXT NOT NULL,
    match_method TEXT NOT NULL,                   -- exact, alias, fuzzy:<name>
    PRIMARY KEY (adm2_pcode, source_id)
);

-- ------------------------------------------------------------------ facts

-- School census counts, public schools, one row per LGA, year and source.
-- 2024 rows come from the DNEMIS Annual School Census; 2014 rows from the NMIS
-- survey (learners, teachers and schools only). A SUBEB's own returns would add
-- rows with their own source_id and year.
CREATE TABLE lga_census (
    adm2_pcode               TEXT NOT NULL REFERENCES lgas (adm2_pcode),
    year                     INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 2100),
    source_id                TEXT NOT NULL REFERENCES data_sources (source_id),
    learners                 REAL CHECK (learners >= 0),
    teachers                 REAL CHECK (teachers >= 0),
    classrooms               REAL CHECK (classrooms >= 0),     -- usable
    toilets                  REAL CHECK (toilets >= 0),        -- usable
    schools                  REAL CHECK (schools >= 0),
    pp_reports_actual        REAL CHECK (pp_reports_actual >= 0),
    pp_reports_expected      REAL CHECK (pp_reports_expected >= 0),
    jss_reports_actual       REAL CHECK (jss_reports_actual >= 0),
    jss_reports_expected     REAL CHECK (jss_reports_expected >= 0),
    pry_learners             REAL CHECK (pry_learners >= 0),
    jss_learners             REAL CHECK (jss_learners >= 0),
    girls                    REAL CHECK (girls >= 0),
    female_teachers          REAL CHECK (female_teachers >= 0),
    special_needs_pry        REAL CHECK (special_needs_pry >= 0),
    iqte_schools             REAL CHECK (iqte_schools >= 0),
    private_learners         REAL CHECK (private_learners >= 0),
    private_reports_actual   REAL CHECK (private_reports_actual >= 0),
    private_reports_expected REAL CHECK (private_reports_expected >= 0),
    -- Published for public and private schools together only.
    pry_learners_all         REAL CHECK (pry_learners_all >= 0),
    pry_dropouts_all         REAL CHECK (pry_dropouts_all >= 0),
    pry_orphans_all          REAL CHECK (pry_orphans_all >= 0),
    learners_all             REAL CHECK (learners_all >= 0),
    computers_all            REAL CHECK (computers_all >= 0),
    non_teaching_staff_all   REAL CHECK (non_teaching_staff_all >= 0),
    PRIMARY KEY (adm2_pcode, year, source_id)
);
CREATE INDEX lga_census_year ON lga_census (year, source_id);

CREATE TABLE lga_population (
    adm2_pcode  TEXT NOT NULL REFERENCES lgas (adm2_pcode),
    year        INTEGER NOT NULL,
    source_id   TEXT NOT NULL REFERENCES data_sources (source_id),
    pop_total   REAL CHECK (pop_total >= 0),
    pop_5_14    REAL CHECK (pop_5_14 >= 0),
    is_projection INTEGER NOT NULL CHECK (is_projection IN (0, 1)),
    PRIMARY KEY (adm2_pcode, year, source_id)
);

-- Share of public schools with each facility (NMIS 2014).
CREATE TABLE lga_facilities (
    adm2_pcode           TEXT NOT NULL REFERENCES lgas (adm2_pcode),
    year                 INTEGER NOT NULL,
    source_id            TEXT NOT NULL REFERENCES data_sources (source_id),
    share_water          REAL CHECK (share_water BETWEEN 0 AND 1),
    share_sanitation     REAL CHECK (share_sanitation BETWEEN 0 AND 1),
    share_power          REAL CHECK (share_power BETWEEN 0 AND 1),
    PRIMARY KEY (adm2_pcode, year, source_id)
);

-- State-level outcomes in long form: WAEC by year and pooled, MICS6 2021.
-- State only: none of these may be joined to an LGA as if it were an LGA outcome.
CREATE TABLE state_outcomes (
    adm1_pcode  TEXT NOT NULL REFERENCES states (adm1_pcode),
    source_id   TEXT NOT NULL REFERENCES data_sources (source_id),
    period      TEXT NOT NULL,                    -- '2016', '2016-2018', '2021'
    measure     TEXT NOT NULL,                    -- e.g. 'waec_5credits_eng_maths_pct'
    value       REAL NOT NULL,
    unit        TEXT NOT NULL,                    -- 'percent', 'candidates'
    PRIMARY KEY (adm1_pcode, source_id, period, measure)
);

-- ------------------------------------------------------------------ assessment

-- One row per build of the ranking: which census year and settings produced it.
CREATE TABLE index_runs (
    run_id            INTEGER PRIMARY KEY,
    census_year       INTEGER NOT NULL,
    census_source_id  TEXT NOT NULL REFERENCES data_sources (source_id),
    vintage_label     TEXT NOT NULL,
    std_learners_per_teacher   REAL NOT NULL,
    std_learners_per_classroom REAL NOT NULL,
    std_learners_per_toilet    REAL NOT NULL,
    w_teacher         REAL NOT NULL,
    w_classroom       REAL NOT NULL,
    w_toilet          REAL NOT NULL,
    top_n             INTEGER NOT NULL,
    settings_yaml     TEXT NOT NULL,              -- full config/settings.yaml used
    meta_json         TEXT NOT NULL,              -- lga_index_meta.json (PCA, grade counts, draws)
    validation_json   TEXT,                       -- validation.json
    git_commit        TEXT,
    built_at          TEXT NOT NULL,              -- ISO 8601 UTC
    CHECK (abs(w_teacher + w_classroom + w_toilet - 1) < 1e-9)
);

-- Grades, ratios, score, rank and gaps for each LGA in a run.
CREATE TABLE lga_assessment (
    run_id             INTEGER NOT NULL REFERENCES index_runs (run_id) ON DELETE CASCADE,
    adm2_pcode         TEXT NOT NULL REFERENCES lgas (adm2_pcode),
    confidence         TEXT NOT NULL CHECK (confidence IN ('A', 'B', 'C', 'Not ranked')),
    caveat             TEXT,                      -- ranked but verify; cost one grade
    reporting_rate     REAL CHECK (reporting_rate BETWEEN 0 AND 1),
    coverage           REAL CHECK (coverage >= 0),
    ltr                REAL CHECK (ltr >= 0),     -- learners per teacher
    lcr                REAL CHECK (lcr >= 0),     -- learners per usable classroom
    ltor               REAL CHECK (ltor >= 0),    -- learners per usable toilet
    toilet_data_ok     INTEGER NOT NULL CHECK (toilet_data_ok IN (0, 1)),
    teachers_needed    REAL CHECK (teachers_needed >= 0),
    classrooms_needed  REAL CHECK (classrooms_needed >= 0),
    need_score         REAL CHECK (need_score BETWEEN 0 AND 100),
    rank               INTEGER CHECK (rank >= 1),
    main_driver        TEXT CHECK (main_driver IN ('Teacher shortage', 'Classroom shortage')),
    pct_teacher        REAL CHECK (pct_teacher BETWEEN 0 AND 1),
    pct_classroom      REAL CHECK (pct_classroom BETWEEN 0 AND 1),
    pct_toilet         REAL CHECK (pct_toilet BETWEEN 0 AND 1),
    top20_share        REAL CHECK (top20_share BETWEEN 0 AND 1),
    persistent_top20   INTEGER CHECK (persistent_top20 IN (0, 1)),
    teachers_to_exit_top20 REAL CHECK (teachers_to_exit_top20 >= 0),
    persistent_shortage    INTEGER CHECK (persistent_shortage IN (0, 1)),
    hidden_demand_flag     INTEGER CHECK (hidden_demand_flag IN (0, 1)),
    PRIMARY KEY (run_id, adm2_pcode),
    UNIQUE (run_id, rank),
    -- Ranked rows have a score and rank; not-ranked rows have neither.
    CHECK ((confidence = 'Not ranked') = (rank IS NULL)),
    CHECK ((confidence = 'Not ranked') = (need_score IS NULL))
);
CREATE INDEX lga_assessment_rank ON lga_assessment (run_id, rank);

-- Why an LGA is not ranked: one row per reason (an LGA can have several).
CREATE TABLE lga_not_ranked_reasons (
    run_id      INTEGER NOT NULL REFERENCES index_runs (run_id) ON DELETE CASCADE,
    adm2_pcode  TEXT NOT NULL REFERENCES lgas (adm2_pcode),
    seq         INTEGER NOT NULL CHECK (seq >= 1),
    reason      TEXT NOT NULL CHECK (length(reason) > 0),
    PRIMARY KEY (run_id, adm2_pcode, seq),
    FOREIGN KEY (run_id, adm2_pcode) REFERENCES lga_assessment (run_id, adm2_pcode) ON DELETE CASCADE
);

-- Views beyond the ranking (not part of the score), at the run's default settings.
CREATE TABLE lga_insights (
    run_id                 INTEGER NOT NULL REFERENCES index_runs (run_id) ON DELETE CASCADE,
    adm2_pcode             TEXT NOT NULL REFERENCES lgas (adm2_pcode),
    teachers_spare         REAL CHECK (teachers_spare >= 0),
    teachers_moved_in      REAL CHECK (teachers_moved_in >= 0),
    teachers_to_hire       REAL CHECK (teachers_to_hire >= 0),
    female_teacher_share   REAL CHECK (female_teacher_share BETWEEN 0 AND 1),
    girls_share            REAL CHECK (girls_share BETWEEN 0 AND 1),
    jss_reporting_rate     REAL CHECK (jss_reporting_rate BETWEEN 0 AND 1),
    jss_per_primary_cohort REAL CHECK (jss_per_primary_cohort >= 0),
    jss_places_gap         REAL CHECK (jss_places_gap >= 0),
    private_reporting_rate REAL CHECK (private_reporting_rate BETWEEN 0 AND 1),
    private_share          REAL CHECK (private_share BETWEEN 0 AND 1),
    ltr_change_since_2014  REAL,
    trend_since_2014       TEXT CHECK (trend_since_2014 IN ('Worse', 'Similar', 'Better')),
    special_needs_share_pry      REAL CHECK (special_needs_share_pry >= 0),
    dropout_rate_pry_all         REAL CHECK (dropout_rate_pry_all >= 0),
    orphan_share_pry_all         REAL CHECK (orphan_share_pry_all >= 0),
    learners_per_computer_all    REAL CHECK (learners_per_computer_all >= 0),
    learners_per_non_teaching_staff_all REAL CHECK (learners_per_non_teaching_staff_all >= 0),
    PRIMARY KEY (run_id, adm2_pcode),
    FOREIGN KEY (run_id, adm2_pcode) REFERENCES lga_assessment (run_id, adm2_pcode) ON DELETE CASCADE
);

-- State aggregates of the LGA ranking (ranked LGAs only, learner-weighted).
CREATE TABLE state_assessment (
    run_id            INTEGER NOT NULL REFERENCES index_runs (run_id) ON DELETE CASCADE,
    adm1_pcode        TEXT NOT NULL REFERENCES states (adm1_pcode),
    need_score_state  REAL CHECK (need_score_state BETWEEN 0 AND 100),
    ltr_ranked_lgas   REAL CHECK (ltr_ranked_lgas > 0),
    n_ranked_lgas     INTEGER NOT NULL CHECK (n_ranked_lgas >= 0),
    PRIMARY KEY (run_id, adm1_pcode)
);

-- ------------------------------------------------------------------ planning

-- A saved planner scenario: the inputs a planner chose (no dataset holds them).
CREATE TABLE scenarios (
    scenario_id     INTEGER PRIMARY KEY,
    run_id          INTEGER NOT NULL REFERENCES index_runs (run_id),
    kind            TEXT NOT NULL CHECK (kind IN ('move', 'budget')),
    name            TEXT NOT NULL,
    scope_state     TEXT REFERENCES states (adm1_pcode),     -- NULL = all of Nigeria
    grades          TEXT NOT NULL DEFAULT 'A,B,C',
    top_n           INTEGER CHECK (top_n >= 1),              -- budget: LGAs in the pool (NULL = all in scope)
    movable_share   REAL CHECK (movable_share BETWEEN 0 AND 1),
    fund_after_moves INTEGER CHECK (fund_after_moves IN (0, 1)),
    teacher_cost    REAL CHECK (teacher_cost > 0),           -- naira per teacher, planner input
    classroom_cost  REAL CHECK (classroom_cost >= 0),        -- naira per classroom, planner input
    budget          REAL CHECK (budget >= 0),                -- naira, planner input
    is_example      INTEGER NOT NULL DEFAULT 0 CHECK (is_example IN (0, 1)),
    notes           TEXT,
    created_by      TEXT,
    created_at      TEXT NOT NULL,
    CHECK (kind <> 'move' OR movable_share IS NOT NULL),
    CHECK (kind <> 'budget' OR (teacher_cost IS NOT NULL AND budget IS NOT NULL))
);

-- What a scenario gives each LGA.
CREATE TABLE scenario_lga_results (
    scenario_id       INTEGER NOT NULL REFERENCES scenarios (scenario_id) ON DELETE CASCADE,
    adm2_pcode        TEXT NOT NULL REFERENCES lgas (adm2_pcode),
    priority          INTEGER CHECK (priority >= 1),
    moved_in          REAL CHECK (moved_in >= 0),
    moved_out         REAL CHECK (moved_out >= 0),
    to_hire           REAL CHECK (to_hire >= 0),
    teachers_funded   REAL CHECK (teachers_funded >= 0),
    classrooms_funded REAL CHECK (classrooms_funded >= 0),
    cost_funded       REAL CHECK (cost_funded >= 0),
    cost_full_gap     REAL CHECK (cost_full_gap >= 0),
    status            TEXT CHECK (status IN ('Fully funded', 'Partly funded', 'Not reached')),
    PRIMARY KEY (scenario_id, adm2_pcode)
);

-- What actually happened: teachers posted and classrooms built, recorded by a
-- SUBEB during a pilot. Empty until then. Lets the next census be compared with
-- the plan.
CREATE TABLE postings (
    posting_id        INTEGER PRIMARY KEY,
    scenario_id       INTEGER REFERENCES scenarios (scenario_id),
    adm2_pcode        TEXT NOT NULL REFERENCES lgas (adm2_pcode),
    teachers_posted   INTEGER NOT NULL DEFAULT 0 CHECK (teachers_posted >= 0),
    classrooms_built  INTEGER NOT NULL DEFAULT 0 CHECK (classrooms_built >= 0),
    effective_date    TEXT NOT NULL,
    recorded_by       TEXT NOT NULL,
    recorded_at       TEXT NOT NULL,
    note              TEXT
);
CREATE INDEX postings_lga ON postings (adm2_pcode, effective_date);

-- ------------------------------------------------------------------ views

CREATE VIEW v_latest_run AS
SELECT * FROM index_runs ORDER BY census_year DESC, run_id DESC LIMIT 1;

-- The latest ranking with names, as the app's main table shows it.
CREATE VIEW v_lga_latest AS
SELECT a.rank, l.adm2_name AS lga, s.adm1_name AS state, a.confidence, a.caveat,
       a.ltr, a.lcr, a.teachers_needed, a.classrooms_needed, a.need_score, a.main_driver,
       a.top20_share, a.persistent_shortage, l.adm2_pcode, l.adm1_pcode, a.run_id
FROM lga_assessment a
JOIN v_latest_run r ON r.run_id = a.run_id
JOIN lgas l ON l.adm2_pcode = a.adm2_pcode
JOIN states s ON s.adm1_pcode = l.adm1_pcode;

CREATE VIEW v_top20_national AS
SELECT * FROM v_lga_latest WHERE rank <= 20 ORDER BY rank;

-- Not-ranked LGAs with every reason in one line.
CREATE VIEW v_not_ranked_latest AS
SELECT v.lga, v.state, group_concat(n.reason, '; ') AS reasons, v.adm2_pcode
FROM v_lga_latest v
JOIN lga_not_ranked_reasons n ON n.run_id = v.run_id AND n.adm2_pcode = v.adm2_pcode
WHERE v.confidence = 'Not ranked'
GROUP BY v.adm2_pcode
ORDER BY v.state, v.lga;
