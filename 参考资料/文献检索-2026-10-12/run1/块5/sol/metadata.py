import concurrent.futures,json,re,requests
from pathlib import Path
root=Path(__file__).resolve().parent
pool=[json.loads(x) for x in (root/'pool.jsonl').read_text().splitlines()]
selected=[r for r in pool if not r.get('abstract') and (r.get('chain_links') or r['key'] in ['W1991618223','W2163871914','W2477905266','W1987163060','W2095218721','W2080891786','W2594791159','W1487188659'])]
def fetch(r):
 try:
  d=requests.get('https://api.crossref.org/works/'+r['doi'],timeout=25).json()['message']
  a=re.sub('<[^>]+>',' ',d.get('abstract',''));a=' '.join(a.split())
  return {'key':r['key'],'requested_doi':r['doi'],'title':d.get('title'), 'abstract':a,'link':d.get('link'), 'src':'publisher-deposited Crossref metadata'}
 except Exception as e:return {'key':r['key'],'error':str(e)}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
 rows=list(ex.map(fetch,selected))
(root/'primary_metadata.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
for r in rows:print(r['key'],r.get('title'),r.get('abstract','')[:1100],r.get('error',''))
