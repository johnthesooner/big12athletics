# big12athletics

Big 12 conference championship history, extended with an analysis of the
University of Oklahoma's performance since joining the SEC (July 2024).

**Start with [`reports/OU_SEC_Performance.md`](reports/OU_SEC_Performance.md)** for the findings.

## Layout

| Path | What |
|---|---|
| `big12_scrape.py` | Scrapes every "titles by season" table from Wikipedia's Big 12 champions list |
| `sec_scrape.py` | Same scraper pointed at the SEC champions list (writes `SEC Championships by Season/`). Not yet run against the live page |
| `Championships by Season/` | Scraped Big 12 champions, one CSV per sport (seasons through 2022-23) |
| `oklahoma_sec/ou_sec_results.csv` | Curated OU SEC-era results by sport and season, each row with a source URL and confidence tag |
| `oklahoma_sec/directors_cup.csv` | Learfield Directors' Cup ranks for OU (and Oklahoma State as a Big 12 control) |
| `ou_analysis.py` | Validates inputs, builds the Big 12 baseline, compares it to SEC-era results, writes tables and charts |
| `reports/` | Generated tables and charts, plus the written report |
| `tests/` | Unit, validation, scraper (offline) and report-sync tests |

## Usage

```bash
pip install -r requirements.txt
python ou_analysis.py        # regenerates reports/*.csv and reports/*.png
python -m pytest             # run all tests
python big12_scrape.py       # optional: needs network access to Wikipedia
python sec_scrape.py         # optional: needs network access to Wikipedia
```

`ou_analysis.py` exits with status 1 and lists every problem if any input
fails validation. It writes nothing in that case.

## Curated data rules (`oklahoma_sec/ou_sec_results.csv`)

| Column | Allowed values |
|---|---|
| `academic_year` | `YYYY-YY`, 2024-25 or later |
| `sport` | Football, Baseball, Softball, Men's/Women's Basketball, Women's Soccer, Volleyball, Women's Gymnastics |
| `reg_season_title`, `tourney_title` | `Y`, `N`, `shared`, `-` (event not held that year), blank (unknown) |
| `conf_wins`, `conf_losses`, `conf_ties` | Non-negative integers. Wins and losses must both be set or both be blank |
| `national_title` | `Y` or `N` |
| `confidence` | `high`, `medium`, `low`, `missing` |
| `source` | `https://` URL (required unless confidence is `missing`) |

**Unknown is not the same as "did not win".** Blank title flags are reported as
unknown outcomes, and the statistical check gives p-values both with and without them.

## Adding a season

1. Append one row per sport to `oklahoma_sec/ou_sec_results.csv`, and the Directors' Cup rank to `directors_cup.csv`.
2. Run `python ou_analysis.py` and commit the regenerated `reports/` files.
3. Update any figures quoted in `reports/OU_SEC_Performance.md`. `tests/test_reports_in_sync.py` fails until the key figures match.

CI (`.github/workflows/ci.yml`) runs the tests on Python 3.12 and 3.13 and fails if the committed report tables are stale.
