"""Paths and domain constants shared by every module."""
import os
from pathlib import Path

# Repo root: src/ou_sec/config.py -> parents[2]. OU_SEC_ROOT overrides it so an
# installed copy of the package can still point at a checkout's data.
ROOT = Path(os.environ.get('OU_SEC_ROOT', Path(__file__).resolve().parents[2]))
DATA_DIR = ROOT / 'data'
BIG12_DIR = DATA_DIR / 'raw' / 'big12_champions'
BIG12_SUPPLEMENT = DATA_DIR / 'curated' / 'big12_supplement.csv'
SEC_RESULTS = DATA_DIR / 'curated' / 'sec_results.csv'
DIRECTORS_CUP = DATA_DIR / 'curated' / 'directors_cup.csv'
REPORTS_DIR = ROOT / 'reports'
SITE_PATH = ROOT / 'docs' / 'index.html'

FOCUS_SCHOOL = 'Oklahoma'
PEER_SCHOOLS = ('Texas',)          # joined the SEC on the same day: natural control
# First full Big 12 year. Softball held a Big 12 season a year early (spring
# 1996): those titles count, but the per-year baseline starts here so a
# softball-only year does not distort the average.
FIRST_FULL_BIG12_YEAR = '1996-97'
FIRST_SEC_YEAR = '2024-25'
RECENT_YEARS = 5

# Sports whose Big 12 "Season" label is the fall calendar year (e.g. volleyball
# "2022" = the 2022-23 academic year). All others are labelled by spring year.
FALL_SPORTS = {'Volleyball', "Women's Soccer", "Men's Cross Country", 'Football'}

# Sports played in both conferences, mapping each Big 12 table column to the
# equivalent SEC title field. Gymnastics maps the Big 12 meet champion to the
# SEC Championships meet, not the SEC regular-season title (a concept the
# Big 12 table does not track), so the comparison stays like-for-like.
COMPARABLE_TITLES = {
    'Baseball': {'Regular Season': 'reg_season_title', 'Tournament': 'tourney_title'},
    'Softball': {'Regular Season': 'reg_season_title', 'Tournament': 'tourney_title'},
    "Men's Basketball": {'Regular Season': 'reg_season_title', 'Tournament': 'tourney_title'},
    "Women's Basketball": {'Regular Season': 'reg_season_title', 'Tournament': 'tourney_title'},
    "Women's Soccer": {'Regular Season': 'reg_season_title', 'Tournament': 'tourney_title'},
    'Volleyball': {'Champion': 'reg_season_title'},
    "Women's Gymnastics": {'Champion': 'tourney_title'},
}
SEC_SPORTS = set(COMPARABLE_TITLES) | {'Football'}

# SEC title flags. Blank means unknown; '-' means no such event was held.
TITLE_FLAGS = {'y', 'shared'}
NO_TITLE_FLAGS = {'n', '-'}
CONFIDENCE_LEVELS = {'high', 'medium', 'low', 'missing'}

SEC_COLUMNS = ['school', 'academic_year', 'sport', 'conf_wins', 'conf_losses', 'conf_ties',
               'conf_finish', 'reg_season_title', 'tourney_title', 'ncaa_result', 'national_title',
               'confidence', 'source', 'notes']
SEC_INT_COLUMNS = ('conf_wins', 'conf_losses', 'conf_ties')
CUP_COLUMNS = ['academic_year', 'school', 'conference', 'rank', 'confidence', 'source']
SUPPLEMENT_COLUMNS = ['sport', 'season_label', 'column', 'champion', 'shared',
                      'confidence', 'source_url', 'notes']

SCHOOL_COLORS = {'Oklahoma': '#841617', 'Texas': '#bf5700', 'Oklahoma State': '#5c5c5c'}
