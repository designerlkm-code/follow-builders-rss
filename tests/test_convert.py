import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET
from convert import update, CONTENT_NS, DC_NS


class ConversionTests(unittest.TestCase):
    def test_guid_history_and_markup(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            post = {'id': '123', 'url': 'https://x.com/a/status/123', 'createdAt': '2026-10-01T12:00:00Z', 'text': 'A & B <script>alert(1)</script> ]]> 中文'}
            feed = {'generatedAt': '2026-10-13T00:00:00Z', 'x': [{'name': '作者', 'tweets': [post, post]}]}
            update('x', feed, path)
            root = ET.parse(path / 'x.xml')
            items = root.findall('./channel/item')
            self.assertEqual(len(items), 1)
            self.assertIn('&lt;script&gt;', items[0].findtext('description'))
            self.assertEqual(items[0].findtext(f'{{{CONTENT_NS}}}encoded'), items[0].findtext('description'))
            self.assertEqual(items[0].findtext(f'{{{DC_NS}}}creator'), '作者')
            self.assertIn('01 Oct 2026', items[0].findtext('pubDate'))
            guid = items[0].findtext('guid')
            update('x', {**feed, 'x': []}, path)
            self.assertEqual(ET.parse(path / 'x.xml').findtext('./channel/item/guid'), guid)

    def test_invalid_snapshot_preserves_previous_feed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            update('blogs', {'blogs': []}, path)
            old = (path / 'blogs.xml').read_bytes()
            with self.assertRaises(ValueError):
                update('blogs', {'blogs': [{'url': 'javascript:bad'}]}, path)
            self.assertEqual((path / 'blogs.xml').read_bytes(), old)

    def test_podcast_guid_distinguishes_shared_playlist(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            feed = {'podcasts': [{'guid': g, 'url': 'https://youtube.com/playlist?list=test', 'title': g, 'transcript': 'test'} for g in ['episode1', 'episode2']]}
            update('podcasts', feed, path)
            items = ET.parse(path / 'podcasts.xml').findall('./channel/item')
            self.assertEqual(len(items), 2)
            self.assertIsNone(items[0].find('pubDate'))


if __name__ == '__main__':
    unittest.main()
