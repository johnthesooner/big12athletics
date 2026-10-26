"""Guards against stale committed outputs and a report that drifts from the code."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ou_analysis as oa  # noqa: E402

REPORT = ROOT / 'reports' / 'OU_SEC_Performance.md'


@pytest.fixture(scope='module')
def fresh(tmp_path_factory):
    out = tmp_path_factory.mktemp('reports')
    assert oa.main(out) == 0
    return out


@pytest.mark.parametrize('name', [
    'ou_big12_titles_by_sport.csv', 'big12_title_share_by_school.csv',
    'ou_big12_comparable_titles_per_year.csv', 'ou_sec_comparable_titles_per_year.csv',
    'ou_sec_titles.csv', 'ou_sec_conference_win_pct.csv', 'ou_title_rate_test.csv',
])
def test_committed_csv_matches_regenerated(fresh, name):
    committed = (oa.REPORTS_DIR / name).read_text(encoding='utf-8')
    assert committed == (fresh / name).read_text(encoding='utf-8'), (
        f'reports/{name} is stale; run `python ou_analysis.py` and commit the result')


def test_report_quotes_current_numbers(fresh):
    text = REPORT.read_text(encoding='utf-8')
    tests = pd.read_csv(fresh / 'ou_title_rate_test.csv')
    for _, r in tests.iterrows():
        for value in (f"{r['big12_rate_per_year']:.2f}", f"{r['expected_titles_at_big12_rate']:.2f}",
                      f"{r['p_at_most_observed']:.2f}", f"{r['p_if_unknowns_were_titles']:.2f}"):
            assert value in text, f'report does not mention {value} from {r["baseline"]}'
    share = pd.read_csv(fresh / 'big12_title_share_by_school.csv', index_col='champion')
    assert f"{int(share.loc['Oklahoma', 'titles'])} ({share.loc['Oklahoma', 'share']:.1%})" in text
    assert f"Texas ({int(share.loc['Texas', 'titles'])})" in text
