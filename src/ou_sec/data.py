"""Load and validate every input.

Each loader raises ``DataValidationError`` listing *every* problem it finds,
so a bad edit to a curated CSV fails loudly instead of silently dropping data.
"""
import re
from pathlib import Path

import pandas as pd

from . import config as cfg

_FOOTNOTE = re.compile(r'\[[^\]]*\]|[†‡*]')
_ACADEMIC_YEAR = re.compile(r'^(\d{4})-(\d{2})$')


class DataValidationError(ValueError):
    """Raised when an input file fails validation; lists every problem."""

    def __init__(self, source, problems):
        self.problems = problems
        super().__init__(f'{source}: {len(problems)} problem(s)\n  - ' + '\n  - '.join(problems))


# ---------------------------------------------------------------- helpers

def clean_team(value):
    """Strip Wikipedia footnote markers ('Baylor†', '—[a]') from a cell."""
    if pd.isna(value):
        return ''
    return _FOOTNOTE.sub('', str(value)).strip()


def normalize_title_type(column):
    """'Regular season' / 'regular  Season ' -> 'Regular Season'."""
    return ' '.join(word.capitalize() for word in str(column).split())


def sport_from_filename(path):
    """"Men's_Tennis_titles_by_season[18].csv" -> "Men's Tennis"."""
    stem = re.sub(r'\[\d+\]$', '', Path(path).stem)
    return stem.replace('_titles_by_season', '').replace('_', ' ')


def is_academic_year(label):
    """True for consecutive-year labels such as '2024-25'."""
    m = _ACADEMIC_YEAR.match(str(label))
    return bool(m) and (int(m.group(1)) + 1) % 100 == int(m.group(2))


def academic_year(sport, season):
    """Map a Big 12 table season label to an 'YYYY-YY' academic year."""
    end = int(season) + 1 if sport in cfg.FALL_SPORTS else int(season)
    return f'{end - 1}-{str(end)[2:]}'


def year_range(first, last):
    """Every 'YYYY-YY' label from first to last inclusive."""
    start, end = int(first[:4]), int(last[:4])
    return [f'{y}-{str(y + 1)[2:]}' for y in range(start, end + 1)]


def _read_raw(path, columns):
    # keep_default_na=False so a literal '-' or 'N' is never coerced to NaN;
    # empty strings become NA explicitly.
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise DataValidationError(path, [f'missing column(s) {missing}'])
    return df.apply(lambda s: s.str.strip()).replace('', pd.NA)


def _to_int(raw, int_columns):
    df = raw.copy()
    for col in int_columns:
        df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
    return df


# ---------------------------------------------------------------- Big 12

def _load_scraped(directory, problems):
    paths = sorted(Path(directory).glob('*.csv'))
    if not paths:
        raise DataValidationError(directory, ['no CSV files found'])
    frames, seen = [], {}
    for path in paths:
        sport = sport_from_filename(path)
        if sport in seen:
            problems.append(f'{path.name}: duplicate of {seen[sport]} (both map to {sport!r})')
            continue
        seen[sport] = path.name
        df = pd.read_csv(path, dtype=str)
        if 'Season' not in df.columns:
            problems.append(f'{path.name}: missing Season column')
            continue
        bad = df.loc[~df['Season'].fillna('').str.fullmatch(r'\d{4}'), 'Season']
        problems += [f'{path.name}: non-numeric Season {s!r}' for s in bad]
        df = df.drop(bad.index)
        if df['Season'].duplicated().any():
            problems.append(f'{path.name}: duplicated Season rows')

        long = df.melt(id_vars='Season', var_name='title_type', value_name='raw')
        long['title_type'] = long['title_type'].map(normalize_title_type)
        long['champion'] = long['raw'].map(clean_team)
        long['shared'] = long['raw'].fillna('').str.contains('†')
        long['sport'] = sport
        long['origin'] = 'scraped'
        frames.append(long.drop(columns='raw'))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=['Season', 'title_type', 'champion', 'shared', 'sport', 'origin'])


def _load_supplement(path, scraped, problems):
    """Curated Big 12 rows for seasons the scrape is missing (never overrides it).

    Co-champions are listed as 'A; B' and each one is credited with a title,
    which is more complete than the scraped tables (they list one name).
    """
    if path is None or not Path(path).exists():
        return scraped.iloc[0:0]
    raw = _read_raw(path, cfg.SUPPLEMENT_COLUMNS)
    have = set(zip(scraped['sport'], scraped['title_type'], strict=True))
    seasons = set(zip(scraped['sport'], scraped['Season'], strict=True))
    rows = []
    for i, r in raw.iterrows():
        tag = f'{Path(path).name} row {i + 2} ({r["sport"]} {r["season_label"]})'
        column = normalize_title_type(r['column'])
        if (r['sport'], column) not in have:
            problems.append(f'{tag}: unknown sport/column {r["sport"]!r}/{column!r}')
        if not str(r['season_label']).isdigit() or len(str(r['season_label'])) != 4:
            problems.append(f'{tag}: season_label must be a 4-digit year')
        elif (r['sport'], r['season_label']) in seasons:
            problems.append(f'{tag}: season already in scraped data; supplement may only fill gaps')
        if r['confidence'] not in cfg.CONFIDENCE_LEVELS - {'missing'}:
            problems.append(f'{tag}: confidence must be high, medium or low')
        if not str(r['source_url']).startswith('https://'):
            problems.append(f'{tag}: source_url must be https://')
        if r['shared'] not in {'Y', 'N'}:
            problems.append(f'{tag}: shared must be Y or N')
        champions = [c.strip() for c in str(r['champion']).split(';') if c.strip()]
        if r['shared'] == 'N' and len(champions) > 1:
            problems.append(f'{tag}: several champions listed but shared=N')
        for champ in champions:
            rows.append({'Season': r['season_label'], 'title_type': column, 'champion': champ,
                         'shared': r['shared'] == 'Y', 'sport': r['sport'], 'origin': 'supplement'})
    dupes = raw[raw.duplicated(['sport', 'season_label', 'column'], keep=False)]
    problems += [f'{Path(path).name}: duplicate row {s} {y} {c}'
                 for s, y, c in dupes[['sport', 'season_label', 'column']].drop_duplicates().itertuples(index=False)]
    return pd.DataFrame(rows, columns=scraped.columns)


