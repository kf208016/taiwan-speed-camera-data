"""Resolve unambiguous exact intersections using NLSC road-crossing service.

Positions describe the intersection, not an exact camera or its current deployment.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
try:
    from .import_mobile import parse_mobile
except ImportError:
    from import_mobile import parse_mobile

ROOT = Path(__file__).resolve().parents[1]
API = 'https://api.nlsc.gov.tw/idc/ListRoadCross/B/'
TOWNS = {'中區':'B01','東區':'B02','南區':'B03','西區':'B04','北區':'B05','西屯區':'B06','南屯區':'B07','北屯區':'B08','豐原區':'B09','東勢區':'B10','大甲區':'B11','清水區':'B12','沙鹿區':'B13','梧棲區':'B14','后里區':'B15','神岡區':'B16','潭子區':'B17','大雅區':'B18','新社區':'B19','石岡區':'B20','外埔區':'B21','大安區':'B22','烏日區':'B23','大肚區':'B24','龍井區':'B25','霧峰區':'B26','太平區':'B27','大里區':'B28','和平區':'B29'}
PATTERN = re.compile(r'^([\u4e00-\u9fff\d]+(?:路|街|大道)(?:[一二三四五六七八九十\d]+段)?)與([\u4e00-\u9fff\d]+(?:路|街|大道)(?:[一二三四五六七八九十\d]+段)?)(?:路口|口)$')


def fetch_crossings(town, road):
    url = API + town + '/' + urllib.parse.quote(road, safe='')
    request = urllib.request.Request(url, headers={'User-Agent':'RoadCameraLookup/1.0'})
    with urllib.request.urlopen(request, timeout=20) as response:
        if not response.geturl().startswith('https://api.nlsc.gov.tw/idc/ListRoadCross/'):
            raise ValueError('來源轉址異常')
        raw = response.read(1_000_001)
    if len(raw) > 1_000_000 or b'<!DOCTYPE' in raw.upper(): raise ValueError('路口回應格式異常')
    root = ET.fromstring(raw)
    if root.tag != 'crossRoads': raise ValueError('路口回應格式異常')
    return [{'name': e.findtext('name'), 'lon': float(e.findtext('x')), 'lat': float(e.findtext('y'))} for e in root.findall('crossRoad')]


def resolve(records, get_crossings):
    cache = {}; located = {}; failures = []
    for item in records:
        district, sep, place = item['place'].partition(' ')
        match = PATTERN.fullmatch(place)
        if not sep or not match or district not in TOWNS: continue
        a, b = match.groups(); town = TOWNS[district]
        try:
            for road in (a, b):
                if (town, road) not in cache: cache[town, road] = get_crossings(town, road)
            forward = [x for x in cache[town,a] if x['name'] == b]
            reverse = [x for x in cache[town,b] if x['name'] == a]
            if len(forward) != 1 or len(reverse) != 1: continue
            x, y = forward[0], reverse[0]
            if not (23 <= x['lat'] <= 25.5 and 119 <= x['lon'] <= 122): continue
            # Independent reverse road lookup must agree within about 30 metres.
            if abs(x['lat']-y['lat']) > 0.00025 or abs(x['lon']-y['lon']) > 0.00025: continue
            located[item['place']] = {'lat':x['lat'], 'lon':x['lon'], 'road1':a, 'road2':b, 'townCode':town,
                'coordinateSource':'https://data.gov.tw/dataset/167920', 'precision':'intersection'}
        except (OSError, ValueError, ET.ParseError, TypeError) as exc:
            failures.append(f'{district} {a}：{type(exc).__name__}')
    return located, failures


def main():
    records = parse_mobile((ROOT/'official-mobile.csv').read_bytes())
    def throttled(town, road):
        result = fetch_crossings(town, road); time.sleep(0.5); return result
    located, errors = resolve(records, throttled)
    if errors:
        print('官方路口服務部分查詢失敗，不覆寫既有定位結果：', *errors, sep='\n', file=sys.stderr); return 1
    result = {'retrievedAt':datetime.now(timezone.utc).isoformat(timespec='seconds'), 'locations':located}
    path = ROOT/'data'/'mobile-intersections.json'; tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8'); tmp.replace(path)
    print(f'雙向交叉核對 {len(located)} 個路口；其餘保留無座標')
    return 0


if __name__ == '__main__': sys.exit(main())
