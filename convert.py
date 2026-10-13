"""Convert public Follow Builders JSON into three RSS feeds; no dependencies."""
import argparse
import hashlib
import html
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
import xml.etree.ElementTree as ET

UPSTREAM = 'https://github.com/zarazhangrui/follow-builders'
KINDS = {'x': 'X 帖子', 'podcasts': '播客', 'blogs': '博客'}
LIMIT = 500


def safe_url(value):
    value = str(value or '')
    return value if value.startswith(('https://', 'http://')) else ''


def clean(value):
    return ''.join(c for c in str(value or '') if c in '\t\n\r' or 32 <= ord(c) <= 0xD7FF or 0xE000 <= ord(c) <= 0xFFFD or 0x10000 <= ord(c) <= 0x10FFFF)


def date(value):
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except (ValueError, TypeError):
        return None


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(content, encoding='utf-8')
    os.replace(tmp, path)


def fetch(kind, cache):
    if cache:
        return json.loads((cache / f'feed-{kind}.json').read_text(encoding='utf-8-sig'))
    urls = [f'https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-{kind}.json',
            f'https://api.github.com/repos/zarazhangrui/follow-builders/contents/feed-{kind}.json?ref=main']
    failures = []
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'follow-builders-rss', 'Accept': 'application/vnd.github.raw+json'})
            with urllib.request.urlopen(req, timeout=25) as response:
                return json.load(response)
        except Exception as exc:
            failures.append(str(exc))
    raise RuntimeError('; '.join(failures))


def normalize(kind, feed):
    if not isinstance(feed, dict) or not isinstance(feed.get(kind), list):
        raise ValueError(f'Invalid {kind} feed schema')
    result = []
    records = []
    if kind == 'x':
        for author in feed[kind]:
            if not isinstance(author, dict) or not isinstance(author.get('tweets'), list):
                raise ValueError('Invalid X author/tweets schema')
            records.extend((post, author.get('name') or author.get('handle', '')) for post in author['tweets'])
    else:
        records = [(post, post.get('author') or post.get('name', '')) for post in feed[kind] if isinstance(post, dict)]
        if len(records) != len(feed[kind]):
            raise ValueError('Invalid item schema')
    for post, author in records:
        url = safe_url(post.get('url'))
        if not url:
            raise ValueError('Missing or invalid original URL')
        text = post.get('text') if kind == 'x' else post.get('transcript') if kind == 'podcasts' else post.get('content') or post.get('description')
        text = clean(html.unescape(str(text or '')))
        title = clean(post.get('title') or f'{author}: ' + ' '.join(text.split())[:100])
        # Podcast playlist URLs may be shared by multiple episodes; prefer their episode GUID.
        key = post.get('id') if kind == 'x' else post.get('guid') or url
        guid = kind + ':' + hashlib.sha256(str(key).encode()).hexdigest()
        published = post.get('createdAt') if kind == 'x' else post.get('publishedAt')
        result.append({'guid': guid, 'url': url, 'title': title, 'author': clean(author),
                       'text': text, 'publishedAt': published if date(published) else None})
    return result


def render(kind, entries, generated_at):
    rss = ET.Element('rss', version='2.0')
    channel = ET.SubElement(rss, 'channel')
    def add(parent, name, value):
        ET.SubElement(parent, name).text = clean(value)
    add(channel, 'title', f'Follow Builders · {KINDS[kind]}')
    add(channel, 'link', UPSTREAM)
    add(channel, 'description', f'Zara Zhang 的公开 Follow Builders 数据转换。源更新时间：{generated_at or "未知"}。内容为原作者表述，未独立核实。')
    add(channel, 'language', 'en')
    if date(generated_at):
        add(channel, 'lastBuildDate', format_datetime(date(generated_at)))
    add(channel, 'ttl', '360')
    for entry in entries:
        item = ET.SubElement(channel, 'item')
        add(item, 'title', entry['title'])
        add(item, 'link', entry['url'])
        ET.SubElement(item, 'guid', isPermaLink='false').text = entry['guid']
        if date(entry['publishedAt']):
            add(item, 'pubDate', format_datetime(date(entry['publishedAt'])))
        # Escape upstream content before embedding HTML; no active markup is passed through.
        body = '<p>' + html.escape(entry['author']) + '</p><p>' + html.escape(entry['text']).replace('\n', '<br/>') + '</p>'
        body += '<p><a href="' + html.escape(entry['url'], quote=True) + '">查看原文</a></p>'
        add(item, 'description', body)
        add(item, 'category', KINDS[kind])
    ET.indent(rss)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss, encoding='unicode') + '\n'


def update(kind, feed, output):
    incoming = normalize(kind, feed)
    state_path = output / f'{kind}-state.json'
    previous = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {'items': []}
    merged = {item['guid']: item for item in previous['items']}
    for item in incoming:
        if item['guid'] in merged and not item['publishedAt']:
            item['publishedAt'] = merged[item['guid']]['publishedAt']
        merged[item['guid']] = item
    entries = sorted(merged.values(), key=lambda e: date(e['publishedAt']) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[:LIMIT]
    xml = render(kind, entries, feed.get('generatedAt'))
    ET.fromstring(xml)  # Never replace the last usable feed with malformed XML.
    atomic_write(output / f'{kind}.xml', xml)
    atomic_write(state_path, json.dumps({'generatedAt': feed.get('generatedAt'), 'items': entries}, ensure_ascii=False, indent=2) + '\n')
    return {'newSnapshotItems': len(incoming), 'retainedItems': len(entries), 'generatedAt': feed.get('generatedAt'), 'upstreamErrors': feed.get('errors', [])}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache-dir', type=Path)
    parser.add_argument('--output-dir', type=Path, default=Path('feeds'))
    args = parser.parse_args()
    failed = False
    status = {}
    for kind in KINDS:
        try:
            status[kind] = {'status': 'ok', **update(kind, fetch(kind, args.cache_dir), args.output_dir)}
            if status[kind]['upstreamErrors']:
                failed = True
        except Exception as exc:
            failed = True
            status[kind] = {'status': 'error', 'error': str(exc), 'previousFeedPreserved': (args.output_dir / f'{kind}.xml').exists()}
    atomic_write(args.output_dir / 'status.json', json.dumps(status, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(status, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