def load_big12_titles(directory=None, supplement=None):
    """Long-format table: one row per (sport, season, title type, champion).

    The curated supplement is applied by default only with the default data
    directory, so a caller pointing at its own tables never gets the repo's
    rows mixed in.
    """
    if directory is None:
        directory = cfg.BIG12_DIR
        supplement = cfg.BIG12_SUPPLEMENT if supplement is None else supplement
    problems = []
    scraped = _load_scraped(directory, problems)
    for sport, columns in cfg.COMPARABLE_TITLES.items():
        missing = set(columns) - set(scraped.loc[scraped['sport'] == sport, 'title_type'])
        if missing:
            problems.append(f'comparable sport {sport!r} missing column(s) {sorted(missing)}')
    extra = _load_supplement(supplement, scraped, problems)
    if problems:
        raise DataValidationError(directory, problems)

    titles = pd.concat([scraped, extra], ignore_index=True)
    titles = titles[~titles['champion'].isin(['', '—'])].copy()
    titles['academic_year'] = [academic_year(s, y) for s, y in zip(titles['sport'], titles['Season'], strict=True)]
    return titles.reset_index(drop=True)


# ---------------------------------------------------------------- SEC

def validate_sec_results(raw):
    """Return a list of problems with the curated SEC results table (string-typed)."""
    df = _to_int(raw, cfg.SEC_INT_COLUMNS)
    problems = []
    for i, r in df.iterrows():
        row = f'row {i + 2} ({r["school"]}, {r["academic_year"]}, {r["sport"]})'
        if pd.isna(r['school']):
            problems.append(f'{row}: school is required')
        if not is_academic_year(r['academic_year']) or r['academic_year'] < cfg.FIRST_SEC_YEAR:
            problems.append(f'{row}: bad academic_year')
        if r['sport'] not in cfg.SEC_SPORTS:
            problems.append(f'{row}: unknown sport (expected one of {sorted(cfg.SEC_SPORTS)})')
        if r['confidence'] not in cfg.CONFIDENCE_LEVELS:
            problems.append(f'{row}: confidence must be one of {sorted(cfg.CONFIDENCE_LEVELS)}')
        for col in ('reg_season_title', 'tourney_title'):
            flag = r[col]
            if pd.notna(flag) and flag.lower() not in cfg.TITLE_FLAGS | cfg.NO_TITLE_FLAGS:
                problems.append(f'{row}: {col}={flag!r} (use Y, N, shared, -, or blank)')
        if pd.notna(r['national_title']) and r['national_title'] not in {'Y', 'N'}:
            problems.append(f'{row}: national_title must be Y or N')
        for col in cfg.SEC_INT_COLUMNS:
            if pd.notna(raw.at[i, col]) and pd.isna(r[col]):
                problems.append(f'{row}: {col}={raw.at[i, col]!r} is not an integer')
            elif pd.notna(r[col]) and r[col] < 0:
                problems.append(f'{row}: {col} is negative')
        if pd.isna(r['conf_wins']) != pd.isna(r['conf_losses']):
            problems.append(f'{row}: conf_wins and conf_losses must both be set or both blank')
        if r['confidence'] != 'missing' and not str(r['source']).startswith('https://'):
            problems.append(f'{row}: sourced rows need an https:// source')
    keys = ['school', 'academic_year', 'sport']
    dupes = df[df.duplicated(keys, keep=False)]
    problems += [f'duplicate row for {s} {y} {sp}' for s, y, sp in
                 dupes[keys].drop_duplicates().itertuples(index=False)]
    return problems


def load_sec_results(path=None):
    path = cfg.SEC_RESULTS if path is None else path
    raw = _read_raw(path, cfg.SEC_COLUMNS)
    problems = validate_sec_results(raw)
    if problems:
        raise DataValidationError(path, problems)
    return _to_int(raw, cfg.SEC_INT_COLUMNS)


def load_directors_cup(path=None):
    path = cfg.DIRECTORS_CUP if path is None else path
    df = _to_int(_read_raw(path, cfg.CUP_COLUMNS), ('rank',))
    problems = []
    for i, r in df.iterrows():
        row = f'row {i + 2} ({r["academic_year"]}, {r["school"]})'
        if not is_academic_year(r['academic_year']):
            problems.append(f'{row}: bad academic_year')
        if r['confidence'] not in cfg.CONFIDENCE_LEVELS:
            problems.append(f'{row}: bad confidence')
        if r['confidence'] != 'missing' and (pd.isna(r['rank']) or r['rank'] < 1):
            problems.append(f'{row}: rank must be a positive integer unless confidence is missing')
    if df.duplicated(['academic_year', 'school']).any():
        problems.append('duplicate (academic_year, school) rows')
    if problems:
        raise DataValidationError(path, problems)
    return df.sort_values(['academic_year', 'school']).reset_index(drop=True)


def load_all():
    """(big12 titles, sec results, directors' cup), all validated."""
    return load_big12_titles(), load_sec_results(), load_directors_cup()
