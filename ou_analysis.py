"""University of Oklahoma: Big 12 baseline vs. SEC era.

Combines the scraped Big 12 champions tables (``Championships by Season/``)
with the hand-curated SEC-era results in ``oklahoma_sec/`` and writes
summary tables and charts to ``reports/``.

All inputs are validated before any analysis runs; a malformed row raises
``DataValidationError`` listing every problem found rather than silently
dropping data.

Run:  python ou_analysis.py
"""
import math
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
BIG12_DIR = ROOT / 'Championships by Season'
SEC_RESULTS = ROOT / 'oklahoma_sec' / 'ou_sec_results.csv'
DIRECTORS_CUP = ROOT / 'oklahoma_sec' / 'directors_cup.csv'
REPORTS_DIR = ROOT / 'reports'

SCHOOL = 'Oklahoma'
FIRST_BIG12_YEAR = '1996-97'
FIRST_SEC_YEAR = '2024-25'

# Sports whose Big 12 "Season" label is the fall calendar year (e.g. volleyball
# "2022" = the 2022-23 academic year). All others are labelled by spring year.
FALL_SPORTS = {'Volleyball', "Women's Soccer", "Men's Cross Country", 'Football'}

# Sports OU plays in both conferences, mapping each Big 12 table column to the
# equivalent SEC title field. Gymnastics maps the Big 12 meet champion to the
# SEC Championships meet, not the SEC regular-season title (a concept the
# Big 12 table does not track), so the comparison stays like-for-like.
COMPARABLE_TITLES = {
    'Baseball': {'Regular Season': 'reg_season_title', 'Tournament': 'tourney_title'},
    'Softball': {'Regular Season': 'reg_season_title', 'Tournament': 'tourney_title'},
    "Men's Basketball": {'Regular Season': 'reg_season_title', 'Tournament': 'tourney_title'},
    "Women's Basketball": {'Regular Season': 'reg_season_title', 'Tournament': 'tourney_title'},
    "Women's Soccer": {'Regular Season': 'reg_season_title', 'Tournament': 'tourney_title'},
    'Volleyball': {'Champion': 'reg_season_title'},
    "Women's Gymnastics": {'Champion': 'tourney_title'},
}

SEC_SPORTS = set(COMPARABLE_TITLES) | {'Football'}

# SEC title flags. Blank means unknown; '-' means no such event was held.
TITLE_FLAGS = {'y', 'shared'}
NO_TITLE_FLAGS = {'n', '-'}
CONFIDENCE_LEVELS = {'high', 'medium', 'low', 'missing'}

SEC_COLUMNS = ['academic_year', 'sport', 'conf_wins', 'conf_losses', 'conf_ties', 'conf_finish',
               'reg_season_title', 'tourney_title', 'ncaa_result', 'national_title',
               'confidence', 'source', 'notes']
SEC_INT_COLUMNS = ('conf_wins', 'conf_losses', 'conf_ties')
CUP_COLUMNS = ['academic_year', 'school', 'conference', 'rank', 'confidence', 'source']

_FOOTNOTE = re.compile(r'\[[^\]]*\]|[†‡*]')
_ACADEMIC_YEAR = re.compile(r'^(\d{4})-(\d{2})$')


class DataValidationError(ValueError):
    """Raised when an input file fails validation; lists every problem."""

    def __init__(self, source, problems):
        self.problems = problems
        super().__init__(f'{source}: {len(problems)} problem(s)\n  - ' + '\n  - '.join(problems))


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
    end = int(season) + 1 if sport in FALL_SPORTS else int(season)
    return f'{end - 1}-{str(end)[2:]}'


def year_range(first, last):
    """Every 'YYYY-YY' label from first to last inclusive."""
    start, end = int(first[:4]), int(last[:4])
    return [f'{y}-{str(y + 1)[2:]}' for y in range(start, end + 1)]


# ---------------------------------------------------------------- loading

