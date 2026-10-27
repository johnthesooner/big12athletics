import pandas as pd
import pytest

from ou_sec import analysis as an
from ou_sec import config as cfg
from ou_sec import data as d

SUPP_HEADER = ','.join(cfg.SUPPLEMENT_COLUMNS)


@pytest.fixture
def big12_dir(tmp_path):
    directory = tmp_path / 'big12'
    directory.mkdir()
    for sport, columns in cfg.COMPARABLE_TITLES.items():
        frame = pd.DataFrame({'Season': ['2021'], **{c: ['Texas'] for c in columns}})
        frame.to_csv(directory / f"{sport.replace(' ', '_')}_titles_by_season.csv", index=False)
    return directory


def write_supp(tmp_path, *rows):
    path = tmp_path / 'supp.csv'
    path.write_text('\n'.join([SUPP_HEADER, *rows]) + '\n', encoding='utf-8')
    return path


GOOD = 'Softball,2024,Tournament,Oklahoma,N,high,https://x.org,'


# ---------------------------------------------------------------- Big 12 supplement

def test_supplement_fills_missing_season(big12_dir, tmp_path):
    titles = d.load_big12_titles(big12_dir, write_supp(tmp_path, GOOD))
    row = titles[(titles['Season'] == '2024') & (titles['sport'] == 'Softball')]
    assert row['champion'].tolist() == ['Oklahoma']
    assert row['origin'].tolist() == ['supplement']


def test_supplement_credits_every_co_champion(big12_dir, tmp_path):
    supp = write_supp(tmp_path, 'Softball,2024,Regular Season,Texas; Oklahoma,Y,high,https://x.org,')
    titles = d.load_big12_titles(big12_dir, supp)
    shared = titles[(titles['Season'] == '2024')]
    assert set(shared['champion']) == {'Texas', 'Oklahoma'}
    assert shared['shared'].all()


def test_missing_supplement_file_is_fine(big12_dir, tmp_path):
    assert len(d.load_big12_titles(big12_dir, tmp_path / 'nope.csv'))


@pytest.mark.parametrize('row, message', [
    (GOOD.replace('2024', '2021'), 'only fill gaps'),
    (GOOD.replace('Tournament', 'Playoff'), 'unknown sport/column'),
    (GOOD.replace(',high,', ',sure,'), 'confidence'),
    (GOOD.replace('https://x.org', 'x.org'), 'https'),
    (GOOD.replace(',N,', ',maybe,'), 'shared must be'),
    (GOOD.replace('Oklahoma,N', 'Oklahoma; Texas,N'), 'shared=N'),
    (GOOD.replace('2024', '24'), '4-digit'),
])
def test_bad_supplement_rows_rejected(big12_dir, tmp_path, row, message):
    with pytest.raises(d.DataValidationError, match=message):
        d.load_big12_titles(big12_dir, write_supp(tmp_path, row))


def test_duplicate_supplement_rows_rejected(big12_dir, tmp_path):
    with pytest.raises(d.DataValidationError, match='duplicate row'):
        d.load_big12_titles(big12_dir, write_supp(tmp_path, GOOD, GOOD))


# ---------------------------------------------------------------- peers

def test_school_basket_drops_sports_school_does_not_play():
    sec = pd.DataFrame({'school': ['Texas', 'Texas'], 'sport': ['Softball', 'Football']})
    assert list(an.school_basket(sec, 'Texas')) == ['Softball']


def test_comparable_sec_titles_filters_by_school():
    sec = pd.DataFrame([
        {'school': 'Oklahoma', 'academic_year': '2024-25', 'sport': 'Softball',
         'reg_season_title': 'Y', 'tourney_title': 'N'},
        {'school': 'Texas', 'academic_year': '2024-25', 'sport': 'Softball',
         'reg_season_title': 'Y', 'tourney_title': 'Y'},
    ])
    assert an.comparable_sec_titles(sec, 'Oklahoma')['won'].sum() == 1
    assert an.comparable_sec_titles(sec, 'Texas')['won'].sum() == 2


def test_binomial_cdf():
    assert an.binomial_cdf(3, 8, 0.5) == pytest.approx(93 / 256)
    assert an.binomial_cdf(8, 8, 0.3) == pytest.approx(1.0)


def test_peer_rate_test_equal_baselines():
    result = an.peer_rate_test({'school': 'A', 'observed': 3, 'expected': 4.8},
                               {'school': 'B', 'observed': 5, 'expected': 4.8}, focus_unknown=2)
    assert result['expected_focus_share'] == 0.5
    assert result['p_focus_at_most_observed'] == pytest.approx(93 / 256, abs=1e-4)
    assert result['p_if_focus_unknowns_were_titles'] > result['p_focus_at_most_observed']


def test_peer_rate_test_scales_by_baseline():
    # Focus expected to win 3x as many: matching the peer is a big shortfall.
    result = an.peer_rate_test({'school': 'A', 'observed': 2, 'expected': 6.0},
                               {'school': 'B', 'observed': 2, 'expected': 2.0})
    assert result['expected_focus_share'] == 0.75
    assert result['p_focus_at_most_observed'] < 0.27


def test_summary_includes_peer_tests_for_committed_data():
    titles, sec, _ = d.load_all()
    summary = an.build_summary(titles, sec)
    assert summary['schools'] == ['Oklahoma', 'Texas']
    assert summary['peer_tests'].loc[0, 'peer'] == 'Texas'
    assert 'Women\'s Gymnastics' not in summary['per_school']['Texas']['basket']
