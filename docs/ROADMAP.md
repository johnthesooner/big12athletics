# Roadmap

Ranked by how much each item would raise the project's credibility. Items marked **(network)** need a machine that can reach Wikipedia or official athletics sites; this project's build environment could not.

## 1. Model standings, not titles (highest value) (network)

Titles are a sparse yes/no outcome: OU has about 12 chances a year and wins 2–4. Final conference standings turn every sport-season into a continuous outcome, **finish percentile** = (N − rank) / (N − 1). That has far more statistical power, enough to detect a real change in three or four seasons instead of six or more.

- Scrape final standings per sport for the Big 12 (2014-15 onward) and the SEC (2024-25 onward).
- Model: `percentile ~ school × era + sport` (fixed effects), with standard errors clustered by sport. OU vs Texas is the interaction term.
- This also fixes conference-size bias. Finishing 4th of 16 and 4th of 10 are different results, and percentile accounts for that.

## 2. Run the SEC scraper and reconcile (network)

`ou-sec scrape sec` writes `data/raw/sec_champions/`. Then:

- Diff the scraped titles against `sec_results.csv` and resolve every mismatch.
- Upgrade confirmed rows to `high` confidence.
- Fill the two unknown women's soccer tournament outcomes and OU's missing 2022-23 Directors' Cup rank.

## 3. Fix shared-title undercounting in the Big 12 scrape (network)

The scrape lists one name for some co-championships (for example, 1996 softball's regular season, likely shared with Oklahoma State). Re-scrape with the improved parser, which now counts skipped rows, and add the missing co-champions as supplement rows with sources.

## 4. Widen the control group

- Add Oklahoma State (stayed in the Big 12) as a second control: did *it* change after OU and Texas left?
- Add earlier movers (Texas A&M and Missouri, 2012) for an event-study: how did their title rates evolve in SEC years 1–10? That shows whether a dip in the first two years usually recovers.

## 5. Revenue-sport depth

Conference titles barely register in football and men's basketball. Add SP+/FPI (football) and NET/KenPom (basketball) by season for a measure of team strength that does not depend on the league.

## 6. Productization

- Turn on GitHub Pages: Settings → Pages → deploy from branch, folder `/docs`. The site is already committed and kept current by CI.
- Add a scheduled CI job each June, after the Directors' Cup final, that runs `ou-sec validate` and opens an issue listing the rows needed for the new season.
- Choose and add a license (the repo has none yet). This is the owner's decision.
- Optional: publish the package (`pip install ou-sec`) and add a `CHANGELOG.md`.

## Done

- [x] Package and CLI (`ou-sec validate | report | site | scrape | all`)
- [x] Validation that lists every problem; unknown outcomes kept separate from losses
- [x] Backfill 2023-24 Big 12 season; settle the 1996 softball question
- [x] Texas control group and exact conditional test
- [x] Story page generated from data, with tests that fail if it is stale
