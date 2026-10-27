import pandas as pd
import pytest

from ou_sec import analysis as an
from ou_sec import config as cfg
from ou_sec import data as d

SEC_HEADER = ','.join(cfg.SEC_COLUMNS)
GOOD_SEC_ROW = "Oklahoma,2024-25,Softball,17,7,0,1st,Y,shared,WCWS,N,high,https://example.com,"


def write_sec(tmp_path, *rows):
    path = tmp_path / 'sec.csv'
    path.write_text('\n'.join([SEC_HEADER, *rows]) + '\n', encoding='utf-8')
    return path


def write_big12(directory, name, frame):
    frame.to_csv(directory / f'{name}_titles_by_season.csv', index=False)


@pytest.fixture
def big12_dir(tmp_path):
    """Minimal Big 12 directory with every comparable sport/column present."""
    d = tmp_path / 'big12'
    d.mkdir()
    for sport, columns in cfg.COMPARABLE_TITLES.items():
        frame = pd.DataFrame({'Season': ['2021'], **{c: ['Texas'] for c in columns}})
        write_big12(d, sport.replace(' ', '_'), frame)
    return d


# ---------------------------------------------------------------- parsing helpers

@pytest.mark.parametrize('raw, expected', [
    ('Baylor†', 'Baylor'),
    ('—[a]', '—'),
    ('Oklahoma State', 'Oklahoma State'),
    (float('nan'), ''),
])
def test_clean_team(raw, expected):
    assert d.clean_team(raw) == expected


@pytest.mark.parametrize('raw', ['Regular season', 'regular  Season ', 'REGULAR SEASON'])
def test_normalize_title_type(raw):
    assert d.normalize_title_type(raw) == 'Regular Season'


def test_sport_from_filename_strips_citation_suffix():
    assert d.sport_from_filename("Men's_Tennis_titles_by_season[18].csv") == "Men's Tennis"
    assert d.sport_from_filename("Men's_Tennis_titles_by_season.csv") == "Men's Tennis"


def test_academic_year_fall_vs_spring():
    assert d.academic_year('Volleyball', '2022') == '2022-23'
    assert d.academic_year('Softball', '2023') == '2022-23'
    assert d.academic_year('Volleyball', '1999') == '1999-00'


@pytest.mark.parametrize('label, ok', [('2024-25', True), ('1999-00', True), ('2024-26', False),
                                       ('2024', False), ('24-25', False)])
def test_is_academic_year(label, ok):
    assert d.is_academic_year(label) is ok


def test_year_range_fills_gaps():
    assert d.year_range('2021-22', '2024-25') == ['2021-22', '2022-23', '2023-24', '2024-25']


# ---------------------------------------------------------------- Big 12 loading

def test_oklahoma_state_is_not_counted_as_oklahoma(big12_dir):
    write_big12(big12_dir, 'Wrestling', pd.DataFrame({
        'Season': ['2020', '2021', '2022'], 'Champion': ['Oklahoma State', 'Oklahoma†', '—']}))
    titles = d.load_big12_titles(big12_dir)
    ou = titles[titles['champion'] == 'Oklahoma']
    assert ou['academic_year'].tolist() == ['2020-21']
    assert ou['shared'].tolist() == [True]
    assert '—' not in set(titles['champion'])


def test_header_capitalization_is_normalized(big12_dir):
    write_big12(big12_dir, "Men's_Basketball", pd.DataFrame({
        'Season': ['2021'], 'Regular season': ['Oklahoma'], 'TOURNAMENT': ['Oklahoma']}))
    per_year = an.comparable_big12_titles(d.load_big12_titles(big12_dir))
    assert per_year['2020-21'] == 2


def test_duplicate_sport_files_rejected(big12_dir):
    frame = pd.DataFrame({'Season': ['2021'], 'Regular Season': ['Texas'], 'Tournament': ['Texas']})
    frame.to_csv(big12_dir / "Men's_Tennis_titles_by_season.csv", index=False)
    frame.to_csv(big12_dir / "Men's_Tennis_titles_by_season[18].csv", index=False)
    with pytest.raises(d.DataValidationError, match='duplicate'):
        d.load_big12_titles(big12_dir)


def test_missing_comparable_column_rejected(big12_dir):
    write_big12(big12_dir, 'Softball', pd.DataFrame({'Season': ['2021'], 'Regular Season': ['Texas']}))
    with pytest.raises(d.DataValidationError, match="Softball.*Tournament"):
        d.load_big12_titles(big12_dir)


def test_non_numeric_season_rejected(big12_dir):
    write_big12(big12_dir, 'Wrestling', pd.DataFrame({'Season': ['2021', 'TBD'], 'Champion': ['Iowa', 'x']}))
    with pytest.raises(d.DataValidationError, match="non-numeric Season 'TBD'"):
        d.load_big12_titles(big12_dir)


def test_empty_directory_rejected(tmp_path):
    with pytest.raises(d.DataValidationError, match='no CSV'):
        d.load_big12_titles(tmp_path)