def load_big12_titles(directory=BIG12_DIR):
    """Long-format table: one row per (sport, season, title type, champion)."""
    paths = sorted(Path(directory).glob('*.csv'))
    if not paths:
        raise DataValidationError(directory, ['no CSV files found'])

    problems, frames, seen = [], [], {}
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
        frames.append(long.drop(columns='raw'))

    titles = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=['Season', 'title_type', 'champion', 'shared', 'sport'])
    for sport, columns in COMPARABLE_TITLES.items():
        missing = set(columns) - set(titles.loc[titles['sport'] == sport, 'title_type'])
        if missing:
            problems.append(f'comparable sport {sport!r} missing column(s) {sorted(missing)}')
    if problems:
        raise DataValidationError(directory, problems)

    titles = titles[~titles['champion'].isin(['', '—'])].copy()
    titles['academic_year'] = [academic_year(s, y) for s, y in zip(titles['sport'], titles['Season'])]
    # The softball table starts at "1996", which maps to a year before the
    # conference's first season (1996-97); drop it rather than guess.
    titles = titles[titles['academic_year'] >= FIRST_BIG12_YEAR]
    return titles.reset_index(drop=True)


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


def validate_sec_results(raw):
    """Return a list of problems with the curated SEC results table (string-typed)."""
    df = _to_int(raw, SEC_INT_COLUMNS)
    problems = []
    for i, r in df.iterrows():
        row = f'row {i + 2} ({r["academic_year"]}, {r["sport"]})'
        if not is_academic_year(r['academic_year']) or r['academic_year'] < FIRST_SEC_YEAR:
            problems.append(f'{row}: bad academic_year')
        if r['sport'] not in SEC_SPORTS:
            problems.append(f'{row}: unknown sport (expected one of {sorted(SEC_SPORTS)})')
        if r['confidence'] not in CONFIDENCE_LEVELS:
            problems.append(f'{row}: confidence must be one of {sorted(CONFIDENCE_LEVELS)}')
        for col in ('reg_season_title', 'tourney_title'):
            flag = r[col]
            if pd.notna(flag) and flag.lower() not in TITLE_FLAGS | NO_TITLE_FLAGS:
                problems.append(f'{row}: {col}={flag!r} (use Y, N, shared, -, or blank)')
        if pd.notna(r['national_title']) and r['national_title'] not in {'Y', 'N'}:
            problems.append(f'{row}: national_title must be Y or N')
        for col in SEC_INT_COLUMNS:
            if pd.notna(raw.at[i, col]) and pd.isna(r[col]):
                problems.append(f'{row}: {col}={raw.at[i, col]!r} is not an integer')
            elif pd.notna(r[col]) and r[col] < 0:
                problems.append(f'{row}: {col} is negative')
        if pd.isna(r['conf_wins']) != pd.isna(r['conf_losses']):
            problems.append(f'{row}: conf_wins and conf_losses must both be set or both blank')
        if r['confidence'] != 'missing' and not str(r['source']).startswith('https://'):
            problems.append(f'{row}: sourced rows need an https:// source')
    dupes = df[df.duplicated(['academic_year', 'sport'], keep=False)]
    problems += [f'duplicate row for {y} {s}' for y, s in
                 dupes[['academic_year', 'sport']].drop_duplicates().itertuples(index=False)]
    return problems


def load_sec_results(path=SEC_RESULTS):
    raw = _read_raw(path, SEC_COLUMNS)
    problems = validate_sec_results(raw)
    if problems:
        raise DataValidationError(path, problems)
    return _to_int(raw, SEC_INT_COLUMNS)


def load_directors_cup(path=DIRECTORS_CUP):
    df = _to_int(_read_raw(path, CUP_COLUMNS), ('rank',))
    problems = []
    for i, r in df.iterrows():
        row = f'row {i + 2} ({r["academic_year"]}, {r["school"]})'
        if not is_academic_year(r['academic_year']):
            problems.append(f'{row}: bad academic_year')
        if r['confidence'] not in CONFIDENCE_LEVELS:
            problems.append(f'{row}: bad confidence')
        if r['confidence'] != 'missing' and (pd.isna(r['rank']) or r['rank'] < 1):
            problems.append(f'{row}: rank must be a positive integer unless confidence is missing')
    if df.duplicated(['academic_year', 'school']).any():
        problems.append('duplicate (academic_year, school) rows')
    if problems:
        raise DataValidationError(path, problems)
    return df.sort_values(['academic_year', 'school']).reset_index(drop=True)


