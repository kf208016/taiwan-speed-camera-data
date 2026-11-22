"""Refresh Hsinchu City Police's explicitly labelled mobile enforcement list."""
import hashlib
import json
import math
import sys
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://tra6.hccp.gov.tw/trafficweb/pages/camera'
TITLE = '新竹市警察局科學儀器(移動式)取締地點一覽表'


class Rows(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows = []; self.row = None; self.cell = None
    def handle_starttag(self, tag, attrs):
        if tag == 'tr': self.row = []
        if tag in ('td', 'th') and self.row is not None: self.cell = []
    def handle_data(self, text):
        if self.cell is not None: self.cell.append(text)
    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(' '.join(''.join(self.cell).split())); self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.rows.append(self.row); self.row = None


def parse(raw):
    parser = Rows(); parser.feed(raw.decode('utf8'))
    headers = [i for i, row in enumerate(parser.rows) if len(row) == 1 and row[0] == TITLE]
    if len(headers) != 1: raise ValueError('移動式表格標題不唯一')
    start = headers[0] + 1
    if start >= len(parser.rows) or [x.replace(' ', '') for x in parser.rows[start]] != ['地點', '速限', '經度', '緯度', '備註']:
        raise ValueError('移動式表格欄位不符')
    records = []; seen = set()
    for row in parser.rows[start + 1:]:
        if len(row) != 5 or row[4] != '移動式': raise ValueError('移動式資料格式異常')
        place, speed, lon, lat, kind = row
        lat, lon = float(lat), float(lon)
        if not place.startswith('新竹市') or not speed.isdigit() or not 20 <= int(speed) <= 130 or not all(map(math.isfinite, (lat, lon))) or not (24.6 <= lat <= 25.0 and 120.7 <= lon <= 121.2):
            raise ValueError('新竹市資料或座標異常')
        key = hashlib.sha256(json.dumps(row, ensure_ascii=False).encode()).hexdigest()[:20]
        if key in seen: raise ValueError('重複資料')
        seen.add(key)
        records.append(dict(id='hsinchu-mobile-'+key, road='新竹市', place=place, direction='詳見地點描述', limit=speed, km=None, lat=lat, lon=lon, kind='mobile', sourceDate='原始網頁未標示', sourceUrl=URL))
    if not 20 <= len(records) <= 500: raise ValueError('移動式筆數異常')
    return records


def write(raw, target=None):
    records = parse(raw)
    payload = {'meta': {'retrievedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'notice':'新竹市警方公告；原始網頁未標示資料日期。'}, 'locations': records}
    output = target or ROOT / 'data' / 'hsinchu-mobile.js'; tmp = output.with_suffix('.tmp')
    tmp.write_text('window.HSINCHU_MOBILE_DATA = '+json.dumps(payload,ensure_ascii=False).replace('<','\\u003c')+';\n',encoding='utf8'); tmp.replace(output)
    print(f'新竹移動式更新成功：{len(records)} 筆')


def main():
    try:
        req = urllib.request.Request(URL, headers={'User-Agent':'RoadCameraLookup/1.0'})
        with urllib.request.urlopen(req,timeout=30) as response:
            if response.geturl() != URL: raise ValueError('來源轉址異常')
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000: raise ValueError('公告過大')
        write(raw); return 0
    except (OSError, ValueError, UnicodeError, TypeError) as exc:
        print(f'新竹移動式更新失敗，保留快照：{type(exc).__name__}',file=sys.stderr); return 1


if __name__ == '__main__': sys.exit(main())
