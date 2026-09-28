import sys,glob,re,os,html as H
from markdown_it import MarkdownIt
from html.parser import HTMLParser
T=sys.argv[1]
md=MarkdownIt('commonmark',{'html':True}).enable(['table','strikethrough'])
class P(HTMLParser):
    def __init__(s): super().__init__(); s.t=[]; s.skip=0
    def handle_starttag(s,tag,a):
        if tag in('pre','code'): s.skip+=1
    def handle_endtag(s,tag):
        if tag in('pre','code'): s.skip-=1
    def handle_data(s,d):
        if not s.skip: s.t.append(d)
issues=[]
for f in sorted(glob.glob(T+'/页面/*.md')+glob.glob(T+'/外链文档/*.md')):
    src=open(f,encoding='utf8').read()
    out=md.render(src)
    fences=len(re.findall(r'^\s*`{3,}\S*\s*$',src,re.M))//2
    pres=out.count('<pre>')
    if pres!=fences: issues.append((os.path.relpath(f,T),'pre',pres,'fences',fences))
    p=P(); p.feed(out); text=''.join(p.t)
    text=re.sub(r'\$\$.*?\$\$','',text,flags=re.S); text=re.sub(r'\$[^$\n]*\$','',text)
    for pat,name in [(r'\\',"backslash"),(r'\*\*','**'),(r'~~','~~'),(r'(?<![\w/])\[[^\]]*\]\([^)]*\)','rawlink')]:
        m=re.findall(pat,text)
        if m: issues.append((os.path.relpath(f,T),name,len(m),re.search(pat,text) and text[max(0,re.search(pat,text).start()-30):re.search(pat,text).start()+40].replace('\n',' ')))
print(len(issues))
for i in issues[:40]: print(i)
