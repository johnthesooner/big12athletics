import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import big12_scrape as bs  # noqa: E402

PAGE = """
<html><body>
<table><caption>Softball titles by season[3]</caption>
  <tr><th>Season</th><th>Regular Season</th><th>Tournament</th></tr>
  <tr><th scope="row">2022</th><td>Oklahoma</td><td>Oklahoma State</td></tr>
  <tr><td>2023</td><td>Oklahoma<sup>†</sup></td><td>Oklahoma</td></tr>
  <tr><td>2024</td><td colspan="2">Oklahoma</td></tr>
</table>
<table><caption>Empty titles by season</caption><tr><th>Season</th></tr></table>
<table><caption>Conference membership</caption><tr><th>School</th></tr><tr><td>Texas</td></tr></table>
</body></html>
"""


class FakeResponse:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')


def test_table_file_stem_strips_citations():
    assert bs.table_file_stem("Men's Tennis titles by season[18]") == "Men's_Tennis_titles_by_season"
    assert bs.table_file_stem('Track/Field titles by season') == 'Track_Field_titles_by_season'


def test_only_titles_tables_selected():
    assert len(bs.find_titles_tables(PAGE)) == 2


def test_row_header_cells_are_kept_and_irregular_rows_counted():
    df, skipped = bs.parse_titles_table(bs.find_titles_tables(PAGE)[0])
    assert list(df.columns) == ['Season', 'Regular Season', 'Tournament']
    assert df['Season'].tolist() == ['2022', '2023']  # <th scope=row> season kept
    assert skipped == 1  # colspan row reported, not silently dropped


def test_scrape_writes_files_and_skips_empty(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(bs.requests, 'get', lambda url, **kw: FakeResponse(PAGE))
    written = bs.scrape_big_12_championship_data('https://example.org', tmp_path)
    assert [p.name for p in written] == ['Softball_titles_by_season.csv']
    out = pd.read_csv(written[0], dtype=str)
    assert out.loc[1, 'Regular Season'] == 'Oklahoma †'
    err = capsys.readouterr().err
    assert 'skipped 1 row' in err and 'no rows parsed' in err


def test_empty_table_does_not_overwrite_existing_file(tmp_path, monkeypatch):
    existing = tmp_path / 'Empty_titles_by_season.csv'
    existing.write_text('keep me')
    monkeypatch.setattr(bs.requests, 'get', lambda url, **kw: FakeResponse(PAGE))
    bs.scrape_big_12_championship_data('https://example.org', tmp_path)
    assert existing.read_text() == 'keep me'


def test_page_without_tables_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(bs.requests, 'get', lambda url, **kw: FakeResponse('<html></html>'))
    with pytest.raises(RuntimeError, match='layout may have changed'):
        bs.scrape_big_12_championship_data('https://example.org', tmp_path)


def test_http_error_propagates(tmp_path, monkeypatch):
    monkeypatch.setattr(bs.requests, 'get', lambda url, **kw: FakeResponse('', status=503))
    with pytest.raises(RuntimeError, match='503'):
        bs.scrape_big_12_championship_data('https://example.org', tmp_path)
