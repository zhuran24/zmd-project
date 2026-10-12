import requests, subprocess, sys
from pathlib import Path
out=Path(__file__).resolve().parent/'cache'/sys.argv[1]
r=requests.get(sys.argv[2],stream=True,timeout=40)
r.raise_for_status()
limit=99_000_000
if int(r.headers.get('Content-Length','0'))>limit: raise SystemExit('over size limit')
data=bytearray()
for c in r.iter_content(65536):
 data.extend(c)
 if len(data)>limit: raise SystemExit('over size limit')
if not data.startswith(b'%PDF'): raise SystemExit('not PDF')
out.write_bytes(data)
subprocess.run(['pdftotext','-layout',str(out),str(out.with_suffix('.txt'))],check=True)
print(out.with_suffix('.txt'),len(data))
