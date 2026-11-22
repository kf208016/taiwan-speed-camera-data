"""Convert Taichung police mobile enforcement CSV into a safe local snapshot."""
import csv
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'https://data.gov.tw/dataset/170672'


def parse_mobile(raw):
    text = raw.decode('utf-8-sig').lstrip('\ufeff')
    reader = csv.DictReader(io.StringIO(text, newline=''))
    required = {'編號', '行政區', '取締地點', '取締行向', '速限Speed', '經度', '緯度'}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise ValueError('移動式資料欄位不符')
    records = []
    ids = set()
    for row in reader:
        ident, place = row['編號'].strip(), row['取締地點'].strip()
        if not ident.isdigit() or ident in ids or not place or not row['行政區'].strip():
            raise ValueError('移動式資料編號或地點異常')
        ids.add(ident)
        lat = lon = None
        try:
            lat, lon = float(row['緯度']), float(row['經度'])
            if not (23 <= lat <= 25.5 and 119 <= lon <= 122):
                lat = lon = None
        except ValueError:
            pass
        raw_limit = row['速限Speed'].strip()
        parts = re.fullmatch(r'\s*(\d{2,3})(?:\s*[/、,]\s*(\d{2,3}))?\s*', raw_limit)
        limit = '/'.join(x for x in parts.groups() if x) if parts and all(20 <= int(x) <= 130 for x in parts.groups() if x) else '請查公告'
        records.append({'id': 'taichung-mobile-' + ident, 'road': '臺中市',
                        'place': row['行政區'].strip() + ' ' + place,
                        'direction': row['取締行向'].strip() or '未提供',
                        'limit': limit, 'km': None,
                        'lat': lat, 'lon': lon, 'kind': 'mobile',
                        'sourceDate': '原始檔未提供', 'sourceUrl': SOURCE})
    if not 10 <= len(records) <= 10000:
        raise ValueError('移動式資料筆數異常')
    return records


def apply_reference_coordinates(records, reference):
    """Attach verified intersection positions only when full place text matches."""
    if not isinstance(reference, dict) or not isinstance(reference.get('locations'), dict):
        raise ValueError('路口座標資料格式異常')
    for item in records:
        if item['lat'] is not None:
            continue
        candidate = reference['locations'].get(item['place'])
        if not isinstance(candidate, dict) or candidate.get('precision') != 'intersection':
            continue
        lat, lon = candidate.get('lat'), candidate.get('lon')
        if isinstance(lat, (int, float)) and not isinstance(lat, bool) and isinstance(lon, (int, float)) and not isinstance(lon, bool) and 23 <= lat <= 25.5 and 119 <= lon <= 122:
            item.update(lat=lat, lon=lon, coordinateType='intersection', coordinateSource='https://data.gov.tw/dataset/167920', coordinateDate=reference.get('retrievedAt', ''))
    return records


def main():
    records = parse_mobile((ROOT / 'official-mobile.csv').read_bytes())
    payload = {'meta': {'retrievedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                        'notice': '臺中市警方公告移動式取締地點，並非即時勤務；原始檔未提供公告日期。'},
               'locations': records}
    output = ROOT / 'data' / 'mobile.js'
    temp = output.with_suffix('.tmp')
    temp.write_text('window.MOBILE_CAMERA_DATA = ' + json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c') + ';\n', encoding='utf8')
    temp.replace(output)
    print(f'移動式資料 {len(records)} 筆；有座標 {sum(x["lat"] is not None for x in records)} 筆')


if __name__ == '__main__':
    main()
