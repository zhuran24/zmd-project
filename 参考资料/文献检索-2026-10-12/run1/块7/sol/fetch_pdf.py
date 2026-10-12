"""Download a primary-source PDF under this directory; cap at 20 MB."""
import sys
from pathlib import Path
import requests
import subprocess

name, url = sys.argv[1:3]
root = Path(__file__).resolve().parent / 'fulltext'
root.mkdir(exist_ok=True)
out = root / (name + '.pdf')
limit = 20 * 1024 * 1024
with requests.get(url, timeout=30, stream=True) as r:
    r.raise_for_status()
    if int(r.headers.get('Content-Length', 0)) > limit:
        raise SystemExit('PDF exceeds 20 MB cap')
    data = bytearray()
    for chunk in r.iter_content(65536):
        data.extend(chunk)
        if len(data) > limit:
            raise SystemExit('PDF exceeds 20 MB cap')
if not data.startswith(b'%PDF'):
    raise SystemExit('Response is not PDF')
out.write_bytes(data)
subprocess.run(['pdftotext', '-layout', str(out), str(out.with_suffix('.txt'))], check=True)
out.with_suffix('.source.txt').write_text(url + '\n')
print(out.with_suffix('.txt'), len(data))
