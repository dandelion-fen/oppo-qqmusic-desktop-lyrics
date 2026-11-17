"""Android MediaSession bridge and timed lyrics. Standard library only."""
import base64
import bisect
import dataclasses
import difflib
import html
import json
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path


@dataclasses.dataclass
class Playback:
    title: str
    artist: str
    position: float
    playing: bool
    speed: float = 1.0
    sampled: float = dataclasses.field(default_factory=time.monotonic)

    def now(self):
        return max(0, self.position + ((time.monotonic() - self.sampled) * self.speed if self.playing else 0))


def parse_session(text, device_uptime=None):
    # Session headers vary between Android releases. package= remains a standard field.
    chunks = re.split(r'(?m)(?=^\s*Session #\d+:)', text)
    candidates = []
    for chunk in chunks:
        # Some releases don't print Session # headers; split at package fields instead.
        starts = list(re.finditer(r'(?m)^\s*package=(\S+)', chunk))
        for i, match in enumerate(starts):
            if match.group(1).rstrip(',') != 'com.tencent.qqmusic':
                continue
            end = starts[i + 1].start() if i + 1 < len(starts) else len(chunk)
            block = chunk[match.start():end]
            state = re.search(r'PlaybackState\s*\{([^\n}]*)', block)
            desc = re.search(r'(?m)^\s*metadata:.*?description=(.*)$', block)
            if not state or not desc:
                continue
            fields = desc.group(1).strip().split(', ', 2)
            title = fields[0].strip()
            artist = fields[1].strip() if len(fields) > 1 and fields[1] != 'null' else ''
            if title in ('', 'null'):
                continue
            def number(key, default):
                m = re.search(r'(?<![\w ])' + key + r'=(-?[\d.]+)', state.group(1))
                if not m:
                    m = re.search(r'(?:^|,\s*)' + key + r'=(-?[\d.]+)', state.group(1))
                return float(m.group(1)) if m else default
            state_label = re.search(r'(?:^|,\s*)state=([A-Z_]+)(?:\((\d+)\))?', state.group(1))
            if state_label:
                status = int(state_label.group(2)) if state_label.group(2) else {'PLAYING': 3, 'PAUSED': 2}.get(state_label.group(1), 0)
            else:
                status = int(number('state', 0))
            position = max(0, number('position', 0)) / 1000
            speed = number('speed', 1)
            updated = number('updated', 0) / 1000
            if status == 3 and device_uptime is not None and updated > 0:
                age = device_uptime - updated
                if 0 <= age < 86400:
                    position += age * speed
            candidates.append(Playback(title, artist, position, status == 3, speed))
    if not candidates:
        return None
    return next((p for p in candidates if p.playing), candidates[0])


def parse_lrc(text):
    offset = re.search(r'\[offset:([+-]?\d+)\]', text, re.I)
    shift = int(offset.group(1)) / 1000 if offset else 0
    rows = []
    for line in text.splitlines():
        stamps = re.findall(r'\[(\d+):(\d+(?:\.\d+)?)\]', line)
        words = re.sub(r'\[[^]]*\]', '', line).strip()
        for minute, second in stamps:
            rows.append((max(0, int(minute) * 60 + float(second) + shift), words))
    # Merge translation / original text at identical timestamps.
    merged = {}
    for stamp, words in sorted(rows):
        if stamp not in merged:
            merged[stamp] = words
        elif words and words not in merged[stamp].split(' / '):
            merged[stamp] += ' / ' + words
    return list(merged.items())


def line_at(rows, seconds):
    return bisect.bisect_right([r[0] for r in rows], seconds) - 1


def locate_adb(configured=''):
    if configured and Path(configured).is_file():
        return configured
    local = Path(__file__).resolve().parent / 'tools' / 'adb.exe'
    return str(local) if local.exists() else shutil.which('adb')


