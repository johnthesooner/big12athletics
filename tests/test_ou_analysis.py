import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ou_analysis as oa  # noqa: E402


@pytest.mark.parametrize('raw, expected', [
    ('Baylor†', 'Baylor'),
    ('—[a]', '—'),
    ('Oklahoma State', 'Oklahoma State'),
    (float('nan'), ''),
])
def test_clean_team(raw, expected):
    assert oa.clean_team(raw) == expected


def test_sport_from_filename_strips_citation_suffix():
    assert oa.sport_from_filename("Men's_Tennis_titles_by_season[18].csv") == "Men's Tennis"


def test_academic_year_fall_vs_spring():
    assert oa.academic_year('Volleyball', '2022') == '2022-23'
    assert oa.academic_year('Softball', '2023') == '2022-23'


def test_oklahoma_state_is_not_counted_as_oklahoma(tmp_path):
    pd.DataFrame({'Season': ['2020', '2021', '2022'],
                  'Champion': ['Oklahoma State', 'Oklahoma†', '—']}).to_csv(
        tmp_path / 'Wrestling_titles_by_season.csv', index=False)
    titles = oa.load_big12_titles(tmp_path)
    assert len(titles) == 2  # placeholder dash dropped
    ou = titles[titles['champion'] == 'Oklahoma']
    assert ou['academic_year'].tolist() == ['2020-21']
    assert ou['shared'].tolist() == [True]


def test_comparable_basket_ignores_non_basket_sports(tmp_path):
    pd.DataFrame({'Season': ['2021'], 'Champion': ['Oklahoma']}).to_csv(
        tmp_path / 'Wrestling_titles_by_season.csv', index=False)
    pd.DataFrame({'Season': ['2021'], 'Regular Season': ['Oklahoma'], 'Tournament': ['Texas']}).to_csv(
        tmp_path / 'Softball_titles_by_season.csv', index=False)
    per_year = oa.comparable_big12_titles(oa.load_big12_titles(tmp_path))
    assert per_year.to_dict() == {'2020-21': 1}


def test_sec_gymnastics_regular_season_title_excluded_from_basket():
    sec = pd.DataFrame([{'academic_year': '2025-26', 'sport': "Women's Gymnastics",
                         'reg_season_title': 'Y', 'tourney_title': 'N'}])
    basket = oa.comparable_sec_titles(sec)
    assert basket['won'].sum() == 0
    assert len(oa.all_sec_titles(sec)) == 1


def test_shared_counts_as_title():
    assert oa.is_title('shared') and oa.is_title('Y')
    assert not oa.is_title('N') and not oa.is_title(float('nan'))


def test_poisson_cdf_matches_closed_form():
    assert oa.poisson_cdf(0, 2.0) == pytest.approx(0.135335, rel=1e-5)
    assert oa.poisson_cdf(50, 2.0) == pytest.approx(1.0)


def test_curated_sec_data_is_well_formed():
    sec = oa.load_sec_results()
    assert set(sec['confidence']) <= {'high', 'medium', 'low', 'missing'}
    flags = sec[['reg_season_title', 'tourney_title']].stack().dropna().str.lower()
    assert set(flags) <= {'y', 'n', 'shared'}
    sourced = sec[sec['confidence'] != 'missing']
    assert sourced['source'].str.startswith('https://').all()
    assert not sec.duplicated(['academic_year', 'sport']).any()