def test_early_softball_season_counted_but_not_in_baseline(big12_dir):
    write_big12(big12_dir, 'Softball', pd.DataFrame({
        'Season': ['1996', '1997'], 'Regular Season': ['Oklahoma', 'Oklahoma'], 'Tournament': ['x', 'x']}))
    titles = d.load_big12_titles(big12_dir)
    assert '1995-96' in set(titles['academic_year'])           # title still credited
    per_year = an.comparable_big12_titles(titles)
    assert per_year.index.min() == cfg.FIRST_FULL_BIG12_YEAR   # but baseline starts at 1996-97


def test_comparable_basket_ignores_non_basket_sports(big12_dir):
    write_big12(big12_dir, 'Wrestling', pd.DataFrame({'Season': ['2021'], 'Champion': ['Oklahoma']}))
    write_big12(big12_dir, 'Softball', pd.DataFrame({
        'Season': ['2021'], 'Regular Season': ['Oklahoma'], 'Tournament': ['Texas']}))
    per_year = an.comparable_big12_titles(d.load_big12_titles(big12_dir))
    assert per_year['2020-21'] == 1
    assert per_year.sum() == 1  # wrestling title not counted


# ---------------------------------------------------------------- SEC validation

def test_good_sec_row_loads(tmp_path):
    sec = d.load_sec_results(write_sec(tmp_path, GOOD_SEC_ROW))
    assert sec.loc[0, 'conf_wins'] == 17
    assert sec.loc[0, 'tourney_title'] == 'shared'


@pytest.mark.parametrize('row, message', [
    (GOOD_SEC_ROW.replace('Softball', 'Sofball'), 'unknown sport'),
    (GOOD_SEC_ROW.replace(',Y,shared,', ',Yes,shared,'), "reg_season_title='Yes'"),
    (GOOD_SEC_ROW.replace('2024-25', '2023-24'), 'bad academic_year'),
    (GOOD_SEC_ROW.replace('2024-25', '2024-26'), 'bad academic_year'),
    (GOOD_SEC_ROW.replace(',17,7,', ',seventeen,7,'), "conf_wins='seventeen' is not an integer"),
    (GOOD_SEC_ROW.replace(',17,7,', ',-1,7,'), 'conf_wins is negative'),
    (GOOD_SEC_ROW.replace(',17,7,', ',17,,'), 'both be set'),
    (GOOD_SEC_ROW.replace(',high,', ',sure,'), 'confidence must be'),
    (GOOD_SEC_ROW.replace('https://example.com', 'example.com'), 'https:// source'),
    (GOOD_SEC_ROW.replace(',WCWS,N,', ',WCWS,maybe,'), 'national_title'),
])
def test_bad_sec_rows_rejected(tmp_path, row, message):
    with pytest.raises(d.DataValidationError, match=message):
        d.load_sec_results(write_sec(tmp_path, row))


def test_duplicate_sec_rows_rejected(tmp_path):
    with pytest.raises(d.DataValidationError, match='duplicate row'):
        d.load_sec_results(write_sec(tmp_path, GOOD_SEC_ROW, GOOD_SEC_ROW))


def test_missing_sec_column_rejected(tmp_path):
    path = tmp_path / 'sec.csv'
    path.write_text('academic_year,sport\n2024-25,Softball\n')
    with pytest.raises(d.DataValidationError, match='missing column'):
        d.load_sec_results(path)


def test_validation_reports_every_problem(tmp_path):
    bad = GOOD_SEC_ROW.replace('Softball', 'Sofball').replace(',high,', ',sure,')
    with pytest.raises(d.DataValidationError) as err:
        d.load_sec_results(write_sec(tmp_path, bad))
    assert len(err.value.problems) == 2


def test_dash_flag_is_not_read_as_missing(tmp_path):
    row = GOOD_SEC_ROW.replace('Softball', 'Volleyball').replace(',Y,shared,', ',N,-,')
    sec = d.load_sec_results(write_sec(tmp_path, row))
    assert sec.loc[0, 'tourney_title'] == '-'


# ---------------------------------------------------------------- SEC analysis

@pytest.mark.parametrize('flag, expected', [('Y', True), ('shared', True), ('SHARED ', True),
                                            ('N', False), ('-', False)])
def test_title_status(flag, expected):
    assert an.title_status(flag) is expected


def test_title_status_unknown_is_na():
    assert an.title_status(pd.NA) is pd.NA
    assert an.title_status(float('nan')) is pd.NA
    assert not an.is_title(pd.NA)


def test_unknown_outcomes_are_counted_not_scored_as_losses():
    sec = pd.DataFrame([
        {'academic_year': '2024-25', 'sport': "Women's Soccer", 'reg_season_title': 'N', 'tourney_title': pd.NA},
        {'academic_year': '2024-25', 'sport': 'Softball', 'reg_season_title': 'Y', 'tourney_title': 'shared'},
    ])
    per_year = an.sec_titles_per_year(an.comparable_sec_titles(sec))
    assert per_year.loc['2024-25'].to_dict() == {'titles': 2, 'unknown': 1}


