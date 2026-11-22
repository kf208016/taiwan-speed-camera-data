"""Refresh the NPA public speed enforcement dataset, preserving the last snapshot on failure."""
import csv
import hashlib
import io
import json
import math
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://opdadm.moi.gov.tw/api/v1/no-auth/resource/api/dataset/EA5E6FCD-B82D-43B7-A5CF-E9893253187E/resource/DF61BE0F-731C-40C1-9C89-E9DECC7D2507/download'
SOURCE = 'https://data.gov.tw/dataset/7320'
FIELDS = ['CityName', 'RegionName', 'Address', 'DeptNm', 'BranchNm', 'Longitude', 'Latitude', 'direct', 'limit']


def parse(raw):
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''))
    if reader.fieldnames != FIELDS: raise ValueError('欄位不符')
    records = []; identities = {}
    for row in reader:
        if row['CityName'] == '設置縣市' and row['Longitude'] == '經度': continue
        if None in row or not all(isinstance(row[k], str) for k in FIELDS): raise ValueError('欄位破損')
        city, area, place = (row[k].strip() for k in FIELDS[:3])
        if not city or not place: raise ValueError('缺少地點')
        try:
            lat, lon = float(row['Latitude']), float(row['Longitude'])
            if not all(map(math.isfinite, (lat, lon))) or not (21 <= lat <= 26.5 and 119 <= lon <= 122.5): lat = lon = None
        except ValueError: lat = lon = None
        speed = row['limit'].strip()
        if not re.fullmatch(r'\d{1,3}', speed) or not 20 <= int(speed) <= 130: speed = '請查公告'
        key = hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]
        identities[key] = identities.get(key, 0) + 1
        records.append(dict(id=f'npa-national-{key}-{identities[key]}', road=city, city=city, place=' '.join(filter(None, [city, area, place])), direction=row['direct'].strip() or '未提供', limit=speed, km=None, lat=lat, lon=lon, kind='national', sourceDate='原始檔未提供', sourceUrl=SOURCE))
    if not 500 <= len(records) <= 20000: raise ValueError('資料筆數異常')
    return records


def main():
    try:
        req = urllib.request.Request(URL, headers={'User-Agent': 'RoadCameraLookup/1.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.geturl() != URL: raise ValueError('來源轉址異常')
            raw = response.read(5_000_001)
        if len(raw) > 5_000_000: raise ValueError('檔案過大')
        records = parse(raw)
        payload = {'meta': {'retrievedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'notice':'警政署全國測速執法設置點，設備類型未提供；下載時間非公告日期。'}, 'locations': records}
        output = ROOT / 'data' / 'nationwide.js'; tmp = output.with_suffix('.tmp')
        tmp.write_text('window.NATIONWIDE_CAMERA_DATA = ' + json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c') + ';\n', encoding='utf8')
        tmp.replace(output)
        print(f'更新成功：{len(records)} 筆；{sum(x["lat"] is not None for x in records)} 筆座標通過範圍檢查')
        return 0
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, csv.Error) as exc:
        print(f'更新失敗，保留先前資料：{type(exc).__name__}', file=sys.stderr); return 1


if __name__ == '__main__': sys.exit(main())
