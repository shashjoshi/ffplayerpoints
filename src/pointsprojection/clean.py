#Clean nflverse csv into ont player-week modeling table in DuckDB

#Pipeline
#One view per source folder in data/raw/ (reads every seasons csv)
#Structure: SQL in data/sql/, any missing is written, existing are overwritten: clean is source of truth, not the existing SQL
#Table: One row per player in pos groups[QB/RB/WR/TE] per regular season week
#Position Group Filtering: Excludes Defense/ST and Kickers - Only "Significant Scorers": QB/TE/WR/RB
#build() always rebuilds from raw csv

#Imports
import duckdb
import pandas as pd
from .data import RAW_DIR, ROOT_DIR, PROC_DIR

DB_PATH = PROC_DIR / "fantasy.duckdb"
SQL_DIR = ROOT_DIR / "data" / "sql"

#Required data sources for staging (PBP data is excluded as it is not player/week basis and used for feature engineering)
REQ_SOURCES = ["schedules", "injury", "rosters", "playerstats", "snapcounts", "ngs_receiving", "ngs_passing", "ngs_rushing",]

#SQL for each pipeline step
#build() writes from here to data/sql/, overwriting
DEFAULT_SQL = {
    "00_macros.sql":"""
-- Reusable SQL helpers

--Map franchises who moved to current abbreviation
--Raiders, Chargers, Rams all moved, so normalize
CREATE OR REPLACE MACRO norm_team(t) AS
    CASE t
        WHEN 'OAK' THEN 'LV'
        WHEN 'SD' THEN 'LAC'
        WHEN 'STL' THEN 'LA'
        WHEN 'SL' THEN 'LA'
        WHEN 'ARZ' THEN 'ARI'
        WHEN 'BLT' THEN 'BAL'
        WHEN 'CLV' THEN 'CLE'
        WHEN 'HST' THEN 'HOU'
        ELSE t
    END;
""",

    "01_stg_schedules.sql": """
--One row per TEAM per reg season game
--Each game appears twice, once for home, once for away side
--spread_line has positive = HOME favored where team_spread has positive = THIS favored
--Team total implied from half game total plus/minus half spread if favored

CREATE OR REPLACE VIEW stg_team_games AS 
WITH reg AS (
    SELECT *
    FROM raw_schedules
    WHERE game_type = 'REG'
)
SELECT
    game_id,
    season,
    week,
    CAST(gameday AS DATE) AS gameday, 
    gametime, 
    weekday, 
    norm_team(home_team) AS team,
    norm_team(away_team) AS opponent,
    TRUE AS is_home,
    location = 'Neutral' AS is_neutral_site,
    spread_line AS team_spread,
    total_line,
    total_line / 2 + spread_line / 2 AS implied_team_total,
    home_rest AS rest_days,
    div_game = 1 AS is_division_game,
    roof,
    roof IN ('dome', 'closed') AS is_indoor,
    surface,
    temp,
    wind
FROM reg

UNION ALL

SELECT
    game_id,
    season,
    week,
    CAST(gameday AS DATE),
    gametime,
    weekday,
    norm_team(away_team),
    norm_team(home_team),
    FALSE,
    location = 'Neutral',
    -spread_line,
    total_line,
    total_line / 2 - spread_line / 2,
    away_rest,
    div_game = 1,
    roof,
    roof IN ('dome', 'closed'),
    surface,
    temp,
    wind
FROM reg
""",

    "02_stg_injuries.sql":"""
-- One row per player per week: based on FINAL injury rep
-- Player can have several reports in a week, but only base off last

CREATE OR REPLACE VIEW stg_injuries AS
WITH ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY gsis_id, season, week
            ORDER BY date_modified DESC
        ) AS rn
    FROM raw_injury
    WHERE game_type = 'REG'
        AND gsis_id IS NOT NULL
)
SELECT
    gsis_id,
    season,
    week,
    report_status,
    report_primary_injury,
    CASE
        WHEN practice_status ILIKE 'Did Not Participate%' THEN 'DNP'
        WHEN practice_status ILIKE 'Limited%' THEN 'LP'
        WHEN practice_status ILIKE 'Full%' THEN 'FP'
        ELSE NULL
    END AS practice_status
FROM ranked
WHERE rn = 1;
""",

    "03_stg_rosters.sql": """
-- Position players who were rostered: ACT = active, INA = inactive but contracted
-- Excluded: IR as RES, PUP, suspended, practice squad as DEV, cut, etc
-- Elevated practice squad players recovered from player_stats later

CREATE OR REPLACE VIEW stg_rosters AS
SELECT
    gsis_id,
    season,
    week,
    norm_team(team) AS roster_team,
    position AS roster_position,
    full_name,
    status AS roster_status,
    CAST(birth_date AS DATE) AS birth_date,
    years_exp,
    rookie_year,
    draft_number
FROM raw_rosters
WHERE game_type = 'REG'
    AND position IN ('QB', 'RB', 'WR', 'TE')
    AND status IN ('ACT', 'INA')
    AND gsis_id IS NOT NULL;

-- Lookup from GSIS id to PFR id, for joining with snap counts
CREATE OR REPLACE VIEW stg_id_map AS
SELECT
    gsis_id,
    MAX(pfr_id) AS pfr_id
FROM raw_rosters
WHERE gsis_id IS NOT NULL
    AND pfr_id IS NOT NULL
GROUP BY gsis_id;
""",

    "04_stg_player_stats.sql":"""
--Regular season box score and usage by playerweek
--Target side values, shifted by features.py

CREATE OR REPLACE VIEW stg_player_stats AS
SELECT
    player_id AS gsis_id,
    season,
    week,
    norm_team(team) AS stats_team,
    position AS stats_position,
    player_display_name,

    --passing
    completions,
    attempts,
    passing_yards,
    passing_tds,
    passing_interceptions,
    sacks_suffered,
    passing_air_yards,
    passing_2pt_conversions,

    --rushing
    carries,
    rushing_yards,
    rushing_tds,
    rushing_2pt_conversions,

    --receiving
    targets,
    receptions,
    receiving_yards,
    receiving_tds,
    receiving_air_yards,
    receiving_yards_after_catch,
    receiving_2pt_conversions,
    target_share,
    air_yards_share,
    wopr,

    --ball security / misc scoring
    sack_fumbles_lost + rushing_fumbles_lost + receiving_fumbles_lost AS fumbles_lost,
    special_teams_tds,

    --target
    fantasy_points_ppr
FROM raw_playerstats
WHERE season_type = 'REG'
    AND player_id IS NOT NULL;
""",

    "05_stg_ngs.sql":"""
--Next Gen Stats per playerweek, one view per statype
--Drop week 0 season totals row and only keep stuff that doesnt come from player stats

CREATE OR REPLACE VIEW stg_ngs_receiving AS
SELECT
    player_gsis_id AS gsis_id,
    season,
    week,
    avg_cushion AS ngs_rec_avg_cushion,
    avg_separation AS ngs_rec_avg_separation,
    avg_intended_air_yards AS ngs_rec_avg_intended_air_yards,
    percent_share_of_intended_air_yards AS ngs_rec_pct_share_intended_air_yards,
    catch_percentage AS ngs_rec_catch_pct,
    avg_yac AS ngs_rec_avg_yac,
    avg_expected_yac AS ngs_rec_avg_expected_yac,
    avg_yac_above_expectation AS ngs_rec_avg_yac_above_expectation
FROM raw_ngs_receiving
WHERE season_type = 'REG' AND week > 0 AND player_gsis_id IS NOT NULL;

CREATE OR REPLACE VIEW stg_ngs_passing AS
SELECT
    player_gsis_id AS gsis_id,
    season,
    week,
    avg_time_to_throw AS ngs_pass_avg_time_to_throw,
    avg_completed_air_yards AS ngs_pass_avg_completed_air_yards,
    avg_intended_air_yards AS ngs_pass_avg_intended_air_yards,
    avg_air_yards_differential AS ngs_pass_avg_air_yards_differential,
    aggressiveness AS ngs_pass_aggressiveness,
    avg_air_yards_to_sticks AS ngs_pass_avg_air_yards_to_sticks,
    passer_rating AS ngs_pass_passer_rating,
    completion_percentage_above_expectation AS ngs_pass_cpoe
FROM raw_ngs_passing
WHERE season_type = 'REG' AND week > 0 AND player_gsis_id IS NOT NULL;

CREATE OR REPLACE VIEW stg_ngs_rushing AS 
SELECT
    player_gsis_id AS gsis_id,
    season,
    week,
    efficiency AS ngs_rush_efficiency,
    percent_attempts_gte_eight_defenders AS ngs_rush_pct_8plus_defenders,
    avg_time_to_los AS ngs_rush_avg_time_to_los,
    expected_rush_yards AS ngs_rush_expected_yards,
    rush_yards_over_expected AS ngs_rush_yards_over_expected,
    rush_yards_over_expected_per_att AS ngs_rush_yoe_per_att,
    rush_pct_over_expected AS ngs_rush_pct_over_expected
FROM raw_ngs_rushing
WHERE season_type = 'REG' AND week > 0 AND player_gsis_id IS NOT NULL;
""",

    "05_stg_snap_counts.sql": """
-- Offensive snaps per playerweek keyed by PFR id

CREATE OR REPLACE VIEW stg_snap_counts AS
SELECT
    pfr_player_id AS pfr_id,
    season,
    week,
    MAX(offense_snaps) AS offense_snaps,
    MAX(offense_pct) AS offense_pct
FROM raw_snapcounts
WHERE game_type = 'REG'
  AND pfr_player_id IS NOT NULL
GROUP BY pfr_player_id, season, week;

-- Fallback for players with no PFR on roster rows mathed on lowercase name, team, season, week
-- Only unique are kept
CREATE OR REPLACE VIEW stg_snap_counts_by_name AS
SELECT
    LOWER(TRIM(player))          AS name_key,
    norm_team(team)              AS team,
    season,
    week,
    MAX(offense_snaps)           AS offense_snaps,
    MAX(offense_pct)             AS offense_pct
FROM raw_snapcounts
WHERE game_type = 'REG'
GROUP BY ALL
HAVING COUNT(*) = 1;
""",

    "06_player_weeks.sql":"""
--Modeling table: ONe row per player per week
-- Base population = (game-day roster: ACT or INA) UNION (anyone who recorded stats).
-- * Keep act/ina but 0 stats
--Then:
--* INNER joins to schedule dropping bye weeks
-- * LEFT joins injury rep and snap count matched on PFR id and fallback
-- * LEFT joins add ngs; stays null if no ngs above thresh - Null not 0
-- * Drop when out or doubtful, Q stays

CREATE OR REPLACE VIEW int_player_base AS
SELECT
    gsis_id,
    season,
    week,
    COALESCE(s.stats_team, r.roster_team)            AS team,      -- stats team = team actually played for
    COALESCE(r.roster_position, s.stats_position)    AS position,
    COALESCE(r.full_name, s.player_display_name)     AS player_name,
    r.roster_status,
    s.gsis_id IS NOT NULL                            AS has_stats,
    r.birth_date,
    r.years_exp,
    r.rookie_year,
    r.draft_number,
    s.* EXCLUDE (gsis_id, season, week, stats_team, stats_position, player_display_name)
FROM stg_rosters AS r
FULL OUTER JOIN stg_player_stats AS s
    USING (gsis_id, season, week);
 
 
CREATE OR REPLACE TABLE player_weeks AS
SELECT
    -- keys
    b.gsis_id,
    m.pfr_id,
    b.season,
    b.week,
    g.game_id,
 
    -- player
    b.player_name,
    b.position,
    b.team,
    b.roster_status,
    b.has_stats,
    b.birth_date,
    b.years_exp,
    b.rookie_year,
    b.draft_number,
 
    -- game context (known before kickoff)
    g.opponent,
    g.gameday,
    g.gametime,
    g.weekday,
    g.is_home,
    g.is_neutral_site,
    g.team_spread,
    g.total_line,
    g.implied_team_total,
    g.rest_days,
    g.is_division_game,
    g.roof,
    g.is_indoor,
    g.surface,
    g.temp,
    g.wind,
 
    -- injury report (known before kickoff)
    i.report_status,
    i.report_primary_injury,
    i.practice_status,
 
    -- outcomes for THIS week (targets / inputs for later weeks' lag features)
    COALESCE(sn.offense_snaps, snn.offense_snaps, 0) AS offense_snaps,
    COALESCE(sn.offense_pct, snn.offense_pct, 0)     AS offense_pct,
    (sn.pfr_id IS NOT NULL OR snn.name_key IS NOT NULL) AS has_snap_row,
    COALESCE(b.completions, 0)                    AS completions,
    COALESCE(b.attempts, 0)                       AS attempts,
    COALESCE(b.passing_yards, 0)                  AS passing_yards,
    COALESCE(b.passing_tds, 0)                    AS passing_tds,
    COALESCE(b.passing_interceptions, 0)          AS passing_interceptions,
    COALESCE(b.sacks_suffered, 0)                 AS sacks_suffered,
    COALESCE(b.passing_air_yards, 0)              AS passing_air_yards,
    COALESCE(b.passing_2pt_conversions, 0)        AS passing_2pt_conversions,
    COALESCE(b.carries, 0)                        AS carries,
    COALESCE(b.rushing_yards, 0)                  AS rushing_yards,
    COALESCE(b.rushing_tds, 0)                    AS rushing_tds,
    COALESCE(b.rushing_2pt_conversions, 0)        AS rushing_2pt_conversions,
    COALESCE(b.targets, 0)                        AS targets,
    COALESCE(b.receptions, 0)                     AS receptions,
    COALESCE(b.receiving_yards, 0)                AS receiving_yards,
    COALESCE(b.receiving_tds, 0)                  AS receiving_tds,
    COALESCE(b.receiving_air_yards, 0)            AS receiving_air_yards,
    COALESCE(b.receiving_yards_after_catch, 0)    AS receiving_yards_after_catch,
    COALESCE(b.receiving_2pt_conversions, 0)      AS receiving_2pt_conversions,
    COALESCE(b.target_share, 0)                   AS target_share,
    COALESCE(b.air_yards_share, 0)                AS air_yards_share,
    COALESCE(b.wopr, 0)                           AS wopr,
    COALESCE(b.fumbles_lost, 0)                   AS fumbles_lost,
    COALESCE(b.special_teams_tds, 0)              AS special_teams_tds,
    COALESCE(b.fantasy_points_ppr, 0)             AS fantasy_points_ppr,
 
    -- Next Gen Stats (NULL when the player was below NGS volume thresholds)
    nr.gsis_id IS NOT NULL                        AS has_ngs_receiving,
    np.gsis_id IS NOT NULL                        AS has_ngs_passing,
    nu.gsis_id IS NOT NULL                        AS has_ngs_rushing,
    nr.* EXCLUDE (gsis_id, season, week),
    np.* EXCLUDE (gsis_id, season, week),
    nu.* EXCLUDE (gsis_id, season, week)
 
FROM int_player_base AS b
INNER JOIN stg_team_games AS g
    ON  g.season = b.season
    AND g.week   = b.week
    AND g.team   = b.team
LEFT JOIN stg_injuries AS i
    ON  i.gsis_id = b.gsis_id
    AND i.season  = b.season
    AND i.week    = b.week
LEFT JOIN stg_id_map AS m
    ON  m.gsis_id = b.gsis_id
LEFT JOIN stg_snap_counts AS sn
    ON  sn.pfr_id = m.pfr_id
    AND sn.season = b.season
    AND sn.week   = b.week
LEFT JOIN stg_snap_counts_by_name AS snn          -- fallback only when there is no PFR id
    ON  m.pfr_id IS NULL
    AND snn.name_key = LOWER(TRIM(b.player_name))
    AND snn.team     = b.team
    AND snn.season   = b.season
    AND snn.week     = b.week
LEFT JOIN stg_ngs_receiving AS nr
    ON nr.gsis_id = b.gsis_id AND nr.season = b.season AND nr.week = b.week
LEFT JOIN stg_ngs_passing AS np
    ON np.gsis_id = b.gsis_id AND np.season = b.season AND np.week = b.week
LEFT JOIN stg_ngs_rushing AS nu
    ON nu.gsis_id = b.gsis_id AND nu.season = b.season AND nu.week = b.week
WHERE b.position IN ('QB', 'RB', 'WR', 'TE')
  AND COALESCE(i.report_status, '') NOT IN ('Out', 'Doubtful')
ORDER BY b.season, b.week, b.team, b.position, b.player_name;
""",
}


