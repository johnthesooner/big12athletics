"""Command-line entry point: ``ou-sec <command>`` (or ``python -m ou_sec``)."""
import argparse
import sys
from pathlib import Path

import pandas as pd

from . import config as cfg
from .analysis import build_summary
from .data import DataValidationError, load_all


def _load_or_exit():
    try:
        return load_all()
    except DataValidationError as err:
        print(f'Input validation failed:\n{err}', file=sys.stderr)
        raise SystemExit(1) from None


def cmd_validate(args):
    titles, sec, cup = _load_or_exit()
    print(f'OK: {len(titles)} Big 12 title rows (through {titles["academic_year"].max()}), '
          f'{len(sec)} SEC rows for {sorted(sec["school"].unique())}, {len(cup)} Directors\' Cup rows')
    coverage = sec.groupby(['school', 'confidence']).size().unstack(fill_value=0)
    print('\nSEC row confidence by school:\n' + coverage.to_string())
    return 0


def cmd_report(args):
    from .reports import write_reports
    titles, sec, cup = _load_or_exit()
    summary = build_summary(titles, sec)
    written = write_reports(summary, cup, args.out)
    if not args.quiet:
        pd.set_option('display.width', 160)
        print('Title-rate check (comparable basket):')
        print(summary['rate_tests'].to_string(index=False))
        print('\nPeer comparison (titles per year):')
        print(summary['peers'].to_string(index=False))
        print('\nOU vs peer (exact conditional Poisson test):')
        print(summary['peer_tests'].to_string(index=False))
        print(f'\nWrote {len(written)} files to {args.out}')
    return 0


def cmd_site(args):
    from .site import build_site
    titles, sec, cup = _load_or_exit()
    path = build_site(build_summary(titles, sec), sec, cup, args.out, getattr(args, 'fragment', None))
    print(f'Wrote {path}')
    return 0


def cmd_scrape(args):
    from .scrape import SOURCES, scrape_champions
    url, default_dir = SOURCES[args.source]
    scrape_champions(url, args.out or default_dir)
    return 0


def cmd_all(args):
    args.quiet = True
    for cmd, out in ((cmd_report, cfg.REPORTS_DIR), (cmd_site, cfg.SITE_PATH)):
        args.out = out
        cmd(args)
    print(f'Reports in {cfg.REPORTS_DIR}, site at {cfg.SITE_PATH}')
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog='ou-sec', description=(
        "Oklahoma's move from the Big 12 to the SEC: validate data, build reports and the story site."))
    sub = parser.add_subparsers(dest='command', required=True)

    sub.add_parser('validate', help='check every input file and print coverage').set_defaults(func=cmd_validate)

    p = sub.add_parser('report', help='write tables and charts to reports/')
    p.add_argument('--out', type=Path, default=cfg.REPORTS_DIR)
    p.add_argument('--quiet', action='store_true')
    p.set_defaults(func=cmd_report)

    p = sub.add_parser('site', help='build the self-contained story page (docs/index.html)')
    p.add_argument('--out', type=Path, default=cfg.SITE_PATH)
    p.add_argument('--fragment', type=Path, default=None,
                   help='also write the page without the <html>/<head> wrapper (for embedding/hosting)')
    p.set_defaults(func=cmd_site)

    p = sub.add_parser('scrape', help='re-scrape Wikipedia champions tables (needs network)')
    p.add_argument('source', choices=['big12', 'sec'])
    p.add_argument('--out', type=Path, default=None)
    p.set_defaults(func=cmd_scrape)

    sub.add_parser('all', help='report + site').set_defaults(func=cmd_all)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
