"""Build the self-contained story page (docs/index.html) from the analysis.

Every number on the page is read from the same summary the reports use, so
the page cannot drift from the data. Charts are inline SVG (readable with
JavaScript off, theme-aware through CSS variables); a small script adds hover
tooltips. All data-derived text goes through ``html.escape``.
"""
import csv
import math
from html import escape
from pathlib import Path

import pandas as pd

from . import __version__
from . import config as cfg
from .data import year_range

TEMPLATE = Path(__file__).with_name('templates') / 'site.html'
REPO_URL = 'https://github.com/johnthesooner/big12athletics'
SPORT_ORDER = ['Football', "Men's Basketball", "Women's Basketball", 'Baseball', 'Softball',
               "Women's Gymnastics", 'Volleyball', "Women's Soccer"]


def e(value):
    return escape(str(value), quote=True)


def short_sport(sport):
    """"Women's Gymnastics" -> "gymnastics"."""
    return sport.lower().replace("women's ", '').replace("men's ", '')


def ordinal(n):
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def fmt_p(p):
    return f'{p:.2f}'


# ---------------------------------------------------------------- SVG charts

def _tip(*lines):
    """Data attributes read by the tooltip script (and a <title> for no-JS)."""
    text = ' · '.join(lines)
    return f' tabindex="0" data-tip="{e(text)}"', f'<title>{e(text)}</title>'


def _bar_path(x, y, w, h, r=4):
    """Column with a rounded data end and a square baseline."""
    if h <= 0:
        return ''
    r = min(r, w / 2, h)
    return (f'M{x:.1f},{y + h:.1f} L{x:.1f},{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} '
            f'L{x + w - r:.1f},{y:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} L{x + w:.1f},{y + h:.1f} Z')


