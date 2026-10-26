from big12_scrape import scrape_big_12_championship_data

# Untested against the live page: this repo's build environment could not
# reach Wikipedia. If no files are written, check the table captions.
if __name__ == '__main__':
    url = 'https://en.wikipedia.org/wiki/List_of_Southeastern_Conference_champions'
    scrape_big_12_championship_data(url, output_dir='SEC Championships by Season')