def test_sec_gymnastics_regular_season_title_excluded_from_basket():
    sec = pd.DataFrame([{'academic_year': '2025-26', 'sport': "Women's Gymnastics",
                         'reg_season_title': 'Y', 'tourney_title': 'N'}])
    assert an.comparable_sec_titles(sec)['won'].sum() == 0
    assert len(an.all_sec_titles(sec)) == 1


def test_football_titles_outside_basket_still_listed():
    sec = pd.DataFrame([{'academic_year': '2025-26', 'sport': 'Football',
                         'reg_season_title': 'N', 'tourney_title': 'Y'}])
    assert an.comparable_sec_titles(sec).empty
    assert an.all_sec_titles(sec)['sport'].tolist() == ['Football']


def test_all_sec_titles_empty_has_columns():
    sec = pd.DataFrame([{'academic_year': '2025-26', 'sport': 'Football',
                         'reg_season_title': 'N', 'tourney_title': 'N'}])
    assert list(an.all_sec_titles(sec).columns) == ['school', 'academic_year', 'sport', 'title_type', 'shared']


def test_conference_win_pct_counts_ties_as_half():
    sec = pd.DataFrame({'academic_year': ['2025-26'], 'sport': ["Women's Soccer"],
                        'conf_wins': pd.array([3], 'Int64'), 'conf_losses': pd.array([4], 'Int64'),
                        'conf_ties': pd.array([3], 'Int64'), 'confidence': ['medium']})
    assert an.conference_win_pct(sec).loc[0, 'conf_win_pct'] == pytest.approx(0.45)


def test_conference_win_pct_skips_unknown_records():
    sec = pd.DataFrame({'academic_year': ['2024-25'], 'sport': ["Women's Soccer"],
                        'conf_wins': pd.array([pd.NA], 'Int64'), 'conf_losses': pd.array([pd.NA], 'Int64'),
                        'conf_ties': pd.array([pd.NA], 'Int64'), 'confidence': ['low']})
    assert an.conference_win_pct(sec).empty


# ---------------------------------------------------------------- statistics

def test_poisson_cdf_matches_closed_form():
    assert an.poisson_cdf(0, 2.0) == pytest.approx(0.135335, rel=1e-5)
    assert an.poisson_cdf(1, 2.0) == pytest.approx(0.406006, rel=1e-5)
    assert an.poisson_cdf(50, 2.0) == pytest.approx(1.0)
    assert an.poisson_cdf(-1, 2.0) == 0.0


def test_title_rate_test_bounds_unknowns():
    result = an.title_rate_test(pd.Series([2, 2]), sec_titles=3, sec_years=2, unknown=2)
    assert result['expected_titles_at_big12_rate'] == 4.0
    assert result['p_at_most_observed'] < result['p_if_unknowns_were_titles']


def test_title_rate_test_rejects_empty_inputs():
    with pytest.raises(ValueError):
        an.title_rate_test(pd.Series([], dtype=int), 1, 2)
    with pytest.raises(ValueError):
        an.title_rate_test(pd.Series([1]), 1, 0)


# ---------------------------------------------------------------- Directors' Cup

def test_directors_cup_rejects_missing_rank(tmp_path):
    path = tmp_path / 'cup.csv'
    path.write_text(','.join(cfg.CUP_COLUMNS) + '\n2024-25,Oklahoma,SEC,,high,https://x\n')
    with pytest.raises(d.DataValidationError, match='rank must be'):
        d.load_directors_cup(path)


def test_directors_cup_allows_missing_rank_when_flagged(tmp_path):
    path = tmp_path / 'cup.csv'
    path.write_text(','.join(cfg.CUP_COLUMNS) + '\n2022-23,Oklahoma,Big 12,,missing,\n')
    assert d.load_directors_cup(path)['rank'].isna().all()


# ---------------------------------------------------------------- end to end

def test_committed_data_loads_and_validates():
    titles, sec, cup = d.load_all()
    assert len(titles) and len(cup)
    assert set(sec['academic_year']) == {'2024-25', '2025-26'}
    assert {'Oklahoma', 'Texas'} <= set(sec['school'])
    assert titles['academic_year'].max() == '2023-24'  # supplement backfills OU's last Big 12 year


def test_cli_report_writes_all_outputs(tmp_path):
    from ou_sec import cli
    from ou_sec.reports import CHARTS, TABLES
    assert cli.main(['report', '--out', str(tmp_path), '--quiet']) == 0
    assert set(TABLES + CHARTS) <= {p.name for p in tmp_path.iterdir()}


def test_cli_exits_1_on_bad_input(tmp_path, monkeypatch, capsys):
    from ou_sec import cli
    monkeypatch.setattr(cfg, 'SEC_RESULTS', write_sec(tmp_path, GOOD_SEC_ROW.replace('Softball', 'Sofball')))
    with pytest.raises(SystemExit) as exc:
        cli.main(['report', '--out', str(tmp_path / 'out')])
    assert exc.value.code == 1
    assert 'unknown sport' in capsys.readouterr().err
    assert not (tmp_path / 'out').exists()


def test_cli_validate(capsys):
    from ou_sec import cli
    assert cli.main(['validate']) == 0
    assert 'OK:' in capsys.readouterr().out
