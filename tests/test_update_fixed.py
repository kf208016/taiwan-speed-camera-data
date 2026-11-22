import io
import json
import unittest
import zipfile
import tempfile
from pathlib import Path
from unittest.mock import patch
from scripts import update_fixed
from scripts.update_fixed import discover, parse_archive


def page(url):
    content = [{'identifier':'13940', 'distribution':[{'encodingFormat':'CSV', 'contentUrl':url}]}]
    return '<script type="application/ld+json">' + json.dumps(content) + '</script>'


class FixedUpdateTests(unittest.TestCase):
    def test_discovers_official_dated_archive(self):
        url, source_date = discover(page('https://www.tgos.tw/tgos/VirtualDir/Product/a/1150720-國道公路固定式測速照相地點.zip'))
        self.assertEqual(source_date, '2026-07-20')
        self.assertTrue(url.startswith('https://www.tgos.tw/'))

    def test_rejects_untrusted_resource(self):
        with self.assertRaises(ValueError):
            discover(page('https://evil.example/tgos/VirtualDir/Product/a/1150720-國道公路固定式測速照相地點.zip'))

    def test_rejects_bad_archive(self):
        with self.assertRaises(zipfile.BadZipFile):
            parse_archive(b'not a zip', '2026-07-20')

    def test_failure_keeps_prior_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'data').mkdir()
            snapshot = root / 'data' / 'locations.js'
            snapshot.write_text('previous', encoding='utf8')
            with patch.object(update_fixed, 'ROOT', root), patch.object(update_fixed, 'fetch', side_effect=OSError('offline')):
                self.assertEqual(update_fixed.main(), 1)
            self.assertEqual(snapshot.read_text(encoding='utf8'), 'previous')