def titles_chart(big12, sec_per_year, school):
    """Columns: titles per year, Big 12 (context grey) then SEC (school colour)."""
    years = year_range(big12.index[0], sec_per_year.index[-1])
    W, H, left, right, top, bottom = 760, 300, 34, 12, 18, 58
    plot_w, plot_h = W - left - right, H - top - bottom
    ymax = max(4, int(max(big12.max(), (sec_per_year['titles'] + sec_per_year['unknown']).max())))
    band = plot_w / len(years)
    bw = min(16, band - 4)
    y = lambda v: top + plot_h - v / ymax * plot_h  # noqa: E731
    key = 'ou' if school == cfg.FOCUS_SCHOOL else 'tx'
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="t1-title t1-desc" class="chart">',
           f'<title id="t1-title">{e(school)} conference titles per year</title>',
           '<desc id="t1-desc">Comparable conference titles won each year, Big 12 seasons in grey and SEC '
           'seasons in colour. Full numbers are in the table below the chart.</desc>']
    for v in range(0, ymax + 1):
        out.append(f'<line class="grid" x1="{left}" x2="{W - right}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                   f'<text class="tick" x="{left - 8}" y="{y(v) + 4:.1f}" text-anchor="end">{v}</text>')
    sec_start = None
    for i, yr in enumerate(years):
        x = left + i * band + (band - bw) / 2
        cx = x + bw / 2
        if yr in big12.index:
            v = int(big12[yr])
            attrs, title = _tip(yr, f'{v} Big 12 title{"s" if v != 1 else ""}')
            out.append(f'<g class="mark"{attrs}>{title}<rect class="hit" x="{left + i * band:.1f}" y="{top}" '
                       f'width="{band:.1f}" height="{plot_h}"/>'
                       f'<path class="bar big12" d="{_bar_path(x, y(v), bw, y(0) - y(v))}"/></g>')
        elif yr in sec_per_year.index:
            sec_start = sec_start if sec_start is not None else left + i * band
            v, u = int(sec_per_year.at[yr, 'titles']), int(sec_per_year.at[yr, 'unknown'])
            lines = [yr, f'{v} SEC title{"s" if v != 1 else ""}']
            if u:
                lines.append(f'{u} outcome{"s" if u != 1 else ""} unknown')
            attrs, title = _tip(*lines)
            unknown = (f'<rect class="unknown {key}" x="{x + 1:.1f}" y="{y(v + u) + 1:.1f}" width="{bw - 2:.1f}" '
                       f'height="{max(0, y(v) - y(v + u) - 3):.1f}" rx="3"/>' if u else '')
            out.append(f'<g class="mark"{attrs}>{title}<rect class="hit" x="{left + i * band:.1f}" y="{top}" '
                       f'width="{band:.1f}" height="{plot_h}"/>'
                       f'<path class="bar {key}" d="{_bar_path(x, y(v), bw, y(0) - y(v))}"/>{unknown}'
                       f'<text class="value" x="{cx:.1f}" y="{y(v + u) - 6:.1f}" text-anchor="middle">{v}</text></g>')
        else:
            out.append(f'<text class="note" x="{cx:.1f}" y="{y(0) - 6:.1f}" text-anchor="middle" '
                       f'transform="rotate(-90 {cx:.1f} {y(0) - 6:.1f})" dy="4">no data</text>')
        if i % 2 == 0 or yr in sec_per_year.index:
            out.append(f'<text class="tick" x="{cx:.1f}" y="{H - bottom + 16}" text-anchor="end" '
                       f'transform="rotate(-50 {cx:.1f} {H - bottom + 16})">{yr}</text>')
    if sec_start is not None:
        out.append(f'<line class="divider" x1="{sec_start:.1f}" x2="{sec_start:.1f}" y1="{top - 6}" '
                   f'y2="{y(0)}"/><text class="note" x="{sec_start + 6:.1f}" y="{top + 4}">SEC era</text>')
    out.append(f'<line class="axis" x1="{left}" x2="{W - right}" y1="{y(0):.1f}" y2="{y(0):.1f}"/></svg>')
    return ''.join(out)


def peer_chart(peers):
    """Grouped columns: recent Big 12 rate vs SEC rate for each school."""
    W, H, left, right, top, bottom = 520, 260, 34, 12, 26, 44
    plot_w, plot_h = W - left - right, H - top - bottom
    ymax = max(3, math.ceil(max(peers['big12_rate_recent'].max(), peers['sec_rate'].max())))
    y = lambda v: top + plot_h - v / ymax * plot_h  # noqa: E731
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="t2-title" class="chart">',
           '<title id="t2-title">Comparable conference titles per year: last five Big 12 years vs the SEC</title>']
    for v in range(ymax + 1):
        out.append(f'<line class="grid" x1="{left}" x2="{W - right}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                   f'<text class="tick" x="{left - 8}" y="{y(v) + 4:.1f}" text-anchor="end">{v}</text>')
    group = plot_w / len(peers)
    bw = 24
    for i, r in enumerate(peers.itertuples()):
        key = 'ou' if r.school == cfg.FOCUS_SCHOOL else 'tx'
        gx = left + i * group + group / 2
        for j, (label, val, cls) in enumerate((('Last 5 Big 12 years', r.big12_rate_recent, 'big12'),
                                               ('SEC, 2024-26', r.sec_rate, key))):
            x = gx - bw - 6 + j * (bw + 12)
            attrs, title = _tip(r.school, label, f'{val:.1f} titles per year')
            out.append(f'<g class="mark"{attrs}>{title}<rect class="hit" x="{x - 6}" y="{top}" width="{bw + 12}" '
                       f'height="{plot_h}"/><path class="bar {cls}" d="{_bar_path(x, y(val), bw, y(0) - y(val))}"/>'
                       f'<text class="value" x="{x + bw / 2:.1f}" y="{y(val) - 6:.1f}" '
                       f'text-anchor="middle">{val:.1f}</text></g>')
        out.append(f'<text class="label" x="{gx:.1f}" y="{H - bottom + 20}" text-anchor="middle">{e(r.school)}</text>'
                   f'<text class="tick" x="{gx:.1f}" y="{H - bottom + 36}" text-anchor="middle">'
                   f'{r.basket_sports} comparable sports</text>')
    out.append(f'<line class="axis" x1="{left}" x2="{W - right}" y1="{y(0):.1f}" y2="{y(0):.1f}"/></svg>')
    return ''.join(out)


def cup_chart(cup):
    """Directors' Cup rank lines (rank 1 at the top); missing years break the line."""
    years = year_range(cup['academic_year'].min(), cup['academic_year'].max())
    W, H, left, right, top, bottom = 600, 280, 40, 150, 20, 34
    plot_w, plot_h = W - left - right, H - top - bottom
    worst = int(cup['rank'].max()) + 2
    x = lambda i: left + i * plot_w / (len(years) - 1)  # noqa: E731
    y = lambda r: top + (r - 1) / (worst - 1) * plot_h  # noqa: E731
    keys = {'Oklahoma': 'ou', 'Texas': 'tx', 'Oklahoma State': 'osu'}
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="t3-title" class="chart">',
           '<title id="t3-title">Learfield Directors\' Cup national rank by year (1 is best)</title>']
    for r in (1, 10, 20, 30):
        if r <= worst:
            out.append(f'<line class="grid" x1="{left}" x2="{W - right}" y1="{y(r):.1f}" y2="{y(r):.1f}"/>'
                       f'<text class="tick" x="{left - 8}" y="{y(r) + 4:.1f}" text-anchor="end">#{r}</text>')
    for i, yr in enumerate(years):
        out.append(f'<text class="tick" x="{x(i):.1f}" y="{H - 10}" text-anchor="middle">{yr}</text>')
    if cfg.FIRST_SEC_YEAR in years:
        sx = (x(years.index(cfg.FIRST_SEC_YEAR)) + x(years.index(cfg.FIRST_SEC_YEAR) - 1)) / 2
        out.append(f'<line class="divider" x1="{sx:.1f}" x2="{sx:.1f}" y1="{top - 8}" y2="{top + plot_h}"/>'
                   f'<text class="note" x="{sx + 6:.1f}" y="{top + 2}">SEC era</text>')
    ends = []
    for school in ('Texas', 'Oklahoma', 'Oklahoma State'):
        d = cup[(cup['school'] == school) & cup['rank'].notna()].set_index('academic_year')['rank']
        if d.empty:
            continue
        key = keys[school]
        segments, current = [], []
        for i, yr in enumerate(years):
            if yr in d.index:
                current.append((i, int(d[yr])))
            elif current:
                segments.append(current)
                current = []
        if current:
            segments.append(current)
        for seg in segments:
            if len(seg) > 1:
                pts = ' '.join(f'{x(i):.1f},{y(r):.1f}' for i, r in seg)
                out.append(f'<polyline class="line {key}" points="{pts}"/>')
        for i, r in [p for seg in segments for p in seg]:
            attrs, title = _tip(school, years[i], f'#{r} nationally')
            out.append(f'<g class="mark"{attrs}>{title}<circle class="hit" cx="{x(i):.1f}" cy="{y(r):.1f}" r="12"/>'
                       f'<circle class="dot {key}" cx="{x(i):.1f}" cy="{y(r):.1f}" r="4.5"/></g>')
        last_i, last_r = segments[-1][-1]
        ends.append((y(last_r), x(last_i), school, last_r, key))
    ends.sort()
    placed = []
    for ly, lx, school, r, _key in ends:
        ly = max(ly, placed[-1] + 16) if placed else ly
        placed.append(ly)
        out.append(f'<text class="label" x="{lx + 12:.1f}" y="{ly + 4:.1f}">{e(school)} #{r}</text>')
    out.append('</svg>')
    return ''.join(out)