# ---------------------------------------------------------------- analysis

def title_status(flag):
    """True = won (incl. shared), False = did not win or not held, NA = unknown."""
    if pd.isna(flag):
        return pd.NA
    flag = str(flag).strip().lower()
    if flag in TITLE_FLAGS:
        return True
    if flag in NO_TITLE_FLAGS:
        return False
    return pd.NA


def is_title(flag):
    return title_status(flag) is True


def big12_titles_by_sport(titles, school=SCHOOL):
    ou = titles[titles['champion'] == school]
    table = ou.pivot_table(index='sport', columns='title_type', values='Season',
                           aggfunc='count', fill_value=0)
    table['Total'] = table.sum(axis=1)
    return table.reset_index().sort_values(['Total', 'sport'], ascending=[False, True]).set_index('sport')


def big12_share_by_school(titles):
    counts = titles['champion'].value_counts().sort_index()
    counts = counts.sort_values(ascending=False, kind='stable')
    return pd.DataFrame({'titles': counts, 'share': (counts / counts.sum()).round(3)})


def comparable_big12_titles(titles, school=SCHOOL):
    """OU Big 12 titles per academic year, restricted to the comparable basket."""
    mask = pd.Series(False, index=titles.index)
    for sport, columns in COMPARABLE_TITLES.items():
        mask |= (titles['sport'] == sport) & titles['title_type'].isin(columns)
    basket = titles[mask]
    years = sorted(basket['academic_year'].unique())
    per_year = basket[basket['champion'] == school].groupby('academic_year').size()
    return per_year.reindex(years, fill_value=0)


def comparable_sec_titles(sec):
    """One row per comparable SEC title opportunity; ``won`` is NA when unknown."""
    rows = []
    for _, r in sec[sec['sport'].isin(COMPARABLE_TITLES)].iterrows():
        for field in COMPARABLE_TITLES[r['sport']].values():
            rows.append({'academic_year': r['academic_year'], 'sport': r['sport'],
                         'title_type': field, 'won': title_status(r[field])})
    out = pd.DataFrame(rows, columns=['academic_year', 'sport', 'title_type', 'won'])
    out['won'] = out['won'].astype('boolean')
    return out


def sec_titles_per_year(basket):
    """Titles won and unknown outcomes per SEC academic year."""
    grouped = basket.groupby('academic_year')['won']
    return pd.DataFrame({'titles': grouped.sum().astype(int),
                         'unknown': grouped.apply(lambda s: int(s.isna().sum()))})


def all_sec_titles(sec):
    """Every SEC title OU won, including ones outside the comparable basket."""
    rows = []
    for _, r in sec.iterrows():
        for field in ('reg_season_title', 'tourney_title'):
            if is_title(r[field]):
                rows.append({'academic_year': r['academic_year'], 'sport': r['sport'],
                             'title_type': field, 'shared': str(r[field]).lower() == 'shared'})
    return pd.DataFrame(rows, columns=['academic_year', 'sport', 'title_type', 'shared'])


def conference_win_pct(sec):
    """Per sport-season win %, counting ties as half a win."""
    known = sec.dropna(subset=['conf_wins', 'conf_losses']).copy()
    known['conf_ties'] = known['conf_ties'].fillna(0)
    games = known['conf_wins'] + known['conf_losses'] + known['conf_ties']
    known['conf_win_pct'] = ((known['conf_wins'] + 0.5 * known['conf_ties']) / games).astype(float).round(3)
    return known[['academic_year', 'sport', 'conf_wins', 'conf_losses', 'conf_ties',
                  'conf_win_pct', 'confidence']].reset_index(drop=True)


def poisson_cdf(k, lam):
    """P(X <= k) for X ~ Poisson(lam)."""
    if k < 0:
        return 0.0
    return sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(k + 1))


