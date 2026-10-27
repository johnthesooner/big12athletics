"""Metrics: Big 12 title baseline vs. SEC results, per school.

Every function takes validated frames from ``ou_sec.data`` and returns plain
DataFrames/Series, so the CLI, the static site and the tests share one code
path.
"""
import math

import pandas as pd

from . import config as cfg


def title_status(flag):
    """True = won (incl. shared), False = did not win or not held, NA = unknown."""
    if pd.isna(flag):
        return pd.NA
    flag = str(flag).strip().lower()
    if flag in cfg.TITLE_FLAGS:
        return True
    if flag in cfg.NO_TITLE_FLAGS:
        return False
    return pd.NA


def is_title(flag):
    return title_status(flag) is True


def school_basket(sec, school):
    """Comparable sports this school actually plays in the SEC (Texas has no gymnastics)."""
    played = set(sec.loc[sec['school'] == school, 'sport'])
    return {s: cols for s, cols in cfg.COMPARABLE_TITLES.items() if s in played}


# ---------------------------------------------------------------- Big 12

def big12_titles_by_sport(titles, school=cfg.FOCUS_SCHOOL):
    ou = titles[titles['champion'] == school]
    table = ou.pivot_table(index='sport', columns='title_type', values='Season',
                           aggfunc='count', fill_value=0)
    table['Total'] = table.sum(axis=1)
    return table.reset_index().sort_values(['Total', 'sport'], ascending=[False, True]).set_index('sport')


def big12_share_by_school(titles):
    counts = titles['champion'].value_counts().sort_index()
    counts = counts.sort_values(ascending=False, kind='stable')
    return pd.DataFrame({'titles': counts, 'share': (counts / counts.sum()).round(3)})


def comparable_big12_titles(titles, school=cfg.FOCUS_SCHOOL, basket=None):
    """Titles per academic year for ``school``, restricted to the comparable basket."""
    basket = cfg.COMPARABLE_TITLES if basket is None else basket
    mask = pd.Series(False, index=titles.index)
    for sport, columns in basket.items():
        mask |= (titles['sport'] == sport) & titles['title_type'].isin(columns)
    in_basket = titles[mask & (titles['academic_year'] >= cfg.FIRST_FULL_BIG12_YEAR)]
    years = sorted(in_basket['academic_year'].unique())
    per_year = in_basket[in_basket['champion'] == school].groupby('academic_year').size()
    return per_year.reindex(years, fill_value=0)


# ---------------------------------------------------------------- SEC

def comparable_sec_titles(sec, school=cfg.FOCUS_SCHOOL, basket=None):
    """One row per comparable SEC title opportunity; ``won`` is NA when unknown."""
    rows_in = sec[sec['school'] == school] if 'school' in sec else sec
    basket = cfg.COMPARABLE_TITLES if basket is None else basket
    rows = []
    for _, r in rows_in[rows_in['sport'].isin(basket)].iterrows():
        for field in basket[r['sport']].values():
            rows.append({'academic_year': r['academic_year'], 'sport': r['sport'],
                         'title_type': field, 'won': title_status(r[field])})
    out = pd.DataFrame(rows, columns=['academic_year', 'sport', 'title_type', 'won'])
    out['won'] = out['won'].astype('boolean')
    return out


def sec_titles_per_year(basket_rows):
    """Titles won and unknown outcomes per SEC academic year."""
    grouped = basket_rows.groupby('academic_year')['won']
    return pd.DataFrame({'titles': grouped.sum().astype(int),
                         'unknown': grouped.apply(lambda s: int(s.isna().sum()))})


def all_sec_titles(sec):
    """Every SEC title won, including ones outside the comparable basket."""
    rows = []
    for _, r in sec.iterrows():
        for field in ('reg_season_title', 'tourney_title'):
            if is_title(r[field]):
                rows.append({'school': r.get('school', cfg.FOCUS_SCHOOL), 'academic_year': r['academic_year'],
                             'sport': r['sport'], 'title_type': field,
                             'shared': str(r[field]).lower() == 'shared'})
    return pd.DataFrame(rows, columns=['school', 'academic_year', 'sport', 'title_type', 'shared'])


def conference_win_pct(sec):
    """Per school/sport/season win %, counting ties as half a win."""
    known = sec.dropna(subset=['conf_wins', 'conf_losses']).copy()
    known['conf_ties'] = known['conf_ties'].fillna(0)
    games = known['conf_wins'] + known['conf_losses'] + known['conf_ties']
    known['conf_win_pct'] = ((known['conf_wins'] + 0.5 * known['conf_ties']) / games).astype(float).round(3)
    cols = ['school', 'academic_year', 'sport', 'conf_wins', 'conf_losses', 'conf_ties',
            'conf_win_pct', 'confidence']
    return known[[c for c in cols if c in known]].reset_index(drop=True)


def national_titles(sec):
    won = sec[sec['national_title'] == 'Y']
    return won[['school', 'academic_year', 'sport']].reset_index(drop=True)


# ---------------------------------------------------------------- statistics

