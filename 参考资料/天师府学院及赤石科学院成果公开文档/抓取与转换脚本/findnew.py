import json,glob,re,collections,sys
crawled={f.split('/')[-1][:-5] for f in glob.glob('blocks/*.json')}
bad=set(json.load(open('unreachable.json'))) if glob.glob('unreachable.json') else set()
allb={}
for f in glob.glob('blocks/*.json'):
    for k,v in json.load(open(f)).items():
        if isinstance(v,dict): allb[k]=v
SP='300000000$NingWbZZPfWp'
new=set(); ext=set()
for k,v in allb.items():
    if not k.startswith('block:'): continue
    if v.get('type')=='page': new.add(v['id'])
    for seg in (v.get('props') or {}).get('title') or []:
        if len(seg)>1:
            for a in seg[1]:
                if a[0] in ('t','ql','p'):
                    s=json.dumps(a[1],ensure_ascii=False)
                    new.update(re.findall(r'DTmluZ1diWlpQZldw\?p=([A-Za-z0-9]{22})', s))
                    for u in re.findall(r'https://docs\.qq\.com/[^"\s]+', s):
                        if 'DTmluZ1diWlpQZldw' not in u: ext.add(u)
                if a[0]=='bql' and a[1][1]==SP: new.add(a[1][0])
                if a[0]=='m': new.add(str(a[1]).split('-')[0])
    if v.get('type')=='bookmark':
        u=v['props'].get('linkUrl','')
        new.update(re.findall(r'DTmluZ1diWlpQZldw\?p=([A-Za-z0-9]{22})', u))
        if 'docs.qq.com' in u and 'DTmluZ1diWlpQZldw' not in u: ext.add(u)
todo=sorted(new-crawled-bad)
json.dump(todo,open('todo.json','w'))
json.dump(sorted(ext),open('external_links.json','w'),ensure_ascii=False,indent=0)
print('todo',len(todo),'ext',len(ext))
