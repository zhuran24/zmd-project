import json,glob,re,os,sys,urllib.parse,unicodedata
T=sys.argv[1]
def norm(x):
    x=unicodedata.normalize('NFKC',x)
    return re.sub(r'[\*`~_#>\|\[\]\(\)!\$\\\s​‌‍﻿]','',x)
def cjk(x):
    return ''.join(ch for ch in x if '一'<=ch<='鿿')
bad=[]
for f in glob.glob(T+'/**/*.md',recursive=True):
    for m in re.finditer(r'\]\(([^)\s]+)\)', open(f,encoding='utf8').read()):
        u=m.group(1)
        if re.match(r'https?:',u) or u.startswith('#'): continue
        path=os.path.normpath(os.path.join(os.path.dirname(f),urllib.parse.unquote(u.split('#')[0])))
        if not os.path.exists(path): bad.append((os.path.relpath(f,T),u))
        elif '#' in u and re.fullmatch(r'[A-Za-z0-9]{22}', u.split('#',1)[1]):
            anc=u.split('#',1)[1]
            if f'<a id="{anc}"></a>' not in open(path,encoding='utf8').read(): bad.append((os.path.relpath(f,T),u,'anchor'))
print('broken local links/anchors',len(bad)); print(bad[:10])
TAGS=r'(?<!\\)</?(?:b|i|s|u|code|span|br|div|table|tr|td|details|summary|a)(?:\s[^>]*)?>'
mdv={}
for f in glob.glob(T+'/页面/*.md'):
    txt=open(f,encoding='utf8').read()
    m=re.search(r'原文：\S+\?p=([A-Za-z0-9]{22})',txt)
    if not m: continue
    t=re.sub(TAGS,'',txt)
    a=re.sub(r'\]\([^)\s]*\)',']',t)            # 去掉链接目标
    b=re.sub(r'\$\$.*?\$\$','',a,flags=re.S); b=re.sub(r'\$[^$\n]*\$','',b)   # 再去掉公式
    mdv[m.group(1)]=(norm(t),norm(a),norm(b),cjk(t))
miss_total=0; per=[]
for pj in sorted(glob.glob('pages/*.json')):
    d=json.load(open(pj)); pid=d['meta']['id']
    if pid not in mdv: per.append((d['meta']['title'],'NO MD')); continue
    text=d['text'].split('\nBack reference\n')[0]
    lines=[l.strip() for l in text.split('\n')][1:]
    miss=[]
    for l in lines:
        n=norm(l)
        if not n or re.fullmatch(r'\d+\.?',n) or n in ('Untitled','TOC') or re.fullmatch(r'\d+ people have liked it|If you like it, please give it a like~',l): continue
        if any(n in v for v in mdv[pid][:3]): continue
        c=cjk(l)
        if len(c)>=4 and c in mdv[pid][3]: continue
        miss.append(l[:100])
    if miss: per.append((d['meta']['title'],len(miss),miss[:8]))
    miss_total+=len(miss)
print('pages checked',len(glob.glob('pages/*.json')),'missing lines',miss_total)
for x in per: print(x)
