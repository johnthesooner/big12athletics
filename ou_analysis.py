"""University of Oklahoma: Big 12 baseline vs. SEC era.

Combines the scraped Big 12 champions tables (``Championships by Season/``)
with the hand-curated SEC-era results in ``oklahoma_sec/`` and writes
summary tables and charts to ``reports/``.

Run:  python ou_analysis.py
"""
import math
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
BIG12_DIR = ROOT / 'Championships by Season'
SEC_RESULTS = ROOT / 'oklahoma_sec' / 'ou_sec_results.csv'
DIRECTORS_CUP = ROOT / 'oklahoma_sec' / 'directors_cup.csv'
REPORTS_DIR = ROOT / 'reports'

SCHOOL = 'Oklahoma'

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
    "Men's Basketball": {'Regular season': 'reg_season_title', 'Tournament': 'tourney_title'},
    "Women's Basketball": {'Regular Season': 'reg_season_title', 'Tournament': 'tourney_title'},
    "Women's Soccer": {'Regular Season': 'reg_season_title', 'Tournament': 'tourney_title'},
    'Volleyball': {'Champion': 'reg_season_title'},
    "Women's Gymnastics": {'Champion': 'tourney_title'},
}

FIRST_BIG12_YEAR = '1996-97'

_FOOTNOTE = re.compile(r'\[[^\]]*\]|[†‡*]')


def clean_team(value):
    """Strip Wikipedia footnote markers ('Baylor†', '—[a]') from a cell."""
    if pd.isna(value):
        return ''
    return _FOOTNOTE.sub('', str(value)).strip()


def sport_from_filename(path):
    """"Men's_Tennis_titles_by_season[18].csv" -> "Men's Tennis"."""
    stem = re.sub(r'\[\d+\]$', '', Path(path).stem)
    return stem.replace('_titles_by_season', '').replace('_', ' ')


def academic_year(sport, season):
    """Map a Big 12 table season label to an 'YYYY-YY' academic year."""
    end = int(season) + 1 if sport in FALL_SPORTS else int(season)
    return f'{end - 1}-{str(end)[2:]}'


def load_big12_titles(directory=BIG12_DIR):
    """Long-format table: one row per (sport, season, title type, champion)."""
    frames = []
    for path in sorted(Path(directory).glob('*.csv')):
        sport = sport_from_filename(path)
        df = pd.read_csv(path, dtype=str)
        long = df.melt(id_vars='Season', var_name='title_type', value_name='champion')
        long['champion'] = long['champion'].map(clean_team)
        long['shared'] = df.melt(id_vars='Season')['value'].fillna('').str.contains('†').values
        long['sport'] = sport
        frames.append(long)
    titles = pd.concat(frames, ignore_index=True)
    titles = titles[~titles['champion'].isin(['', '—'])]
    titles['academic_year'] = [academic_year(s, y) for s, y in zip(titles['sport'], titles['Season'])]
    # The softball table starts at "1996", which maps to a year before the
    # conference's first season (1996-97); drop it rather than guess.
    titles = titles[titles['academic_year'] >= FIRST_BIG12_YEAR]
    return titles.reset_index(drop=True)


def load_sec_results(path=SEC_RESULTS):
    return pd.read_csv(path, dtype={'conf_wins': 'Int64', 'conf_losses': 'Int64'})


def is_title(flag):
    """SEC flags: 'Y' and 'shared' both count as a title."""
    return str(flag).strip().lower() in {'y', 'shared'}


def big12_titles_by_sport(titles, school=SCHOOL):
    ou = titles[titles['champion'] == school]
    table = ou.pivot_table(index='sport', columns='title_type', values='Season',
                           aggfunc='count', fill_value=0)
    table['Total'] = table.sum(axis=1)
    return table.sort_values('Total', ascending=False)


def big12_share_by_school(titles):
    counts = titles['champion'].value_counts()
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
    rows = []
    for _, r in sec[sec['sport'].isin(COMPARABLE_TITLES)].iterrows():
        for field in COMPARABLE_TITLES[r['sport']].values():
            rows.append({'academic_year': r['academic_year'], 'sport': r['sport'],
                         'title_type': field, 'won': is_title(r[field])})
    return pd.DataFrame(rows)


def all_sec_titles(sec):
    """Every SEC title OU won, including ones outside the comparable basket."""
    rows = []
    for _, r in sec.iterrows():
        for field in ('reg_season_title', 'tourney_title'):
            if is_title(r[field]):
                rows.append({'academic_year': r['academic_year'], 'sport': r['sport'],
                             'title_type': field, 'shared': str(r[field]).lower() == 'shared'})
    return pd.DataFrame(rows)


def conference_win_pct(sec):
    known = sec.dropna(subset=['conf_wins', 'conf_losses']).copy()
    games = known['conf_wins'] + known['conf_losses']
    known['conf_win_pct'] = (known['conf_wins'] / games).astype(float).round(3)
    return known[['academic_year', 'sport', 'conf_wins', 'conf_losses', 'conf_win_pct', 'confidence']]


def poisson_cdf(k, lam):
    """P(X <= k) for X ~ Poisson(lam)."""
    return sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(k + 1))


