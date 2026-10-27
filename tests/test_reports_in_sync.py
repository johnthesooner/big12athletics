"""Guards against stale committed outputs and a report that drifts from the code."""
import pandas as pd
import pytest

from ou_sec import cli
from ou_sec import config as cfg
from ou_sec.reports import TABLES

REPORT = cfg.REPORTS_DIR / 'OU_SEC_Performance.md'


@pytest.fixture(scope='module')
def fresh(tmp_path_factory):
    out = tmp_path_factory.mktemp('reports')
    assert cli.main(['report', '--out', str(out), '--quiet']) == 0
    return out


@pytest.mark.parametrize('name', TABLES)
def test_committed_csv_matches_regenerated(fresh, name):
    committed = (cfg.REPORTS_DIR / name).read_text(encoding='utf-8')
    assert committed == (fresh / name).read_text(encoding='utf-8'), (
        f'reports/{name} is stale; run `ou-sec all` (or `make all`) and commit the result')


def test_report_quotes_current_rate_tests(fresh):
    text = REPORT.read_text(encoding='utf-8')
    tests = pd.read_csv(fresh / 'title_rate_tests.csv')
    for _, r in tests.iterrows():
        row = (f"| {r['school']} | {r['baseline']} | {r['big12_rate_per_year']:.2f} | "
               f"{r['expected_titles_at_big12_rate']:.2f} | {r['observed_sec_titles']} | "
               f"{r['p_at_most_observed']:.2f} | {r['p_if_unknowns_were_titles']:.2f} |")
        assert row in text, f'report statistics table is missing or stale: {row}'


def test_report_quotes_current_peer_test_and_share(fresh):
    text = REPORT.read_text(encoding='utf-8')
    pt = pd.read_csv(fresh / 'peer_tests.csv').iloc[0]
    assert f"P(OU ≤ {pt['focus_observed']}) = {pt['p_focus_at_most_observed']:.2f}" in text
    assert f"{pt['p_if_focus_unknowns_were_titles']:.2f} if OU's two unknowns" in text
    share = pd.read_csv(fresh / 'big12_title_share_by_school.csv', index_col='champion')
    assert f"{int(share.loc['Oklahoma', 'titles'])} ({share.loc['Oklahoma', 'share']:.1%})" in text
    assert f"Texas ({int(share.loc['Texas', 'titles'])})" in text
    peers = pd.read_csv(fresh / 'peer_comparison.csv', index_col='school')
    ou = peers.loc['Oklahoma']
    assert f"{ou['sec_rate']:.1f} a year, against {ou['big12_rate_recent']:.2f}" in text
