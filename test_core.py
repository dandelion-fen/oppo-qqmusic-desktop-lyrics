import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core import fetch_lyrics, line_at, parse_lrc, parse_session


def session(state=3, position=12000, updated=100000):
    return f'''Sessions Stack - have 2 sessions:
  Session #0:
    package=com.other.player
    state=PlaybackState {{state=3, position=100, speed=1.0, updated=100000}}
    metadata: size=3, description=Other song, Other artist, Album
  Session #1:
    package=com.tencent.qqmusic
    state=PlaybackState {{state={state}, position={position}, buffered position=90000, speed=1.0, updated={updated}, actions=123}}
    metadata: size=3, description=晴天, 周杰伦, 叶惠美
'''


class CoreTests(unittest.TestCase):
    def test_android_uptime_projection(self):
        p = parse_session(session(), 105)
        self.assertEqual((p.title, p.artist, p.position, p.playing), ('晴天', '周杰伦', 17, True))

    def test_pause_does_not_advance(self):
        p = parse_session(session(state=2), 105)
        self.assertEqual(p.position, 12)
        self.assertFalse(p.playing)

    def test_named_android_playback_state(self):
        raw = session().replace('state=3,', 'state=PLAYING(3),')
        self.assertTrue(parse_session(raw, 105).playing)
        self.assertEqual(parse_session(raw, 105).position, 17)

    def test_seek_uses_new_position(self):
        self.assertEqual(parse_session(session(position=60000, updated=105000), 105).position, 60)

    def test_nonqq_and_missing_metadata(self):
        self.assertIsNone(parse_session(session().replace('com.tencent.qqmusic', 'com.example')))
        self.assertIsNone(parse_session('package=com.tencent.qqmusic\nstate=PlaybackState {state=3}'))

    def test_no_session_headers(self):
        self.assertEqual(parse_session(session().replace('Session #0:', '').replace('Session #1:', ''), 105).title, '晴天')

    def test_lrc_translation_offset_and_multiple_timestamps(self):
        rows = parse_lrc('[offset:+100]\n[00:01.20][00:03.00]Hello\n[00:01.20]你好\n[ar:test]')
        self.assertEqual(rows, [(1.3, 'Hello / 你好'), (3.1, 'Hello')])
        self.assertEqual(line_at(rows, 0), -1)
        self.assertEqual(line_at(rows, 1.3), 0)
        self.assertEqual(line_at(rows, 500), 1)

    def test_provider_fallback_and_cache(self):
        calls = []
        def mock_request(url, data=None):
            calls.append(url)
            if 'qq.com' in url:
                raise OSError('QQ temporarily unavailable')
            if '/search/' in url:
                return {'result': {'songs': [{'id': 1, 'name': '晴天', 'artists': [{'name': '周杰伦'}]}]}}
            return {'lrc': {'lyric': '[00:01]歌词'}}
        with tempfile.TemporaryDirectory() as directory, patch('core.request_json', side_effect=mock_request):
            value = fetch_lyrics('晴天', '周杰伦', Path(directory))
            self.assertEqual(value['source'], '网易云')
            count = len(calls)
            self.assertEqual(fetch_lyrics('晴天', '周杰伦', directory), value)
            self.assertEqual(len(calls), count)


if __name__ == '__main__':
    unittest.main()
