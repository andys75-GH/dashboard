"""Nightly tidy-up of the GTab history files (run by .github/workflows/trim-gtab.yml).

Keeps each file to a rolling window of recent days so it stays well under GitHub's 1 MB
API limit (the Power Automate flows can't read files bigger than that).

Before a day is dropped, every club listed in it is recorded in data/gtab_clubs.json
with the last date it was seen. The dashboard uses that list so a club that has been
missing from the emails for a long time keeps showing as missing until someone removes
it by hand - trimming never removes a club on its own.
"""
import json
import os
from datetime import date, timedelta

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')

# file -> days of reports to keep, and the first date its reports listed every club
FILES = {
    'gtab':         {'keep_days': 30, 'full_from': '2026-10-01'},
    'gtab_merkur1': {'keep_days': 45, 'full_from': '2026-10-04'},
    'gtab_tardis':  {'keep_days': 90, 'full_from': ''},
    'gtab_groups':  {'keep_days': 90, 'full_from': ''},
}
CLUBS = os.path.join(DATA, 'gtab_clubs.json')


def load(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, separators=(',', ':'), ensure_ascii=False)


def club_key(entry, site):
    # Group/brand + number + name: enough to tell twin rooms and same-named clubs apart
    return '|'.join(str(x) for x in (entry.get('group', ''), entry.get('brand', ''), site.get('id', ''), site.get('name', '')))


def main():
    clubs = load(CLUBS, {})
    changed = False
    for name, cfg in FILES.items():
        path = os.path.join(DATA, name + '.json')
        reports = load(path, None)
        if not reports:
            continue
        latest = max(r['date'] for r in reports)
        cutoff = (date.fromisoformat(latest) - timedelta(days=cfg['keep_days'] - 1)).isoformat()
        keep = [r for r in reports if r['date'] >= cutoff]
        drop = [r for r in reports if r['date'] < cutoff]
        if not drop:
            print(f'{name}: {len(reports)} entries, nothing older than {cutoff}')
            continue
        known = clubs.setdefault(name, {})
        for r in drop:
            if r['date'] < cfg['full_from']:
                continue  # report only listed problem clubs, so it can't tell us who is missing
            for s in r.get('sites', []):
                if not isinstance(s, dict) or 'sites' in s:
                    continue
                k = club_key(r, s)
                if k not in known or known[k]['lastSeen'] <= r['date']:
                    known[k] = {
                        'id': s.get('id', ''), 'name': s.get('name', ''),
                        'group': r.get('group', ''), 'brand': s.get('brand') or r.get('brand', ''),
                        'installed': s.get('installed', 0), 'lastSeen': r['date'],
                    }
        save(path, keep)
        changed = True
        print(f'{name}: kept {len(keep)} entries from {cutoff}, archived clubs from {len(drop)} older entries '
              f'({len(known)} clubs on record)')
    if changed:
        save(CLUBS, clubs)


if __name__ == '__main__':
    main()
