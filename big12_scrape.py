import requests
import pandas as pd
from bs4 import BeautifulSoup

def scrape_big_12_championship_data(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Only select tables that have a caption containing 'titles by season'
    caption_tables = [table for table in soup.find_all('table') if table.caption and 'titles by season' in table.caption.text.lower()]

    def scrape_table(table):
        headers = [header.text.strip() for header in table.find_all('th')]
        all_data = []
        for row in table.find_all('tr')[1:]:
            cells = row.find_all('td')
            if cells:
                data = [cell.text.strip() for cell in cells]
                if len(data) == len(headers):
                    all_data.append(data)

        df = pd.DataFrame(all_data, columns=headers)
        table_title = table.caption.text.strip().replace('/', '_').replace(' ', '_')
        file_name = f'{table_title}.csv'
        df.to_csv(file_name, index=False)
        print(f'Data from "{table_title}" saved to {file_name}')

    for table in caption_tables:
        scrape_table(table)

if __name__ == '__main__':
    url = 'https://en.wikipedia.org/wiki/List_of_Big_12_Conference_champions'
    scrape_big_12_championship_data(url)