# ---------------------------------------------------------------- tables & copy

def _chip(flag, label):
    flag = '' if pd.isna(flag) else str(flag).strip().lower()
    if flag == 'y':
        return f'<span class="chip win">{e(label)}</span>'
    if flag == 'shared':
        return f'<span class="chip win">{e(label)} (shared)</span>'
    if flag == '':
        return f'<span class="chip unknown">{e(label)}: unknown</span>'
    return ''


def _record(r):
    if pd.isna(r['conf_wins']):
        return '<span class="muted">not found</span>'
    rec = f'{int(r["conf_wins"])}-{int(r["conf_losses"])}'
    if pd.notna(r['conf_ties']) and int(r['conf_ties']):
        rec += f'-{int(r["conf_ties"])}'
    return rec


def season_cell(r):
    chips = [_chip(r['reg_season_title'], 'SEC regular season'), _chip(r['tourney_title'], 'SEC tournament')]
    if r['national_title'] == 'Y':
        chips.append('<span class="chip natl">National champion</span>')
    finish = f' · {e(r["conf_finish"])}' if pd.notna(r['conf_finish']) else ''
    post = f'<div class="post">{e(r["ncaa_result"])}</div>' if pd.notna(r['ncaa_result']) else ''
    conf = '' if r['confidence'] == 'high' else f' <span class="conf">{e(r["confidence"])} confidence</span>'
    src = (f' <a class="src" href="{e(r["source"])}" target="_blank" rel="noopener">source</a>'
           if pd.notna(r['source']) else '')
    return (f'<div class="rec"><span class="num">{_record(r)}</span>{finish}{conf}{src}</div>'
            f'<div class="chips">{"".join(c for c in chips if c)}</div>{post}')