def write_sql_files(overwrite: bool = True) -> list[str]:
    #Write DEFAULT_SQL to data/sql/. With overwrite=true rewrites
    #overwrite=false only missing are written
    #returns the names written
    SQL_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for name, sql in DEFAULT_SQL.items():
        path = SQL_DIR / name
        if overwrite or not path.exists():
            path.write_text(sql.lstrip("\n"))
            written.append(name)
    return written


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH), read_only=read_only)


def build_raw_views(con: duckdb.DuckDBPyConnection) -> list[str]:
    created = []
    for folder in sorted (p for p in RAW_DIR.iterdir() if p.is_dir()):
        if not any(folder.glob("*.csv")):
            continue
        pattern = (folder/"*.csv").as_posix()
        con.execute(f"""
            CREATE OR REPLACE VIEW raw_{folder.name} AS 
            SELECT * FROM read_csv('{pattern}', union_by_name = true, filename = true)
        """)
        created.append(folder.name)

    missing = [i for i in REQ_SOURCES if i not in created]
    if missing:
        raise FileNotFoundError(
            f"No raw CSV for {missing} in {RAW_DIR}. Run download() or check pathing"
        )
    return created


def run_sql_files(con: duckdb.DuckDBPyConnection) -> list[str]:
    #Run every .sql in data/sql/ and warn for file not in DEFAULT_SQL
    files = sorted(SQL_DIR.glob("*.sql"))
    extras = [f.name for f in files if f.name not in DEFAULT_SQL]
    if extras:
        print(f"WARNING: running SQL files not defind in clean.py: {extras}. Consider deletion for stale files")
    for f in files:
        con.execute(f.read_text())
    return [f.name for f in files]


