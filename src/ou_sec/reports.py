"""Write the generated tables and charts in reports/."""
from pathlib import Path

from . import charts
from . import config as cfg

TABLES = (
    'ou_big12_titles_by_sport.csv', 'big12_title_share_by_school.csv',
    'ou_big12_comparable_titles_per_year.csv', 'ou_sec_comparable_titles_per_year.csv',
    'sec_titles_by_school.csv', 'sec_conference_win_pct.csv', 'title_rate_tests.csv',
    'peer_comparison.csv', 'peer_tests.csv', 'national_titles.csv',
)
CHARTS = ('ou_titles_per_year.png', 'peer_comparison.png', 'directors_cup.png')


def write_reports(summary, cup, reports_dir=cfg.REPORTS_DIR):
    out = Path(reports_dir)
    out.mkdir(parents=True, exist_ok=True)
    s = summary
    s['by_sport'].to_csv(out / 'ou_big12_titles_by_sport.csv')
    s['share'].to_csv(out / 'big12_title_share_by_school.csv', index_label='champion')
    s['big12_basket'].rename('ou_titles').to_csv(out / 'ou_big12_comparable_titles_per_year.csv',
                                                 index_label='academic_year')
    s['sec_per_year'].to_csv(out / 'ou_sec_comparable_titles_per_year.csv', index_label='academic_year')
    s['sec_all'].to_csv(out / 'sec_titles_by_school.csv', index=False)
    s['win_pct'].to_csv(out / 'sec_conference_win_pct.csv', index=False)
    s['rate_tests'].to_csv(out / 'title_rate_tests.csv', index=False)
    s['peers'].to_csv(out / 'peer_comparison.csv', index=False)
    s['peer_tests'].to_csv(out / 'peer_tests.csv', index=False)
    s['national'].to_csv(out / 'national_titles.csv', index=False)

    focus = s['per_school'][cfg.FOCUS_SCHOOL]
    charts.plot_title_rates(focus['big12_per_year'], focus['sec_per_year'], out / 'ou_titles_per_year.png',
                            n_sports=len(focus['basket']))
    charts.plot_peer_comparison(s['peers'], out / 'peer_comparison.png')
    charts.plot_directors_cup(cup, out / 'directors_cup.png')
    return [out / name for name in TABLES + CHARTS]