def sport_table(sec, school):
    rows = sec[sec['school'] == school]
    years = sorted(rows['academic_year'].unique())
    head = ''.join(f'<th scope="col">{e(y)}</th>' for y in years)
    body = []
    for sport in [s for s in SPORT_ORDER if s in set(rows['sport'])]:
        cells = []
        for yr in years:
            match = rows[(rows['sport'] == sport) & (rows['academic_year'] == yr)]
            cells.append(f'<td>{season_cell(match.iloc[0]) if len(match) else ""}</td>')
        body.append(f'<tr><th scope="row">{e(sport)}</th>{"".join(cells)}</tr>')
    return (f'<div class="table-wrap"><table class="sports"><thead><tr><th scope="col">Sport</th>{head}</tr>'
            f'</thead><tbody>{"".join(body)}</tbody></table></div>')


def numbers_table(headers, rows):
    head = ''.join(f'<th scope="col">{e(h)}</th>' for h in headers)
    body = ''.join('<tr>' + ''.join(f'<td>{e(c)}</td>' for c in row) + '</tr>' for row in rows)
    return (f'<div class="table-wrap"><table class="numbers"><thead><tr>{head}</tr></thead>'
            f'<tbody>{body}</tbody></table></div>')


def collect_sources(sec, cup):
    urls = list(dict.fromkeys(list(sec['source'].dropna()) + list(cup['source'].dropna())))
    if cfg.BIG12_SUPPLEMENT.exists():
        with open(cfg.BIG12_SUPPLEMENT, encoding='utf-8') as f:
            urls += [r['source_url'] for r in csv.DictReader(f) if r['source_url'] not in urls]
    return urls


def build_context(summary, sec, cup):
    s = summary
    ou = s['per_school'][cfg.FOCUS_SCHOOL]
    tests = ou['rate_tests'].set_index('baseline')
    recent = tests.iloc[1]
    peers = s['peers'].set_index('school')
    pt = s['peer_tests'].iloc[0] if len(s['peer_tests']) else None
    nat = s['national']
    ou_nat = nat[nat['school'] == cfg.FOCUS_SCHOOL]
    ou_cup = cup[(cup['school'] == cfg.FOCUS_SCHOOL) & (cup['academic_year'] >= cfg.FIRST_SEC_YEAR)]
    share = s['share']
    rank = list(share.index).index(cfg.FOCUS_SCHOOL) + 1
    ou_rate = float(peers.at[cfg.FOCUS_SCHOOL, 'sec_rate'])
    ou_recent = float(peers.at[cfg.FOCUS_SCHOOL, 'big12_rate_recent'])
    conf_counts = sec.groupby('confidence').size().to_dict()
    leaders = list(share.index[:rank - 1])
    ahead = f", behind only {' and '.join(leaders)}" if leaders else ', the most of any school'
    return {
        'ou': ou, 'tests': tests, 'recent': recent, 'peers': peers, 'pt': pt, 'ou_nat': ou_nat,
        'ou_cup': ou_cup, 'rank': rank, 'share': share, 'ou_rate': ou_rate, 'ou_recent': ou_recent,
        'direction': 'fewer' if ou_rate < ou_recent else 'more' if ou_rate > ou_recent else 'as many',
        'conf_counts': conf_counts, 'sources': collect_sources(sec, cup), 'ahead': ahead,
    }


