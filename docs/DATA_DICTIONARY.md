# Data dictionary

All inputs live in `data/`. **Raw** files are produced by a scraper and never edited by hand. **Curated** files are maintained by hand and validated on every run. Validation rules are enforced in `src/ou_sec/data.py`. A bad edit stops the pipeline and lists every problem.

## `data/raw/big12_champions/<Sport>_titles_by_season.csv`

One file per sport, scraped from Wikipedia's *List of Big 12 Conference champions*.

| Column | Meaning |
|---|---|
| `Season` | 4-digit year. Spring and winter sports use the spring year (2023 = 2022-23). Fall sports (volleyball, soccer, cross country) use the fall year (2022 = 2022-23) |
| title columns | `Regular Season`, `Tournament`, `Champion`, `Indoor Champion`, `Outdoor Champion` (capitalization is normalized on load) |

Cell conventions: `†` = shared title (only one co-champion is named), `—` = no title awarded, `[a]` = footnote (stripped).

## `data/curated/big12_supplement.csv`

Big 12 seasons missing from the scrape (currently OU's final year, 2023-24). It may only fill gaps, never override scraped rows.

| Column | Type | Rules |
|---|---|---|
| `sport` | text | Must match a scraped sport |
| `season_label` | 4-digit year | Same convention as `Season` above |
| `column` | text | Must be a title column that sport has |
| `champion` | text | `—` if none; co-champions separated by `; ` (each is credited) |
| `shared` | Y/N | Must be Y when more than one champion is listed |
| `confidence` | high/medium/low | high = 2+ agreeing sources |
| `source_url` | https URL | Required |
| `notes` | text | Scores, conflicts, caveats |

## `data/curated/sec_results.csv`

One row per school, sport and SEC season.

| Column | Type | Rules |
|---|---|---|
| `school` | text | Required (`Oklahoma`, `Texas`) |
| `academic_year` | `YYYY-YY` | 2024-25 or later; consecutive years |
| `sport` | text | Football, Baseball, Softball, Men's/Women's Basketball, Women's Soccer, Volleyball, Women's Gymnastics |
| `conf_wins`, `conf_losses`, `conf_ties` | int ≥ 0 | Wins and losses both set or both blank |
| `conf_finish` | text | Place or seed as reported |
| `reg_season_title`, `tourney_title` | flag | `Y`, `N`, `shared`, `-` (event not held), blank (**unknown**) |
| `ncaa_result` | text | Postseason result |
| `national_title` | Y/N | |
| `confidence` | high/medium/low/missing | |
| `source` | https URL | Required unless confidence is `missing` |
| `notes` | text | Overall record, conflicts, caveats |

The SEC awards no football regular-season title, so football rows use `N` there even when a team finished first.

## `data/curated/directors_cup.csv`

| Column | Type | Rules |
|---|---|---|
| `academic_year` | `YYYY-YY` | |
| `school` | text | |
| `conference` | text | Conference that season |
| `rank` | int ≥ 1 | Blank only when confidence is `missing` |
| `confidence`, `source` | | As above |

## Generated outputs (`reports/`)

| File | Contents |
|---|---|
| `title_rate_tests.csv` | Poisson check per school and baseline |
| `peer_comparison.csv` | Titles per year: full Big 12, recent Big 12, SEC, change |
| `peer_tests.csv` | OU vs Texas exact conditional test |
| `ou_big12_comparable_titles_per_year.csv` / `ou_sec_comparable_titles_per_year.csv` | OU's yearly series (SEC includes unknown counts) |
| `ou_big12_titles_by_sport.csv`, `big12_title_share_by_school.csv` | Big 12 history |
| `sec_titles_by_school.csv`, `sec_conference_win_pct.csv`, `national_titles.csv` | SEC-era detail (ties count as half a win) |
| `*.png` | Static charts for the written report |