def poisson_cdf(k, lam):
    """P(X <= k) for X ~ Poisson(lam)."""
    if k < 0:
        return 0.0
    return sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(k + 1))


def title_rate_test(big12_per_year, sec_titles, sec_years, unknown=0):
    """How surprising is the SEC title count if the school kept its Big 12 rate?

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


def school_summary(titles, sec, school, recent_years=cfg.RECENT_YEARS):
    """Big 12 baseline, SEC results and rate tests for one school."""
    basket = school_basket(sec, school)
    big12 = comparable_big12_titles(titles, school, basket)
    sec_per_year = sec_titles_per_year(comparable_sec_titles(sec, school, basket))
    n_sec = len(sec_per_year)
    observed, unknown = int(sec_per_year['titles'].sum()), int(sec_per_year['unknown'].sum())
    tests = pd.DataFrame([
        {'school': school, 'baseline': 'Big 12 full history',
         **title_rate_test(big12, observed, n_sec, unknown)},
        {'school': school, 'baseline': f'Big 12 last {recent_years} years',
         **title_rate_test(big12.iloc[-recent_years:], observed, n_sec, unknown)},
    ])
    return {'basket': sorted(basket), 'big12_per_year': big12, 'sec_per_year': sec_per_year, 'rate_tests': tests}


def peer_comparison(per_school):
    """Change in comparable titles per year, Big 12 (recent) -> SEC, per school.

    Descriptive only: with two SEC seasons the difference between schools
    (a crude difference-in-differences) has a very wide uncertainty band.
    """
    rows = []
    for school, s in per_school.items():
        recent = s['rate_tests'].iloc[1]
        sec_rate = s['sec_per_year']['titles'].mean()
        rows.append({
            'school': school,
            'basket_sports': len(s['basket']),
            'big12_rate_full': s['rate_tests'].iloc[0]['big12_rate_per_year'],
            'big12_rate_recent': recent['big12_rate_per_year'],
            'sec_rate': round(float(sec_rate), 2),
            'change_vs_recent': round(float(sec_rate - recent['big12_rate_per_year']), 2),
            'sec_unknown_outcomes': int(s['sec_per_year']['unknown'].sum()),
        })
    return pd.DataFrame(rows)


def binomial_cdf(k, n, p):
    """P(X <= k) for X ~ Binomial(n, p)."""
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def peer_rate_test(focus, peer, focus_unknown=0):
    """Did the focus school fall behind the peer by more than chance would allow?

    Exact conditional test for two Poisson counts: given the combined SEC
    title total, the focus school's share is Binomial(n, p0), where p0 is its
    share of the titles *expected* from each school's recent Big 12 rate. A
    small p means the focus school under-performed the peer relative to
    their own baselines. Unknown focus outcomes are bounded as in
    ``title_rate_test``.
    """
    e_focus, e_peer = focus['expected'], peer['expected']
    p0 = e_focus / (e_focus + e_peer)

    def p_value(k_focus):
        n = k_focus + peer['observed']
        return round(binomial_cdf(k_focus, n, p0), 4)

    return {
        'focus': focus['school'], 'peer': peer['school'],
        'focus_observed': focus['observed'], 'peer_observed': peer['observed'],
        'focus_expected': round(e_focus, 2), 'peer_expected': round(e_peer, 2),
        'expected_focus_share': round(p0, 3),
        'p_focus_at_most_observed': p_value(focus['observed']),
        'p_if_focus_unknowns_were_titles': p_value(focus['observed'] + focus_unknown),
    }


def peer_tests(per_school, focus=cfg.FOCUS_SCHOOL):
    """Focus school vs each peer, using the recent Big 12 baseline."""
    def counts(school):
        t = per_school[school]['rate_tests'].iloc[1]
        return {'school': school, 'observed': int(t['observed_sec_titles']),
                'expected': float(t['expected_titles_at_big12_rate']), 'unknown': int(t['unknown_outcomes'])}

    f = counts(focus)
    rows = [peer_rate_test(f, counts(p), f['unknown']) for p in per_school if p != focus]
    return pd.DataFrame(rows)


def build_summary(titles, sec, schools=None, recent_years=cfg.RECENT_YEARS):
    """All derived tables in one dict."""
    if schools is None:
        present = set(sec['school'])
        schools = [s for s in (cfg.FOCUS_SCHOOL, *cfg.PEER_SCHOOLS) if s in present]
    per_school = {s: school_summary(titles, sec, s, recent_years) for s in schools}
    focus = per_school[cfg.FOCUS_SCHOOL]
    return {
        'schools': schools,
        'per_school': per_school,
        'by_sport': big12_titles_by_sport(titles),
        'share': big12_share_by_school(titles),
        'big12_basket': focus['big12_per_year'],
        'sec_per_year': focus['sec_per_year'],
        'rate_tests': pd.concat([p['rate_tests'] for p in per_school.values()], ignore_index=True),
        'peers': peer_comparison(per_school),
        'peer_tests': peer_tests(per_school),
        'sec_all': all_sec_titles(sec),
        'win_pct': conference_win_pct(sec),
        'national': national_titles(sec),
        'big12_last_year': titles['academic_year'].max(),
    }
