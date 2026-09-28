import json,glob,re,os,sys,unicodedata
T=sys.argv[1]; raw=sys.argv[2]; pagedir=sys.argv[3]
R=json.load(open(raw)); B=R['block']; V=R.get('collectionview',{})
def norm(x):
    x=unicodedata.normalize('NFKC',x); return re.sub(r'[\*`~_#>\|\[\]\(\)!\$\\\s​‌‍﻿]','',x)
def cjk(x): return ''.join(ch for ch in x if '一'<=ch<='鿿')
def plain(t): return ''.join(s[0] for s in (t or []) if s).replace('\r','')
md={}
for f in glob.glob(f'{T}/{pagedir}/*.md'):
    txt=open(f,encoding='utf8').read()
    m=re.search(r'原文：\S+\?p=([A-Za-z0-9]{22})',txt)
    if m:
        t=re.sub(r'(?<!\\)</?(?:b|i|s|u|code|span|br|div|table|tr|td|details|summary|a)(?:\s[^>]*)?>','',txt)
        md[m.group(1)]=(norm(t),norm(re.sub(r'\]\([^)\s]*\)',']',t)),cjk(t),txt)
miss=[];checked=0;imgmiss=0
for pid,(a,b,c,txt) in md.items():
    st=list(B[pid].get('children') or [])
    while st:
        x=B.get(st.pop())
        if not x: continue
        if x.get('type')=='page' and x['id']!=pid: continue
        st+=x.get('children') or []
        if x.get('type')=='collectionview':
            for vid in (x.get('props') or {}).get('viewIds') or []:
                st+=[r for r in (V.get(vid,{}).get('children') or []) if B.get(r,{}).get('type')!='page']
        p=x.get('props') or {}
        if x.get('type')=='image':
            u=re.sub(r'\?.*','',p.get('displaySource',''))
            name=u.rsplit('/',1)[-1]
            if name and name not in txt: imgmiss+=1
        t=plain(p.get('title'))
        if x.get('type') in ('equation','code'): 
            if t.strip() and t.strip().split('\n')[0].strip() not in txt: miss.append((pid,x['type'],t[:60]))
            checked+=1; continue
        # 去掉行内公式与占位符
        pieces=['']
        for sg in (p.get('title') or []):
            if not sg: continue
            if len(sg)>1 and any(an[0] in('ei','ql','bql','p','r') for an in sg[1]): pieces.append('')
            else: pieces[-1]+=sg[0]
        pieces=[q for q in pieces if norm(q)]
        if not pieces: continue
        checked+=1
        bad=[]
        for q in pieces:
            n=norm(q)
            if n in a or n in b: continue
            cj=cjk(q)
            if len(cj)>=4 and cj in c: continue
            bad.append(q)
        if bad: miss.append((pid,x.get('type'),bad[0][:60]))
print('pages',len(md),'blocks checked',checked,'missing',len(miss),'image refs missing',imgmiss)
for m in miss[:20]: print(m)
