import csv
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import update_nationwide as u


def sample(bad=False):
    out = io.StringIO(newline=''); writer = csv.writer(out); writer.writerow(u.FIELDS)
    for i in range(500): writer.writerow(['臺中市', '西區', f'測試{i}', '警局', '分局', 'nan' if bad and i == 0 else '120.6', '24.1', '東向', '50'])
    return out.getvalue().encode()


class NationwideTests(unittest.TestCase):
    def test_validates_and_preserves_unknown_type(self):
        result = u.parse(sample(True))
        self.assertEqual(len(result), 500); self.assertIsNone(result[0]['lat'])
        self.assertEqual(result[1]['kind'], 'national'); self.assertEqual(result[1]['lat'], 24.1)

    def test_bad_schema_and_truncated_fail(self):
        for value in (b'wrong,header\na,b\n', b''):
            with self.subTest(value=value), self.assertRaises(ValueError): u.parse(value)

    def test_network_failure_preserves_snapshot(self):
        with patch.object(u.urllib.request, 'urlopen', side_effect=OSError('offline')):
            self.assertEqual(u.main(), 1)