def adb_run(adb, args, serial='', timeout=10):
    cmd = [adb] + (['-s', serial] if serial else []) + list(args)
    result = subprocess.run(cmd, capture_output=True, timeout=timeout,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    out = result.stdout.decode('utf-8', errors='replace')
    err = result.stderr.decode('utf-8', errors='replace')
    if result.returncode:
        raise RuntimeError((err or out).strip())
    return out


def devices(adb):
    return [line.split()[0] for line in adb_run(adb, ['devices']).splitlines()[1:]
            if len(line.split()) >= 2 and line.split()[1] == 'device']


def sample(adb, serial):
    raw = adb_run(adb, ['shell', 'dumpsys', 'media_session'], serial)
    uptime = float(adb_run(adb, ['shell', 'cat', '/proc/uptime'], serial).split()[0])
    return parse_session(raw, uptime)


def request_json(url, data=None):
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://y.qq.com/'}
    if data is not None:
        data = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=12) as response:
        return json.loads(response.read().decode('utf-8'))


def similarity(title, artist, name, singer):
    clean = lambda s: re.sub(r'\W', '', s).lower()
    return (difflib.SequenceMatcher(None, clean(title), clean(name)).ratio() * 0.75
            + difflib.SequenceMatcher(None, clean(artist), clean(singer)).ratio() * 0.25)


def fetch_lyrics(title, artist, cache_dir, force=False):
    import hashlib
    cache_dir = Path(cache_dir)
    key = hashlib.sha256((title + '\0' + artist).encode()).hexdigest()
    cached = cache_dir / (key + '.json')
    if cached.exists() and not force:
        try:
            value = json.loads(cached.read_text(encoding='utf-8'))
            if parse_lrc(value['lrc']):
                return value
        except (ValueError, KeyError):
            pass
    errors = []
    for provider in ('QQ音乐', '网易云'):
        try:
            if provider == 'QQ音乐':
                payload = {'req': {'module': 'music.search.SearchCgiService',
                           'method': 'DoSearchForQQMusicDesktop',
                           'param': {'query': title + ' ' + artist, 'search_type': 0,
                                     'num_per_page': 8, 'page_num': 1}}}
                url = 'https://u.y.qq.com/cgi-bin/musicu.fcg?data=' + urllib.parse.quote(json.dumps(payload))
                songs = request_json(url)['req']['data']['body']['song']['list']
                options = [(similarity(title, artist, s['name'], '/'.join(a['name'] for a in s['singer'])), s) for s in songs]
            else:
                data = request_json('https://music.163.com/api/search/get/web',
                                    {'s': title + ' ' + artist, 'type': 1, 'limit': 8})
                result = data.get('result', {})
                if not isinstance(result, dict):
                    raise RuntimeError('搜索服务返回异常，请稍后重试')
                songs = result.get('songs', [])
                options = [(similarity(title, artist, s['name'], '/'.join(a['name'] for a in s['artists'])), s) for s in songs]
            for score, song in sorted(options, key=lambda p: p[0], reverse=True)[:3]:
                if score < 0.72:
                    continue
                if provider == 'QQ音乐':
                    url = 'https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg?' + urllib.parse.urlencode(
                        {'songmid': song['mid'], 'format': 'json', 'nobase64': 1})
                    lrc = request_json(url).get('lyric', '')
                    if '[' not in lrc and lrc:
                        lrc = base64.b64decode(lrc).decode('utf-8')
                else:
                    data = request_json('https://music.163.com/api/song/lyric?' + urllib.parse.urlencode(
                        {'id': song['id'], 'lv': -1, 'kv': -1, 'tv': -1}))
                    lrc = data.get('lrc', {}).get('lyric', '')
                if not isinstance(lrc, str):
                    continue
                lrc = html.unescape(lrc)
                if parse_lrc(lrc):
                    result = {'lrc': lrc, 'source': provider, 'matched': song['name']}
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    cached.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
                    return result
            errors.append(provider + '未匹配到足够相似的带时间轴歌词')
        except Exception as exc:
            errors.append(provider + ': ' + str(exc))
    raise RuntimeError('；'.join(errors))
