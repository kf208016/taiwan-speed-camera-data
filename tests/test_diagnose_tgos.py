import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import diagnose_tgos


class DiagnosticsTests(unittest.TestCase):
    @patch('diagnose_tgos.fetch', return_value=b'page')
    @patch('diagnose_tgos.discover', return_value=('https://www.tgos.tw/a', '2026-07-20'))
    @patch('diagnose_tgos.urllib.request.build_opener')
    def test_reports_403_without_echoing_body(self, build, discover, fetch):
        build.return_value.open.side_effect = HTTPError('https://www.tgos.tw/a', 403, 'Forbidden', {}, io.BytesIO(b'Forbidden private-content'))
        with patch('sys.stdout', new_callable=io.StringIO) as out:
            self.assertEqual(diagnose_tgos.main(), 1)
        value = json.loads(out.getvalue())
        self.assertEqual(value['status'], 403)
        self.assertTrue(value['body_markers']['forbidden'])
        self.assertNotIn('private-content', out.getvalue())


if __name__ == '__main__':
    unittest.main()
