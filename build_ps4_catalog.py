#!/usr/bin/env python3
"""Build a PS4 FPKGi+ GAMES.json and an exhaustive metadata-only PS4 library.

Sources: title IDs/names from Axekinn/ps4-scraper; optional FPKGi DATA lists.
Requires no third-party Python packages. Does NOT supply game files, licenses,
keys, cracks, or guarantee FPKGs work. Only download content you're authorized to.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

DEFAULT_METADATA = 'https://raw.githubusercontent.com/Axekinn/ps4-scraper/main/ps4_titles.csv'
TITLE_RE = re.compile(r'^CUSA\d{5}$', re.I)
# A language tag is evidence about an edition, unlike its broad EU/US/Japan region.
NON_EN_NAMES = 'german deutsch germany french francais français france spanish spain espanol español italian italy russian polish portuguese brazilian dutch japanese korean chinese turkish arabic czech hungarian greek swedish norwegian danish finnish'.split()
NON_EN_RE = '|'.join(re.escape(x) for x in NON_EN_NAMES)
EN_EVIDENCE = re.compile(r'\benglish\b|\[en\]|\[eng\]|\(en\)|\(eng\)', re.I)
LANGUAGE_EDITION = re.compile(
    r'(?:\(\s*(?:' + NON_EN_RE + r')(?:[\s,;/+&-]+(?:' + NON_EN_RE + r'))*(?:\s+(?:edition|version|ver\.?|only))?\s*\)'
    r'|\[\s*(?:de|ger|fr|fra|es|esp|it|ita|ru|rus|pl|pol|jp|jpn|kr|kor|cn|chn)\s*\]'
    r'|\s*[-:]\s*(?:' + NON_EN_RE + r')(?:\s+(?:version|ver\.?|edition|only))?\s*$'
    r'|\s+(?:' + NON_EN_RE + r')\s+(?:version|ver\.?|edition|only)\s*$'
    r')', re.I)
FILE_LANGUAGE = re.compile(r'\[(?:DE|GER|FR|FRA|ES|ESP|IT|ITA|RU|RUS|PL|POL|JP|JPN|KR|KOR|CN|CHN)\]', re.I)


def read_text(source: str, base: Path, max_bytes: int = 64 * 1024 * 1024) -> str:
    if source.startswith(('http://', 'https://')):
        parts = urlsplit(source)
        if not parts.hostname or parts.username or parts.password or parts.scheme != 'https':
            raise ValueError(f'Only public HTTPS source URLs supported: {source}')
        error = None
        for attempt in range(3):
            try:
                req = Request(source, headers={'User-Agent': 'PS4-FPKGi-Catalog-Builder/1.0', 'Accept': 'application/json,text/csv,*/*'})
                with urlopen(req, timeout=45) as resp:
                    body = resp.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise ValueError('Source exceeds size limit')
                return body.decode('utf-8-sig')
            except Exception as exc:
                error = exc
                if attempt < 2:
                    time.sleep(attempt + 1)
        raise RuntimeError(f'Cannot retrieve {source}: {error}')
    path = (base / source).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size > max_bytes:
        raise ValueError('Local source exceeds size limit')
    return path.read_text(encoding='utf-8-sig')


def english_evidence(name: str, filename: str = '') -> bool:
    return bool(EN_EVIDENCE.search(name) or EN_EVIDENCE.search(unquote(filename)))


def non_english_edition(name: str, filename: str = '') -> bool:
    if english_evidence(name, filename):
        return False
    if LANGUAGE_EDITION.search(name):
        return True
    return bool(FILE_LANGUAGE.search(unquote(filename)))


def clean(value: object) -> str:
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def parse_size(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        n = int(value)
        return n if n > 0 else 0
    except (ValueError, TypeError):
        return 0


def valid_pkg_link(url: str) -> bool:
    try:
        p = urlsplit(url)
        return p.scheme in ('http','https') and bool(p.hostname) and not p.username and not p.password and not p.fragment
    except ValueError:
        return False


def read_metadata(csv_text: str) -> dict[str, dict]:
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        raise ValueError('Metadata CSV contains no header')
    titles: dict[str, dict] = {}
    for row in reader:
        tid = clean(row.get('Title_ID') or row.get('title_id')).upper()
        name = clean(row.get('Name') or row.get('name'))
        if not TITLE_RE.fullmatch(tid) or not name:
            continue
        prior = titles.get(tid)
        if prior and len(prior['name']) >= len(name):
            continue
        titles[tid] = {
            'title_id': tid, 'name': name, 'editions': clean(row.get('Editions') or ''),
            'medium': 'PS4 metadata', 'language_status': 'unknown',
            'download_available': False, 'download_count': 0,
        }
    if not titles:
        raise ValueError('No PS4 CUSA title records found; check CSV schema')
    return titles


def choose_score(url: str, item: dict, source_priority: int) -> tuple:
    label = item['name'] + ' ' + unquote(url)
    return (int(english_evidence(label)), int(url.startswith('https://')), -source_priority, int(bool(item.get('cover_url'))))


def build(metadata_csv: str, catalog_sources: list[tuple[str, str]], manual_exclusions: set[str]) -> tuple[dict, list, list, dict]:
    titles = read_metadata(metadata_csv)
    candidate_by_key: dict[tuple[str, str, str], tuple[str, dict, tuple]] = {}
    ignored = Counter()
    excluded: list[dict] = []
    original_download_entries = 0
    source_reports = []
    for priority, (source_name, text) in enumerate(catalog_sources):
        data = json.loads(text)
        if not isinstance(data, dict) or not isinstance(data.get('DATA'), dict):
            raise ValueError(f'{source_name}: missing DATA object')
        n = 0
        for url, raw in data['DATA'].items():
            n += 1
            original_download_entries += 1
            if not isinstance(raw, dict):
                ignored['invalid_metadata'] += 1
                continue
            tid = clean(raw.get('title_id')).upper()
            name = clean(raw.get('name'))
            size = parse_size(raw.get('size'))
            if not TITLE_RE.fullmatch(tid) or not name or not size or not valid_pkg_link(url):
                ignored['missing_required_fields'] += 1
                continue
            if tid in manual_exclusions or non_english_edition(name, url):
                ignored['explicit_non_english'] += 1
                excluded.append({'title_id': tid, 'name': name, 'reason': 'Excluded non-English edition', 'source': source_name})
                continue
            region = clean(raw.get('region')).upper() or None
            version = clean(raw.get('version')) or None
            item = {'title_id': tid, 'name': name, 'size': size, 'region': region,
                    'version': version, 'release': raw.get('release'), 'min_fw': raw.get('min_fw'),
                    'cover_url': raw.get('cover_url')}
            # Duplicates across mirrors: select one per title ID, region and version,
            # while preserving regional editions and different versions.
            key = (tid, region or '', version or '')
            score = choose_score(url, item, priority)
            if key not in candidate_by_key or score > candidate_by_key[key][2]:
                if key in candidate_by_key:
                    ignored['duplicate_mirror'] += 1
                candidate_by_key[key] = (url, item, score)
            else:
                ignored['duplicate_mirror'] += 1
        source_reports.append({'source': source_name, 'entries_read': n})

    game_entries: dict[str, dict] = {}
    for url, item, _ in sorted(candidate_by_key.values(), key=lambda x: (x[1]['name'].casefold(), x[1]['title_id'], x[0])):
        game_entries[url] = item
        tid = item['title_id']
        if tid not in titles:
            titles[tid] = {'title_id': tid, 'name': item['name'], 'editions': '',
                            'medium': 'FPKGi source', 'language_status': 'unknown',
                            'download_available': False, 'download_count': 0}
        titles[tid]['download_count'] += 1
        titles[tid]['download_available'] = True
        if english_evidence(item['name'], url):
            titles[tid]['language_status'] = 'English marked in source'

    # Keep metadata-only games even if there is no package download.
    for tid in list(titles):
        record = titles[tid]
        if tid in manual_exclusions or non_english_edition(record['name']):
            excluded.append({'title_id': tid, 'name': record['name'], 'reason': 'Metadata title explicitly non-English', 'source': 'metadata'})
            del titles[tid]

    library = sorted(titles.values(), key=lambda e: (e['name'].casefold(), e['title_id']))
    report = {
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'metadata_title_ids_after_filter': len(library),
        'download_source_entries_read': original_download_entries,
        'fpkgi_download_entries_after_filter': len(game_entries),
        'unique_title_ids_with_download': len({v['title_id'] for v in game_entries.values()}),
        'metadata_only_records': sum(not x['download_available'] for x in library),
        'excluded_entries': len(excluded), 'skipped_reasons': dict(ignored),
        'source_reports': source_reports,
        'caveats': [
            'A title record is not a unique game: editions and regions may vary.',
            'Presence in a third-party FPKGi index does not verify its link works or its contents are authorized.',
            'An unknown language is kept to avoid losing English-capable games.',
            'Metadata-only titles have no download button in stock FPKGi+.',
        ],
    }
    return {'DATA': game_entries}, library, excluded, report


def write_json(path: Path, obj: object) -> None:
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='sources.json')
    parser.add_argument('--metadata', help='Override the public PS4 title CSV source (URL or path)')
    parser.add_argument('--output', default='.')
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    base = config_path.parent
    config = json.loads(config_path.read_text(encoding='utf-8'))
    sources = []
    errors = []
    for entry in config.get('catalog_sources', []):
        if not entry.get('enabled', True):
            continue
        try:
            sources.append((entry.get('name') or entry['url'], read_text(entry['url'], base)))
        except Exception as e:
            errors.append(str(e))
    for name in config.get('local_catalogs', []):
        path = base / name
        if path.exists():
            sources.append((name, read_text(name, base)))
    if not sources:
        print('No source catalogs loaded; refusing to overwrite a working GAMES.json. ' + '; '.join(errors), file=sys.stderr)
        return 2
    metadata_source = args.metadata or config.get('metadata_csv') or DEFAULT_METADATA
    try:
        metadata_text = read_text(metadata_source, base)
        catalog, library, excluded, report = build(metadata_text, sources, {x.upper() for x in config.get('excluded_title_ids', [])})
    except Exception as e:
        print(f'Cannot build catalog: {e}', file=sys.stderr)
        return 3
    if not catalog['DATA']:
        print('No valid FPKGi entries generated. Keeping previous files.', file=sys.stderr)
        return 4
    report['source_fetch_errors'] = errors
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for filename, payload in [
        ('GAMES.json', catalog), ('PS4_LIBRARY.json', library),
        ('PS4_LANGUAGE_EXCLUDED.json', excluded), ('catalog_report.json', report),
    ]:
        write_json(output / filename, payload)
    print(json.dumps({k: v for k, v in report.items() if k != 'caveats'}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
