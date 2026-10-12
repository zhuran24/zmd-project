import importlib.util,json,sys,subprocess,hashlib,requests
from pathlib import Path
P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('lit',P/'lit_local.py');lit=importlib.util.module_from_spec(spec);spec.loader.exec_module(lit)

def ingest(keys):
 for key in keys:
  try:
   w=lit.resolve(key);r=lit._norm_oa(w);lit.add_pool(str(P/'pool.jsonl'),[r],'identity:'+key)
   print(json.dumps(r,ensure_ascii=False),flush=True)
  except Exception as e:print('ERROR',key,str(e),flush=True)

def download(name,url):
 target=P/'fulltext'/name;target.parent.mkdir(exist_ok=True)
 if target.with_suffix('.txt').exists():return str(target.with_suffix('.txt'))
 r=requests.get(url,stream=True,timeout=35,headers=lit.UA,verify="/etc/ssl/certs/ca-certificates.crt");r.raise_for_status()
 if int(r.headers.get('Content-Length','0'))>100_000_000:raise ValueError('file over 100MB')
 size=0;chunks=[]
 for chunk in r.iter_content(65536):
  size+=len(chunk)
  if size>100_000_000:r.close();raise ValueError('download exceeds100MB')
  chunks.append(chunk)
 data=b''.join(chunks)
 if not data.startswith(b'%PDF'):raise ValueError('not PDF '+url)
 target.with_suffix('.pdf').write_bytes(data)
 subprocess.run(['pdftotext','-layout',str(target.with_suffix('.pdf')),str(target.with_suffix('.txt'))],check=True)
 with (P/'downloads.jsonl').open('a') as f:f.write(json.dumps({'file':name,'url':url,'bytes':size,'sha256':hashlib.sha256(data).hexdigest()})+'\n')
 return str(target.with_suffix('.txt'))

if __name__=='__main__':
 if sys.argv[1]=='ingest':ingest(sys.argv[2:])
 elif sys.argv[1]=='download':print(download(sys.argv[2],sys.argv[3]))
