"""Read-only diagnostic of the official TGOS download response."""
import json
import urllib.error
import urllib.request

from update_fixed import PAGE, NoRedirect, discover, fetch


def main():
    url, date = discover(fetch(PAGE, 2_000_000).decode('utf8'))
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 RoadCameraLookup/1.0'})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
            print(json.dumps({'status': response.status, 'source_date': date, 'size': len(response.read(20_000_001))}))
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(4096).decode('utf-8', 'replace').lower()
            markers = {key: key in body for key in ('geoblock', 'geo-block', 'country', 'forbidden', 'access denied', 'cloudflare', 'akamai')}
            print(json.dumps({'status': exc.code, 'source_date': date, 'body_markers': markers,
                              'header_names': sorted(k.lower() for k in exc.headers.keys())}))
        finally:
            exc.close()
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