def run_checks(con: duckdb.DuckDBPyConnection) -> dict:
    #data quality checks on player weeks. Hard failures raise; rest are reported
    q = lambda sql: con.execute(sql).fetchone()[0]

    dupes = q("""
        SELECT COUNT(*) FROM (
            SELECT gsis_id, season, week FROM player_weeks
            GROUP BY ALL HAVING COUNT(*) > 1
        )
    """)
    if dupes:
        raise ValueError(f"player weeks has {dupes} duplicate (gsis_id, season, week) keys")

    null_keys = q("""
        SELECT COUNT(*) FROM player_weeks
        WHERE gsis_id IS NULL OR team IS NULL OR opponent IS NULL OR game_id IS NULL
    """)
    if null_keys:
        raise ValueError(f"playerweeks has {null_keys} rows with null key columns")

    total = q("SELECT COUNT(*) FROM player_weeks")
    return {
        "rows": total,
        "rows_by_season": dict(con.execute(
            "SELECT season, COUNT(*) FROM player_weeks GROUP BY season ORDER BY season"
        ).fetchall()),
        #Bye weeks (and any team-code mismatch) are dropped by the schedule join.
        #A large number here beyond ~1/17 of base rows means team codes don't line up.
        "base_rows_without_game": q("""
            SELECT COUNT(*) FROM int_player_base b
            WHERE b.position IN ('QB','RB','WR','TE')
              AND NOT EXISTS (SELECT 1 FROM stg_team_games g
                              WHERE g.season = b.season AND g.week = b.week AND g.team = b.team)
        """),
        "pct_with_stats": q("SELECT AVG(has_stats::INT) FROM player_weeks"),
        "pct_with_injury_report": q("SELECT AVG((report_status IS NOT NULL)::INT) FROM player_weeks"),
        #Snap counts join via PFR id; of players who recorded stats, how many found snaps.
        "pct_stats_rows_with_snaps": q(
            "SELECT AVG(has_snap_row::INT) FROM player_weeks WHERE has_stats"
        ),
        "null_spread": q("SELECT COUNT(*) FROM player_weeks WHERE team_spread IS NULL"),
        #NGS coverage among players with real volume (5+ targets / 10+ attempts / 10+ carries)
        "pct_ngs_receiving_5plus_targets": q(
            "SELECT AVG(has_ngs_receiving::INT) FROM player_weeks WHERE targets >= 5 AND season >= 2016"
        ),
        "pct_ngs_passing_10plus_attempts": q(
            "SELECT AVG(has_ngs_passing::INT) FROM player_weeks WHERE attempts >= 10 AND season >= 2016"
        ),
        "pct_ngs_rushing_10plus_carries": q(
            "SELECT AVG(has_ngs_rushing::INT) FROM player_weeks WHERE carries >= 10 AND season >= 2016"
        ),
    }

def build(verbose: bool = True, overwrite_sql: bool = True) -> dict:
    #Rebuild from raw csv and return check results
    #Check overwrite conditions
    con = connect()
    try:
        written = write_sql_files(overwrite=overwrite_sql)
        sources = build_raw_views(con)
        files = run_sql_files(con)
        checks = run_checks(con)
    finally:
        con.close()

    if verbose:
        if not overwrite_sql and written:
            print(f"Wrote missing SQL files: {written}")
        elif not overwrite_sql:
            print("Using existing SQL files in data/sql/ (not overwritten)")
        print(f"Raw views: {sources}")
        print(f"SQL files: {files}")
        for k, v in checks.items():
            print(f"{k}: {round(v, 3) if isinstance(v, float) else v}")
    return checks

def load_player_weeks(seasons: list[int] | None = None) -> pd.DataFrame:
    #Read to pandas
    con = connect(read_only = True)
    try:
        if seasons is None:
            return con.execute("SELECT * FROM player_weeks").df()
        return con.execute(
            "SELECT * FROM player_weeks WHERE season IN (SELECT UNNEST(?))", [seasons]
        ).df()
    finally:
        con.close()