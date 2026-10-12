import sys,requests,subprocess,json
from pathlib import Path
url,name=sys.argv[1:3]
out=Path(__file__).parent/'全文';out.mkdir(exist_ok=True)
r=requests.get(url,timeout=40,stream=True);r.raise_for_status()
limit=99_000_000
if int(r.headers.get('Content-Length',0))>limit:raise SystemExit('超过下载限制')
f=out/(name+'.pdf');size=0
with f.open('wb') as w:
 for b in r.iter_content(65536):
  size+=len(b)
  if size>limit:raise SystemExit('超过下载限制')
  w.write(b)
if not f.read_bytes()[:4]==b'%PDF':raise SystemExit('不是PDF')
subprocess.run(['pdftotext','-layout',str(f),str(f.with_suffix('.txt'))],check=True)
(f.with_suffix('.source.json')).write_text(json.dumps({'url':url,'bytes':size},ensure_ascii=False))
print(f.with_suffix('.txt'))
