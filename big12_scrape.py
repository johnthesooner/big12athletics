import re
import sys
from pathlib import Path

import requests
import pandas as pd
from bs4 import BeautifulSoup

USER_AGENT = 'big12athletics-research/1.0 (https://github.com/johnthesooner/big12athletics)'
_CITATION = re.compile(r'\[[^\]]*\]')


def _cell_text(cell):
    return cell.get_text(' ', strip=True)


def table_file_stem(caption):
    """'Men's Tennis titles by season[18]' -> "Men's_Tennis_titles_by_season"."""
    title = _CITATION.sub('', caption).strip()
    return title.replace('/', '_').replace(' ', '_')


def parse_titles_table(table):
    """Parse one captioned table into (DataFrame, number of skipped rows).

    The header comes from the first row only, and body rows read both <th>
    and <td> cells, because Wikipedia often marks the season as a row header.
    Rows whose cell count differs from the header (rowspan/colspan, merged
    co-champion cells) are skipped and counted, never silently dropped.
    """
    rows = table.find_all('tr')
    if not rows:
        return pd.DataFrame(), 0
    headers = [_cell_text(c) for c in rows[0].find_all(['th', 'td'])]
    data, skipped = [], 0
    for row in rows[1:]:
        cells = [_cell_text(c) for c in row.find_all(['th', 'td'])]
        if not cells:
            continue
        if len(cells) == len(headers):
            data.append(cells)
        else:
            skipped += 1
    return pd.DataFrame(data, columns=headers), skipped


def find_titles_tables(html):
    """Tables whose caption contains 'titles by season'."""
    soup = BeautifulSoup(html, 'html.parser')
    return [t for t in soup.find_all('table')
            if t.caption and 'titles by season' in t.caption.get_text().lower()]


def scrape_big_12_championship_data(url, output_dir='Championships by Season'):
    """Save every 'titles by season' table on a Wikipedia champions page as CSV.

    Works for any conference's 'List of ... champions' page (see sec_scrape.py).
    Returns the list of files written. An empty table never overwrites an
    existing CSV.
    """
    output_dir = Path(output_dir)
    response = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=30)
    response.raise_for_status()
    tables = find_titles_tables(response.text)
    if not tables:
        raise RuntimeError(f"No 'titles by season' tables found at {url}; the page layout may have changed")

    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for table in tables:
        stem = table_file_stem(table.caption.get_text())
        df, skipped = parse_titles_table(table)
        if skipped:
            print(f'WARNING: {stem}: skipped {skipped} row(s) with irregular cell counts '
                  '(likely merged/co-champion cells); review manually', file=sys.stderr)
        if df.empty:
            print(f'WARNING: {stem}: no rows parsed; not writing', file=sys.stderr)
            continue
        file_name = output_dir / f'{stem}.csv'
        df.to_csv(file_name, index=False)
        written.append(file_name)
        print(f'Data from "{stem}" saved to {file_name}')
    return written


if __name__ == '__main__':
    url = 'https://en.wikipedia.org/wiki/List_of_Big_12_Conference_champions'
    scrape_big_12_championship_data(url)
