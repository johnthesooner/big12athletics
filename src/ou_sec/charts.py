"""Static PNG charts for the report (the interactive versions live in the site)."""
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

from . import config as cfg  # noqa: E402
from .data import year_range  # noqa: E402

BIG12_GREY = '#9aa5b1'


def _finish(fig, ax, path):
    ax.spines[['top', 'right']].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150, metadata={'Software': None})
    plt.close(fig)


def plot_title_rates(big12_per_year, sec_per_year, path, school=cfg.FOCUS_SCHOOL, n_sports=None):
    color = cfg.SCHOOL_COLORS.get(school, '#333')
    years = year_range(big12_per_year.index[0], sec_per_year.index[-1])
    x = {y: i for i, y in enumerate(years)}
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.bar([x[y] for y in big12_per_year.index], big12_per_year.values, color=BIG12_GREY, label='Big 12')
    ax.bar([x[y] for y in sec_per_year.index], sec_per_year['titles'].values, color=color, label='SEC')
    if sec_per_year['unknown'].any():
        ax.bar([x[y] for y in sec_per_year.index], sec_per_year['unknown'].values,
               bottom=sec_per_year['titles'].values, fill=False, hatch='///',
               edgecolor=color, linewidth=0.8, label='SEC outcome unknown')
    for y in years:
        if y not in big12_per_year.index and y not in sec_per_year.index:
            ax.text(x[y], 0.05, 'no data', rotation=90, ha='center', va='bottom', fontsize=7, color='#666')
    ax.set_xticks(range(len(years)), years)
    ax.yaxis.get_major_locator().set_params(integer=True)
    ax.set_ylabel('Conference titles won')
    n = n_sports or len(cfg.COMPARABLE_TITLES)
    ax.set_title(f'{school} conference titles per year, comparable {n}-sport basket')
    ax.tick_params(axis='x', rotation=60, labelsize=8)
    ax.legend(frameon=False, loc='upper left')
    _finish(fig, ax, path)


def plot_peer_comparison(peers, path):
    """Recent Big 12 rate vs SEC rate, side by side per school."""
    fig, ax = plt.subplots(figsize=(7, 4))
    width = 0.38
    for i, r in enumerate(peers.itertuples()):
        color = cfg.SCHOOL_COLORS.get(r.school, '#333')
        ax.bar(i - width / 2, r.big12_rate_recent, width, color=BIG12_GREY)
        ax.bar(i + width / 2, r.sec_rate, width, color=color)
        ax.text(i - width / 2, r.big12_rate_recent + 0.05, f'{r.big12_rate_recent:.1f}', ha='center', fontsize=9)
        ax.text(i + width / 2, r.sec_rate + 0.05, f'{r.sec_rate:.1f}', ha='center', fontsize=9)
    labels = [f'{s}\n({n} sports)' for s, n in zip(peers['school'], peers['basket_sports'], strict=True)]
    ax.set_xticks(range(len(peers)), labels)
    ax.set_ylabel('Comparable conference titles per year')
    ax.set_title('Titles per year: last 5 Big 12 years (grey) vs SEC')
    _finish(fig, ax, path)


def plot_directors_cup(cup, path):
    years = year_range(cup['academic_year'].min(), cup['academic_year'].max())
    pos = {y: i for i, y in enumerate(years)}
    fig, ax = plt.subplots(figsize=(7, 4))
    for school in sorted(cup['school'].unique(), key=lambda s: (s != cfg.FOCUS_SCHOOL, s)):
        color = cfg.SCHOOL_COLORS.get(school, '#333')
        d = cup[(cup['school'] == school) & cup['rank'].notna()]
        if d.empty:
            continue
        # Reindex onto every year so a missing season breaks the line rather
        # than drawing a trend through it.
        ranks = d.set_index('academic_year')['rank'].astype(float).reindex(years)
        span = ranks.loc[ranks.first_valid_index():ranks.last_valid_index()]
        ax.plot([pos[y] for y in span.index], span.values, marker='o', color=color, label=school)
        for y, r in span.dropna().items():
            ax.annotate(str(int(r)), (pos[y], r), textcoords='offset points', xytext=(8, 4),
                        fontsize=8, color=color)
    ax.invert_yaxis()
    ax.yaxis.get_major_locator().set_params(integer=True)
    if pos.get(cfg.FIRST_SEC_YEAR, 0) > 0:
        sec_start = pos[cfg.FIRST_SEC_YEAR] - 0.5
        ax.axvline(sec_start, color='#666', linestyle=':', linewidth=1)
        ax.text(sec_start + 0.05, 0.45, 'OU & Texas\njoin SEC', fontsize=8, color='#444',
                transform=ax.get_xaxis_transform())
    ax.set_xticks(range(len(years)), years)
    ax.set_ylabel('Directors\' Cup rank (lower is better)')
    ax.set_title('Learfield Directors\' Cup national rank')
    ax.legend(frameon=False, loc='lower left')
    _finish(fig, ax, path)
