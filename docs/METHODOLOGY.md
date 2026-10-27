# Methodology

How the analysis decides whether Oklahoma lost ground after moving from the Big 12 to the SEC, and why it is built this way.

## The question, made measurable

"Did OU lose ground?" has three measurable parts:

| Part | Measure | Why |
|---|---|---|
| Conference success | Comparable conference titles per year | The outcome fans and administrators track; available back to 1996 |
| National success | National titles; Learfield Directors' Cup rank | Independent of conference, so unaffected by the switch |
| Attribution | Change relative to Texas | Texas moved the same day; its change estimates the pure "SEC effect" |

## 1. Comparable basket

Raw title counts are not comparable across leagues: sports, title types and league sizes differ. The analysis counts only titles that exist in both leagues, per sport:

| Sport | Big 12 title(s) | SEC equivalent |
|---|---|---|
| Baseball, Softball, M/W Basketball, W Soccer | Regular season, Tournament | Regular season, Tournament |
| Volleyball | Champion (regular season) | Regular season title. The SEC volleyball tournament, relaunched in 2025, is excluded |
| W Gymnastics | Championship meet | SEC Championships meet. The SEC regular-season title is excluded |

- Football is excluded because the scraped Big 12 tables do not include it.
- The basket is per school (Texas has no gymnastics), and each school is compared with its own history in its own basket.
- The mapping is defined once, in `src/ou_sec/config.py` (`COMPARABLE_TITLES`).

## 2. Baselines

- **Full history:** mean titles per year over every full Big 12 year (1996-97 to 2023-24, 28 years).
- **Recent:** the last five Big 12 years (2019-20 to 2023-24). This is the headline baseline because programs change over three decades. It includes the COVID-cancelled spring of 2020, which slightly lowers it.
- Spring 1996 softball was a real Big 12 season, played a year before the other sports. Its titles count toward all-time totals but not the per-year baseline, so a softball-only year cannot distort the average.

## 3. Statistical tests

**Single-school test (Poisson).** Treat the SEC title count as Poisson with mean = baseline rate × SEC years, and report P(X ≤ observed).

**Two-school test (exact conditional).** For Poisson counts X (OU) and Y (Texas), conditional on X + Y = n, X follows Binomial(n, p0), where p0 = E_OU / (E_OU + E_TX) and each E comes from that school's own recent baseline. This tests whether OU fell behind Texas *relative to where each started*. It is the count-data version of a two-group, two-period difference-in-differences.

**Unknown outcomes.** A blank title flag means unknown, never "did not win". Tests are reported twice: as observed, and with every unknown counted as a title, the most favorable case for OU. If both versions agree, the unknowns don't matter.

### Assumptions and how they could fail

| Assumption | Reality | Effect on conclusions |
|---|---|---|
| Titles independent | Titles cluster within sports and seasons | Variance is understated, so p-values are, if anything, too small. The "not significant" conclusion is conservative |
| Constant rate | Programs rise and fall | The recent baseline mitigates this, but a five-year average is still noisy |
| Same conference effect for OU and Texas | The SEC's strength differs by sport, and the baskets differ (7 vs 6 sports) | The comparison is rate against rate, but sport mix still matters |
| Records are correct | SEC rows are curated from search results | Every row has a confidence tag and a source. Medium/low rows are listed in the report |

## 4. Data provenance

| Data | Origin | Validation |
|---|---|---|
| Big 12 champions 1996–2023 | Wikipedia scrape (`ou-sec scrape big12`) | Season format, duplicate sports, required columns. The scraper reports rows it skips |
| Big 12 2023-24 | Curated (`big12_supplement.csv`) | Must fill a gap and never override scraped data; https source and confidence on every row; all co-champions listed |
| SEC results | Curated (`sec_results.csv`) | Allowed flags, integer records, known sports, sources, no duplicates |
| Directors' Cup | Curated (`directors_cup.csv`) | Positive ranks unless explicitly marked missing |

Curation rule: corroborate with two independent sources where possible. Confidence is high with two agreeing sources, medium with one good source, and low when sources conflict or are weak.

## 5. Reproducibility guarantees

- `ou-sec validate` checks every input and lists every problem, not just the first.
- `ou-sec all` regenerates `reports/` and `docs/index.html`.
- CI runs the tests on Python 3.12 and 3.13. Tests fail if a committed table, the story page, or a figure quoted in the written report differs from what the code produces.
