"""Refresh Taichung police CSV; preserve the last usable snapshot on failure."""
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from import_mobile import parse_mobile, apply_reference_coordinates

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://newdatacenter.taichung.gov.tw/api/v1/no-auth/resource.download?rid=98a68386-8664-4004-a00b-5318e826646e'


def main():
    try:
        req = urllib.request.Request(URL, headers={'User-Agent': 'RoadCameraLookup/1.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            if not response.geturl().startswith('https://newdatacenter.taichung.gov.tw/'):
                raise ValueError('來源轉址異常')
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError('來源檔案過大')
        records = parse_mobile(raw)
        reference_path = ROOT / 'data' / 'mobile-intersections.json'
        if reference_path.exists():
            records = apply_reference_coordinates(records, json.loads(reference_path.read_text(encoding='utf8')))
        timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
        payload = {'meta': {'retrievedAt': timestamp, 'notice': '臺中市警方公告地點，非即時勤務；原始檔未提供公告日期。'}, 'locations': records}
        output = ROOT / 'data' / 'mobile.js'
        temp = output.with_suffix('.tmp')
        temp.write_text('window.MOBILE_CAMERA_DATA = ' + json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c') + ';\n', encoding='utf8')
        temp.replace(output)
        print(f'更新成功 {timestamp}：{len(records)} 筆，{sum(x["lat"] is not None for x in records)} 筆有座標')
        return 0
    except (OSError, ValueError, UnicodeError) as exc:
        print(f'更新失敗，保留既有資料：{type(exc).__name__}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
