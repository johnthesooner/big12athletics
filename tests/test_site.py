import pandas as pd
import pytest

from ou_sec import analysis as an
from ou_sec import config as cfg
from ou_sec import data as d
from ou_sec import site


@pytest.fixture(scope='module')
def inputs():
    titles, sec, cup = d.load_all()
    return an.build_summary(titles, sec), sec, cup


@pytest.fixture(scope='module')
def page(inputs, tmp_path_factory):
    out = tmp_path_factory.mktemp('site') / 'index.html'
    frag = out.with_name('fragment.html')
    site.build_site(*inputs, out=out, fragment_out=frag)
    return out.read_text(encoding='utf-8'), frag.read_text(encoding='utf-8')


def test_full_page_and_fragment_shapes(page):
    full, fragment = page
    assert full.startswith('<!doctype html>') and '</html>' in full
    assert '<html' not in fragment and fragment.startswith('<title>Sooners in the SEC</title>')
    assert full.count('<svg') == 3


def test_page_quotes_current_numbers(inputs, page):
    summary, _, _ = inputs
    full, _ = page
    peers = summary['peers'].set_index('school')
    ou = peers.loc['Oklahoma']
    assert f"{ou['sec_rate']:.1f} a year against {ou['big12_rate_recent']:.1f}" in full
    pt = summary['peer_tests'].iloc[0]
    assert f"{round(pt['p_focus_at_most_observed'] * 100)}% of the time</strong>" in full
    last_sec = summary['per_school']['Oklahoma']['sec_per_year'].index[-1]
    assert f'seasons through {last_sec}' in full


def test_every_source_is_linked(inputs, page):
    _, sec, cup = inputs
    full, _ = page
    for url in set(sec['source'].dropna()) | set(cup['source'].dropna()):
        assert f'href="{site.e(url)}"' in full


def test_data_text_is_escaped(inputs, tmp_path):
    summary, sec, cup = inputs
    evil = sec.copy()
    evil.loc[evil.index[0], 'ncaa_result'] = '<script>alert(1)</script>'
    out = site.build_site(summary, evil, cup, out=tmp_path / 'x.html')
    text = out.read_text(encoding='utf-8')
    assert '<script>alert(1)</script>' not in text
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in text


def test_unknown_title_flag_renders_as_unknown_chip():
    row = pd.Series({'reg_season_title': 'N', 'tourney_title': pd.NA, 'national_title': 'N',
                     'conf_finish': pd.NA, 'ncaa_result': pd.NA, 'confidence': 'low', 'source': pd.NA,
                     'conf_wins': pd.NA, 'conf_losses': pd.NA, 'conf_ties': pd.NA})
    cell = site.season_cell(row)
    assert 'SEC tournament: unknown' in cell and 'not found' in cell and 'low confidence' in cell


def test_cup_chart_breaks_line_at_missing_year():
    cup = pd.DataFrame({'academic_year': ['2021-22', '2022-23', '2023-24', '2024-25'],
                        'school': ['Oklahoma'] * 4, 'rank': pd.array([10, pd.NA, 24, 9], 'Int64')})
    svg = site.cup_chart(cup)
    assert svg.count('<polyline class="line ou"') == 1  # 2023-24 -> 2024-25 only; 2021-22 stands alone
    assert svg.count('class="dot ou"') == 3


def test_committed_site_is_current(inputs, tmp_path):
    out = site.build_site(*inputs, out=tmp_path / 'index.html')
    assert cfg.SITE_PATH.read_text(encoding='utf-8') == out.read_text(encoding='utf-8'), (
        'docs/index.html is stale; run `ou-sec all` (or `make all`) and commit the result')