def title_rate_test(big12_per_year, sec_titles, sec_years):
    """How surprising is the SEC title count if OU kept its Big 12 rate?

    Treats titles as Poisson events. This ignores conference-strength
    differences and correlation between sports, so it is a sanity check,
    not a causal estimate.
    """
    rate = float(big12_per_year.mean())
    expected = rate * sec_years
    return {
        'big12_rate_per_year': round(rate, 2),
        'sec_years': sec_years,
        'expected_titles_at_big12_rate': round(expected, 2),
        'observed_sec_titles': int(sec_titles),
        'p_at_most_observed': round(poisson_cdf(int(sec_titles), expected), 4),
    }


def year_range(first, last):
    """Every 'YYYY-YY' label from first to last inclusive."""
    start, end = int(first[:4]), int(last[:4])
    return [f'{y}-{str(y + 1)[2:]}' for y in range(start, end + 1)]


def plot_title_rates(big12_per_year, sec_per_year, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    years = year_range(big12_per_year.index[0], sec_per_year.index[-1])
    x = {y: i for i, y in enumerate(years)}
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.bar([x[y] for y in big12_per_year.index], big12_per_year.values, color='#9aa5b1', label='Big 12')
    ax.bar([x[y] for y in sec_per_year.index], sec_per_year.values, color='#841617', label='SEC')
    for y in years:
        if y not in big12_per_year.index and y not in sec_per_year.index:
            ax.text(x[y], 0.05, 'no data', rotation=90, ha='center', va='bottom', fontsize=7, color='#666')
    ax.set_xticks(range(len(years)), years)
    ax.set_ylabel('Conference titles won')
    ax.set_title('Oklahoma conference titles per year, comparable 7-sport basket')
    ax.tick_params(axis='x', rotation=60, labelsize=8)
    ax.spines[['top', 'right']].set_visible(False)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
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
        xs = [pos[y] for y in d['academic_year']]
        ax.plot(xs, d['rank'], marker='o', color=color, label=school)
        for x, y in zip(xs, d['rank']):
            ax.annotate(f'{int(y)}', (x, y), textcoords='offset points', xytext=(0, 7),
                        ha='center', fontsize=8, color=color)
    sec_start = pos['2024-25'] - 0.5
    ax.axvline(sec_start, color='#666', linestyle=':', linewidth=1)
    ax.invert_yaxis()
    ax.text(sec_start + 0.05, 0.95, 'OU joins SEC', fontsize=8, color='#444',
            transform=ax.get_xaxis_transform())
    ax.set_xticks(range(len(years)), years)
    ax.set_ylabel('Directors\' Cup rank (lower is better)')
    ax.set_title('Learfield Directors\' Cup national rank')
    ax.spines[['top', 'right']].set_visible(False)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    REPORTS_DIR.mkdir(exist_ok=True)
    titles = load_big12_titles()
    sec = load_sec_results()
    cup = pd.read_csv(DIRECTORS_CUP, dtype={'rank': 'Int64'}).sort_values('academic_year')

    by_sport = big12_titles_by_sport(titles)
    share = big12_share_by_school(titles)
    big12_basket = comparable_big12_titles(titles)
    sec_basket = comparable_sec_titles(sec)
    sec_per_year = sec_basket.groupby('academic_year')['won'].sum().astype(int)
    sec_all = all_sec_titles(sec)
    win_pct = conference_win_pct(sec)

    recent = big12_basket.iloc[-5:]
    tests = pd.DataFrame([
        {'baseline': 'Big 12 full history', **title_rate_test(big12_basket, sec_per_year.sum(), len(sec_per_year))},
        {'baseline': 'Big 12 last 5 years', **title_rate_test(recent, sec_per_year.sum(), len(sec_per_year))},
    ])

    by_sport.to_csv(REPORTS_DIR / 'ou_big12_titles_by_sport.csv')
    share.to_csv(REPORTS_DIR / 'big12_title_share_by_school.csv')
    big12_basket.rename('ou_titles').to_csv(REPORTS_DIR / 'ou_big12_comparable_titles_per_year.csv')
    sec_all.to_csv(REPORTS_DIR / 'ou_sec_titles.csv', index=False)
    win_pct.to_csv(REPORTS_DIR / 'ou_sec_conference_win_pct.csv', index=False)
    tests.to_csv(REPORTS_DIR / 'ou_title_rate_test.csv', index=False)
    plot_title_rates(big12_basket, sec_per_year, REPORTS_DIR / 'ou_titles_per_year.png')
    plot_directors_cup(cup, REPORTS_DIR / 'ou_directors_cup.png')

    print('OU Big 12 titles by sport (scraped data, seasons through 2023):')
    print(by_sport.to_string(), '\n')
    print('Big 12 title share, top 5:')
    print(share.head().to_string(), '\n')
    print('SEC-era titles (all sports):')
    print(sec_all.to_string(index=False) if len(sec_all) else '  none', '\n')
    print('SEC conference win % by sport:')
    print(win_pct.to_string(index=False), '\n')
    print('Title-rate check (comparable basket):')
    print(tests.to_string(index=False))
    print(f'\nOutputs written to {REPORTS_DIR}')


if __name__ == '__main__':
    main()