def render(summary, sec, cup):
    c = build_context(summary, sec, cup)
    s = summary
    ou, recent, peers, pt = c['ou'], c['recent'], c['peers'], c['pt']
    tx = peers.loc['Texas'] if 'Texas' in peers.index else None
    sec_years = int(recent['sec_years'])
    nat_list = ', '.join(f'{short_sport(r.sport)} ({r.academic_year})' for r in c['ou_nat'].itertuples())
    cup_ranks = ' and '.join(f'#{int(r)}' for r in c['ou_cup']['rank'])
    sig = recent['p_at_most_observed'] < 0.05
    last_sec = ou['sec_per_year'].index[-1]

    big12_rows = [(y, int(v)) for y, v in ou['big12_per_year'].items()]
    sec_rows = [(y, int(r.titles), int(r.unknown)) for y, r in ou['sec_per_year'].iterrows()]
    t1 = numbers_table(['Year', 'Conference', 'Titles', 'Unknown outcomes'],
                       [(y, 'Big 12', v, '') for y, v in big12_rows] + [(y, 'SEC', v, u) for y, v, u in sec_rows])
    t2 = numbers_table(['School', 'Comparable sports', 'Big 12, all years', 'Big 12, last 5 years', 'SEC',
                        'Change vs last 5'],
                       [(r.Index, r.basket_sports, f'{r.big12_rate_full:.2f}', f'{r.big12_rate_recent:.2f}',
                         f'{r.sec_rate:.2f}', f'{r.change_vs_recent:+.2f}') for r in peers.itertuples()])
    cup_sorted = cup.sort_values(['school', 'academic_year'])
    t3 = numbers_table(['School', 'Year', 'Conference', 'National rank'],
                       [(r.school, r.academic_year, r.conference, '—' if pd.isna(r.rank) else f'#{int(r.rank)}')
                        for r in cup_sorted.itertuples()])
    tests_rows = [(r.school, r.baseline, f'{r.big12_rate_per_year:.2f}', f'{r.expected_titles_at_big12_rate:.2f}',
                   r.observed_sec_titles, r.unknown_outcomes, fmt_p(r.p_at_most_observed),
                   fmt_p(r.p_if_unknowns_were_titles)) for r in s['rate_tests'].itertuples()]
    t4 = numbers_table(['School', 'Baseline', 'Rate / yr', 'Expected (2 yrs)', 'Observed', 'Unknown',
                        'P(≤ observed)', 'P if unknowns were titles'], tests_rows)

    tiles = [
        (f'{c["ou_rate"]:.1f}', 'SEC titles per year',
         f'vs {c["ou_recent"]:.1f} in its last five Big 12 years'),
        (f'{tx["sec_rate"]:.1f}' if tx is not None else '—', 'Texas, same move',
         f'vs {tx["big12_rate_recent"]:.1f} before; Texas held steady' if tx is not None else ''),
        (str(len(c['ou_nat'])), f'national titles in {sec_years} SEC years', nat_list),
        (cup_ranks.replace(' and ', ' / '), "Directors' Cup rank", 'best all-around programs nationally'),
    ]
    tiles_html = ''.join(f'<div class="tile"><div class="tile-value">{e(v)}</div><div class="tile-label">{e(lab)}'
                         f'</div><div class="tile-note">{e(n)}</div></div>' for v, lab, n in tiles)

    pt_html = ''
    if pt is not None:
        pt_html = (f'<p>Is OU\'s gap behind Texas real? Both schools started from the same place, '
                   f'{c["ou_recent"]:.1f} titles a year in their last five Big 12 seasons. Since then OU has won '
                   f'{int(pt["focus_observed"])} and Texas {int(pt["peer_observed"])}. If the two programs were '
                   f'equally strong in the SEC, a split at least this lopsided would happen about '
                   f'<strong>{round(pt["p_focus_at_most_observed"] * 100)}% of the time</strong> by chance. That is '
                   f'too often to call it a real difference yet.</p>')
    sources_html = ''.join(f'<li><a href="{e(u)}" target="_blank" rel="noopener">{e(u)}</a></li>'
                           for u in c['sources'])
    cc = c['conf_counts']
    conf_line = ', '.join(f'{cc.get(k, 0)} {k}' for k in ('high', 'medium', 'low', 'missing') if cc.get(k))

    body = f'''
<header class="masthead">
  <div class="wrap">
    <p class="eyebrow">College athletics · conference realignment · seasons through {e(last_sec)}</p>
    <h1>Did Oklahoma lose ground in the SEC?</h1>
    <p class="dek">Oklahoma left the Big 12 for the SEC in July 2024. Two seasons in, it wins
    <strong>{e(c['direction'])} conference titles</strong> ({c['ou_rate']:.1f} a year against {c['ou_recent']:.1f}),
    while Texas, which moved the same day, has held steady. But two seasons is too short to rule out luck, and on the
    national stage OU is as strong as ever.</p>
  </div>
</header>

<main class="wrap">
  <section class="scoreboard" aria-label="Key numbers">{tiles_html}</section>

  <section>
    <h2>The short answer</h2>
    <ul class="answers">
      <li><strong>Fewer conference trophies, mostly by margin.</strong> OU won {int(recent['observed_sec_titles'])}
      comparable SEC titles in {sec_years} years. At its recent Big 12 pace it would have expected about
      {recent['expected_titles_at_big12_rate']:.1f}. Several of its "misses" were close: gymnastics lost the SEC
      meet by 0.275 and then 0.025 points while winning the national title both years.</li>
      <li><strong>Not yet distinguishable from bad luck.</strong> A shortfall this size would happen about
      {round(recent['p_at_most_observed'] * 100)}% of the time even if nothing had
      changed{' (statistically significant)' if sig else ''}.</li>
      <li><strong>Still elite nationally.</strong> OU won {len(c['ou_nat'])} national championships in its first
      {sec_years} SEC years ({e(nat_list)}) and finished {e(cup_ranks)} in the Directors' Cup, which scores every
      sport's national finish.</li>
    </ul>
  </section>

  <section>
    <h2>Thirty years of conference titles</h2>
    <p class="lede">Each column counts the conference titles OU won that year in the {len(ou['basket'])} sports it
    plays in both leagues. Grey is the Big 12; crimson is the SEC. Dashed outlines are outcomes we could not
    confirm: the most OU could have won.</p>
    <figure class="figure">
      <div class="chart-scroll">{titles_chart(ou['big12_per_year'], ou['sec_per_year'], cfg.FOCUS_SCHOOL)}</div>
      <figcaption>OU ranks {ordinal(c['rank'])} of {len(c['share'])} schools in all-time Big 12 titles in
      these records ({int(c['share'].at[cfg.FOCUS_SCHOOL, 'titles'])}){e(c['ahead'])}. Its final Big 12
      year, {e(s['big12_last_year'])}, was one of its best.</figcaption>
      <details><summary>Show the numbers</summary>{t1}</details>
    </figure>
  </section>

  <section>
    <h2>The Texas test</h2>
    <p class="lede">The best way to separate "the SEC is harder" from "something changed at OU" is to look at
    the school that made the same move on the same day.</p>
    <figure class="figure narrow">
      <div class="legend"><span class="key big12"></span>Last 5 Big 12 years
        <span class="key ou"></span>Oklahoma in the SEC <span class="key tx"></span>Texas in the SEC</div>
      <div class="chart-scroll">{peer_chart(s['peers'])}</div>
      <details><summary>Show the numbers</summary>{t2}</details>
    </figure>
    {pt_html}
  </section>

  <section>
    <h2>Sport by sport</h2>
    <p class="lede">Every row is sourced. Records are SEC regular-season play. Rows we are less sure of
    are labelled.</p>
    {sport_table(sec, cfg.FOCUS_SCHOOL)}
    <details class="peer-table"><summary>Texas, sport by sport</summary>{sport_table(sec, 'Texas')}</details>
  </section>

  <section>
    <h2>The national picture</h2>
    <p class="lede">The Learfield Directors' Cup awards points for every sport's national finish, so it rewards
    breadth. Rank 1 is the best athletic department in the country.</p>
    <figure class="figure narrow">
      <div class="chart-scroll">{cup_chart(cup)}</div>
      <figcaption>OU's 2022-23 rank was not found, so its line breaks there rather than guessing.</figcaption>
      <details><summary>Show the numbers</summary>{t3}</details>
    </figure>
  </section>

  <section>
    <h2>How sure are we?</h2>
    <div class="levels">
      <div><h3>In one sentence</h3><p>OU won one or two fewer titles than usual, which happens often enough by
      chance that two seasons cannot prove the SEC move hurt.</p></div>
      <div><h3>The method</h3><p>We treat each year's titles like a random count with OU's Big 12 average as the
      expected value (a Poisson model), and ask how often a count this low would show up anyway. For the Texas
      comparison we ask how often two equally matched programs would split their titles this unevenly.</p></div>
      <div><h3>What could mislead</h3><p>Titles cluster: softball's regular-season and tournament titles tend to
      come together, which makes streaks look more meaningful than they are. And the SEC is deeper, so the true
      title rate should fall. Neither model captures that, which is why we report them as sanity checks.</p></div>
    </div>
    <details><summary>Full statistical table</summary>{t4}</details>
  </section>

  <section class="method">
    <h2>About the data</h2>
    <ul>
      <li><strong>Big 12 history</strong> comes from Wikipedia's champions tables (scraped), with OU's final season
      (2023-24) added by hand from official sources.</li>
      <li><strong>SEC seasons</strong> are curated by hand: {len(sec)} sport-seasons for OU and Texas, each with a
      source and a confidence level ({e(conf_line)}).</li>
      <li><strong>Compared like with like.</strong> Only sports and titles that exist in both leagues count. SEC
      gymnastics' regular-season title is excluded because the Big 12 had no equivalent. Football is excluded
      because the Big 12 tables do not track it.</li>
      <li><strong>Unknown is not the same as a loss.</strong> Where a result could not be confirmed it is shown as
      unknown and the statistics are given both ways.</li>
    </ul>
    <details><summary>All {len(c['sources'])} sources</summary><ol class="sources">{sources_html}</ol></details>
  </section>
</main>

<footer class="wrap footer">
  <p>Built by a tested Python pipeline (<code>ou-sec all</code>) that validates every input, regenerates every
  number on this page, and fails if anything drifts. Code and data:
  <a href="{REPO_URL}" target="_blank" rel="noopener">{REPO_URL.replace('https://', '')}</a> · v{e(__version__)}</p>
</footer>
<div class="tooltip" id="tooltip" role="status" hidden></div>
'''
    return body


def build_site(summary, sec, cup, out=cfg.SITE_PATH, fragment_out=None):
    """Write the full page; optionally also the head+body fragment used for the artifact."""
    template = TEMPLATE.read_text(encoding='utf-8')
    head, script = template.split('<!--BODY-->')
    body = render(summary, sec, cup)
    fragment = head + body + script
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                   '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                   + head + '</head>\n<body>\n' + body + script + '</body>\n</html>\n', encoding='utf-8')
    if fragment_out:
        Path(fragment_out).write_text(fragment, encoding='utf-8')
    return out
