import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import update_hsinchu_mobile as u


def html(bad=''):
    rows = ''.join(f'<tr><td>新竹市東區測試{i}</td><td>50</td><td>{bad if i == 0 and bad else "121.0"}</td><td>24.8</td><td>移動式</td></tr>' for i in range(20))
    return ('<table><tr><td>'+u.TITLE+'</td></tr><tr><td>地 點</td><td>速限</td><td>經度</td><td>緯度</td><td>備註</td></tr>'+rows+'</table>').encode()


class HsinchuTests(unittest.TestCase):
    def test_mobile_only_and_coordinates(self):
        items = u.parse(html()); self.assertEqual(len(items), 20)
        self.assertEqual((items[0]['kind'], items[0]['lat'], items[0]['lon']), ('mobile', 24.8, 121.0))
    def test_rejects_bad_or_swapped_coordinate(self):
        for bad in ('nan', '24.8', '200'):
            with self.subTest(bad=bad), self.assertRaises(ValueError): u.parse(html(bad))
    def test_rejects_missing_title_and_other_type(self):
        for raw in (b'<table></table>', html().replace('移動式</td>'.encode(), '固定式</td>'.encode(), 1)):
            with self.assertRaises(ValueError): u.parse(raw)
    def test_failure_preserves_snapshot(self):
        with patch.object(u.urllib.request, 'urlopen', side_effect=OSError('offline')):
            self.assertEqual(u.main(), 1)
