"""Refresh fixed-camera data from the official dataset page's current resource."""
import csv
import io
import json
import re
import sys
import urllib.request
import zipfile
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
PAGE = 'https://data.gov.tw/dataset/13940'
ROADS = {'一':'1','二':'2','三':'3','四':'4','五':'5','六':'6','八':'8','十':'10'}


class DatasetPage(HTMLParser):
    def __init__(self):
        super().__init__(); self.capture = False; self.parts = []; self.scripts = []
    def handle_starttag(self, tag, attrs):
        if tag == 'script' and dict(attrs).get('type') == 'application/ld+json':
            self.capture = True; self.parts = []
    def handle_data(self, data):
        if self.capture: self.parts.append(data)
    def handle_endtag(self, tag):
        if tag == 'script' and self.capture:
            self.scripts.append(''.join(self.parts)); self.capture = False


def discover(page):
    parser = DatasetPage(); parser.feed(page)
    urls = []
    for script in parser.scripts:
        obj = json.loads(script)
        for item in obj if isinstance(obj, list) else [obj]:
            if not isinstance(item, dict) or str(item.get('identifier')) != '13940': continue
            for entry in item.get('distribution', []):
                if entry.get('encodingFormat', '').upper() == 'CSV': urls.append(entry.get('contentUrl', ''))
    if len(urls) != 1: raise ValueError('官方下載網址不唯一')
    url = urls[0]; parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname != 'www.tgos.tw' or parsed.username or parsed.password or parsed.port not in (None, 443) or parsed.query or parsed.fragment or not parsed.path.startswith('/tgos/VirtualDir/Product/'):
        raise ValueError('官方下載網址不受信任')
    filename = unquote(parsed.path.rsplit('/', 1)[-1])
    match = re.fullmatch(r'(\d{3})(\d{2})(\d{2})-國道公路固定式測速照相地點\.zip', filename)
    if not match: raise ValueError('官方檔名日期或格式變更')
    source_date = date(int(match[1]) + 1911, int(match[2]), int(match[3]))
    if source_date > date.today(): raise ValueError('官方檔案日期異常')
    return urlunsplit((parsed.scheme, parsed.netloc, quote(unquote(parsed.path), safe='/'), '', '')), source_date.isoformat()


def parse_archive(raw, source_date):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        files = [x for x in archive.infolist() if x.filename.lower().endswith('.csv') and not x.filename.lower().endswith('manifest.csv')]
        if len(files) != 1 or files[0].file_size > 20_000_000: raise ValueError('資料檔數量或大小異常')
        rows = list(csv.DictReader(io.StringIO(archive.read(files[0]).decode('utf-8-sig'), newline='')))
    if not 20 <= len(rows) <= 10000: raise ValueError('資料筆數異常')
    locations = []; seen = set()
    for row in rows:
        place = row['設置地點'].strip()
        if place.startswith('臺2己線'): continue
        match = re.match(r'國道([一二三四五六八十])號', place)
        if not match or row['型式'] != '雷達' or row['取締項目'] != '超速': raise ValueError('設備類型或地點無法辨識')
        direction = re.search(r'(南北向|南向|北向|東向|西向)', place)
        ident = row['設備編號'].strip()
        if not direction or not ident or ident in seen: raise ValueError('方向或設備編號異常')
        seen.add(ident)
        distance = re.search(r'(\d+(?:\.\d+)?)公里', place)
        km = float(distance[1]) if distance else None
        if km is not None and not 0 <= km <= 500: raise ValueError('公里數異常')
        limit = int(row['速限'])
        if not 30 <= limit <= 130: raise ValueError('速限異常')
        try:
            lat, lon = float(row['座標緯度']), float(row['座標經度'])
            if not 21 <= lat <= 26.5 or not 119 <= lon <= 122.5: raise ValueError()
        except ValueError: lat = lon = None
        locations.append({'id':'npa-'+ident,'road':'國道'+ROADS[match[1]]+'號','place':place,'direction':direction[1],
            'km':km,'lat':lat,'lon':lon,'limit':limit,'kind':'fixed','sourceDate':source_date,'sourceUrl':PAGE})
    if len(locations) < 20: raise ValueError('國道筆數異常')
    return locations


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('來源發生轉址，須人工檢查')


def fetch(url, maximum):
    request = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0 RoadCameraLookup/1.0'})
    with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
        data = response.read(maximum + 1)
    if len(data) > maximum: raise ValueError('來源檔案過大')
    return data


def main():
    try:
        url, source_date = discover(fetch(PAGE, 2_000_000).decode('utf8'))
        out = ROOT / 'data' / 'locations.js'
        if out.exists():
            existing = out.read_text(encoding='utf8')
            previous = json.loads(existing[existing.index('(')+1:existing.rindex(')')])
            if source_date < previous.get('meta', {}).get('sourceDate', ''):
                raise ValueError('來源日期早於目前快照')
        records = parse_archive(fetch(url, 20_000_000), source_date)
        timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
        payload = {'meta':{'sourceDate':source_date, 'retrievedAt':timestamp, 'status':'imported',
            'notice':f'官方檔案日期 {source_date}，收錄 {len(records)} 筆國道地點；資料不定期更新，請核對最新公告。', 'sourceUrl':PAGE}, 'locations':records}
        tmp = out.with_suffix('.js.tmp')
        tmp.write_text('window.SPEED_CAMERA_DATA = Object.freeze(' + json.dumps(payload,ensure_ascii=False).replace('<','\\u003c') + ');\n',encoding='utf8')
        tmp.replace(out)
        print(f'更新成功，來源日期 {source_date}，{len(records)} 筆')
        return 0
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, zipfile.BadZipFile) as exc:
        print(f'更新失敗，保留先前資料：{type(exc).__name__}', file=sys.stderr)
        return 1


if __name__ == '__main__': sys.exit(main())
