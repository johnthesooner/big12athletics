# big12athletics

Big 12 conference championship history, extended with an analysis of the
University of Oklahoma's performance since joining the SEC (July 2024).

## Layout

| Path | What |
|---|---|
| `big12_scrape.py` | Scrapes every "titles by season" table from Wikipedia's Big 12 champions list |
| `sec_scrape.py` | Same scraper pointed at the SEC champions list (writes `SEC Championships by Season/`) |
| `Championships by Season/` | Scraped Big 12 champions, one CSV per sport (seasons through 2022-23) |
| `oklahoma_sec/ou_sec_results.csv` | Curated OU SEC-era results by sport and season, each row with a source URL and confidence tag |
| `oklahoma_sec/directors_cup.csv` | Learfield Directors' Cup ranks for OU (and Oklahoma State as a Big 12 control) |
| `ou_analysis.py` | Builds the Big 12 baseline, compares it to SEC-era results, writes tables and charts |
| `reports/OU_SEC_Performance.md` | Findings, statistical check, limitations, next steps |
| `tests/` | Unit tests for parsing, title counting and data validation |

## Usage

```bash
pip install requests beautifulsoup4 pandas matplotlib pytest
python ou_analysis.py        # regenerates reports/*.csv and reports/*.png
python -m pytest tests       # run the tests
python sec_scrape.py         # optional: needs network access to Wikipedia
```