def title_rate_test(big12_per_year, sec_titles, sec_years, unknown=0):
    """How surprising is the SEC title count if OU kept its Big 12 rate?

    Treats titles as Poisson events. This ignores conference-strength
    differences and correlation between sports, so it is a sanity check,
    not a causal estimate. When some SEC outcomes are unknown the observed
    count is a lower bound, so the p-value is also given for the case where
    every unknown outcome was a title.
    """
    if len(big12_per_year) == 0 or sec_years == 0:
        raise ValueError('title_rate_test needs at least one Big 12 and one SEC year')
    rate = float(big12_per_year.mean())
    expected = rate * sec_years
    return {
        'big12_years': len(big12_per_year),
        'big12_rate_per_year': round(rate, 2),
        'sec_years': int(sec_years),
        'expected_titles_at_big12_rate': round(expected, 2),
        'observed_sec_titles': int(sec_titles),
        'unknown_outcomes': int(unknown),
        'p_at_most_observed': round(poisson_cdf(int(sec_titles), expected), 4),
        'p_if_unknowns_were_titles': round(poisson_cdf(int(sec_titles + unknown), expected), 4),
    }


def build_summary(titles, sec, recent_years=5):
    """All derived tables, so main() and the tests share one code path."""
    big12_basket = comparable_big12_titles(titles)
    sec_basket = comparable_sec_titles(sec)
    sec_per_year = sec_titles_per_year(sec_basket)
    n_sec = len(sec_per_year)
    observed, unknown = sec_per_year['titles'].sum(), sec_per_year['unknown'].sum()
    rate_tests = pd.DataFrame([
        {'baseline': 'Big 12 full history',
         **title_rate_test(big12_basket, observed, n_sec, unknown)},
        {'baseline': f'Big 12 last {recent_years} years',
         **title_rate_test(big12_basket.iloc[-recent_years:], observed, n_sec, unknown)},
    ])
    return {
        'by_sport': big12_titles_by_sport(titles),
        'share': big12_share_by_school(titles),
        'big12_basket': big12_basket,
        'sec_basket': sec_basket,
        'sec_per_year': sec_per_year,
        'sec_all': all_sec_titles(sec),
        'win_pct': conference_win_pct(sec),
        'rate_tests': rate_tests,
    }


# ---------------------------------------------------------------- charts

def plot_title_rates(big12_per_year, sec_per_year, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    years = year_range(big12_per_year.index[0], sec_per_year.index[-1])
    x = {y: i for i, y in enumerate(years)}
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.bar([x[y] for y in big12_per_year.index], big12_per_year.values, color='#9aa5b1', label='Big 12')
    ax.bar([x[y] for y in sec_per_year.index], sec_per_year['titles'].values, color='#841617', label='SEC')
    if sec_per_year['unknown'].any():
        ax.bar([x[y] for y in sec_per_year.index], sec_per_year['unknown'].values,
               bottom=sec_per_year['titles'].values, fill=False, hatch='///',
               edgecolor='#841617', linewidth=0.8, label='SEC outcome unknown')
    for y in years:
        if y not in big12_per_year.index and y not in sec_per_year.index:
            ax.text(x[y], 0.05, 'no data', rotation=90, ha='center', va='bottom', fontsize=7, color='#666')
    ax.set_xticks(range(len(years)), years)
    ax.set_ylabel('Conference titles won')
    ax.set_title(f'Oklahoma conference titles per year, comparable {len(COMPARABLE_TITLES)}-sport basket')
    ax.tick_params(axis='x', rotation=60, labelsize=8)
    ax.spines[['top', 'right']].set_visible(False)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150, metadata={'Software': None})
    plt.close(fig)


def plot_directors_cup(cup, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    years = year_range(cup['academic_year'].min(), cup['academic_year'].max())
    pos = {y: i for i, y in enumerate(years)}
    fig, ax = plt.subplots(figsize=(7, 4))
    for school, color in (('Oklahoma', '#841617'), ('Oklahoma State', '#ff7300')):
        d = cup[(cup['school'] == school) & cup['rank'].notna()]
        # Reindex onto every year so a missing season breaks the line rather
        # than drawing a trend through it.
        ranks = d.set_index('academic_year')['rank'].astype(float).reindex(years)
        first, last = ranks.first_valid_index(), ranks.last_valid_index()
        span = ranks.loc[first:last]
        ax.plot([pos[y] for y in span.index], span.values, marker='o', color=color, label=school)
        for y, r in span.dropna().items():
            ax.annotate(str(int(r)), (pos[y], r), textcoords='offset points', xytext=(8, 4),
                        fontsize=8, color=color)
    ax.invert_yaxis()
    ax.yaxis.get_major_locator().set_params(integer=True)
    oklahoma = cup[cup['school'] == 'Oklahoma']
    for y in years:
        if oklahoma.loc[oklahoma['academic_year'] == y, 'rank'].notna().sum() == 0:
            ax.text(pos[y], 0.5, 'OU: no data', rotation=90, ha='center', va='center', fontsize=7,
                    color='#666', transform=ax.get_xaxis_transform())
    if pos.get(FIRST_SEC_YEAR, 0) > 0:
        sec_start = pos[FIRST_SEC_YEAR] - 0.5
        ax.axvline(sec_start, color='#666', linestyle=':', linewidth=1)
        ax.text(sec_start + 0.05, 0.45, 'OU joins SEC', fontsize=8, color='#444',
                transform=ax.get_xaxis_transform())
    ax.set_xticks(range(len(years)), years)
    ax.set_ylabel('Directors\' Cup rank (lower is better)')
    ax.set_title('Learfield Directors\' Cup national rank')
    ax.spines[['top', 'right']].set_visible(False)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150, metadata={'Software': None})
    plt.close(fig)


# ---------------------------------------------------------------- entry point

def main(reports_dir=REPORTS_DIR):
    reports_dir = Path(reports_dir)
    try:
        titles = load_big12_titles()
        sec = load_sec_results()
        cup = load_directors_cup()
    except DataValidationError as err:
        print(f'Input validation failed:\n{err}', file=sys.stderr)
        return 1

    s = build_summary(titles, sec)
    reports_dir.mkdir(parents=True, exist_ok=True)
    s['by_sport'].to_csv(reports_dir / 'ou_big12_titles_by_sport.csv')
    s['share'].to_csv(reports_dir / 'big12_title_share_by_school.csv', index_label='champion')
    s['big12_basket'].rename('ou_titles').to_csv(reports_dir / 'ou_big12_comparable_titles_per_year.csv',
                                                 index_label='academic_year')
    s['sec_per_year'].to_csv(reports_dir / 'ou_sec_comparable_titles_per_year.csv', index_label='academic_year')
    s['sec_all'].to_csv(reports_dir / 'ou_sec_titles.csv', index=False)
    s['win_pct'].to_csv(reports_dir / 'ou_sec_conference_win_pct.csv', index=False)
    s['rate_tests'].to_csv(reports_dir / 'ou_title_rate_test.csv', index=False)
    plot_title_rates(s['big12_basket'], s['sec_per_year'], reports_dir / 'ou_titles_per_year.png')
    plot_directors_cup(cup, reports_dir / 'ou_directors_cup.png')

    pd.set_option('display.width', 160)
    print(f'OU Big 12 titles by sport (scraped data, through {titles["academic_year"].max()}):')
    print(s['by_sport'].to_string(), '\n')
    print('Big 12 title share, top 5:')
    print(s['share'].head().to_string(), '\n')
    print('SEC-era titles (all sports):')
    print(s['sec_all'].to_string(index=False) if len(s['sec_all']) else '  none', '\n')
    print('SEC comparable-basket titles per year:')
    print(s['sec_per_year'].to_string(), '\n')
    print('SEC conference win % by sport:')
    print(s['win_pct'].to_string(index=False), '\n')
    print('Title-rate check (comparable basket):')
    print(s['rate_tests'].to_string(index=False))
    print(f'\nOutputs written to {reports_dir}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
