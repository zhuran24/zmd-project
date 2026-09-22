#!/usr/bin/env python3
"""任务7汇总文档核验；只写本目录输入与核验.json，kernel验收只读。"""
from pathlib import Path
import collections
import hashlib
import json
import re
import subprocess
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
E = HERE.parent.parent
ROOT = E.parents[2]
REPORT = HERE / '输入与核验.json'
data = json.loads(REPORT.read_text())
checks = []

def check(name, ok, detail=None):
    checks.append({'name': name, 'passed': bool(ok), 'detail': detail})

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

changed = [x['path'] for x in data['inputs'] if not Path(x['path']).is_file() or sha(Path(x['path'])) != x['sha256']]
check('全部542项输入保持', len(data['inputs']) == 542 and not changed, changed)
m = json.loads((E/'证据/终修/交付清单.json').read_text())
bad = [x['path'] for x in m['files'] if sha(Path(x['path'])) != x['sha256']]
check('55项终修清单匹配', len(m['files']) == 55 and not bad, bad)
for n in data['protected']:
    f = ROOT/n
    old = next(x['sha256'] for x in data['inputs'] if x['path'] == str(f))
    check('受保护文件:'+n, sha(f) == old)

names = ['本轮成果.md','未决去向.md','会议成果回填稿.md']
texts = {n:(E/n).read_text() for n in names}
main, todo, back = (texts[n] for n in names)
check('八任务章节', re.findall(r'^### 2\.(\d) 任务\d', main, re.M) == list('12345678'))
rows = re.findall(r'^\| F-(\d+) / N-F\d+[^\n]+', todo, re.M)
expected = list(range(19,31)) + list(range(32,46))
check('26项无缺漏或重复', list(map(int,rows)) == expected, rows)
stat = collections.Counter()
for l in todo.splitlines():
    if re.match(r'^\| F-\d+ /', l):stat[l.split('|')[2].strip()] += 1
check('26项状态计数', dict(stat) == {'部分':23,'本轮结清':2,'未动':1}, dict(stat))
urows = re.findall(r'^\| U([1-7])[^\n]+', todo, re.M)
prows = re.findall(r'^\| 相位§4-([1-6])[^\n]+', todo, re.M)
check('回路U1到U7', urows == list('1234567'))
check('相位六项', prows == list('123456'))
check('七加六均部分', all(l.split('|')[2].strip() == '部分' for l in todo.splitlines() if re.match(r'^\| (U[1-7]|相位§4-[1-6])', l)))
ids = sorted(set(re.findall(r'R7-(\d{2})',main)))
mapids = re.findall(r'^\| R7-(\d{2}) \|', back, re.M)
check('26结论全部有回填位置', ids == mapids == [f'{i:02d}' for i in range(1,27)])
check('A到H齐全', re.findall(r'^## ([A-H])\.',back,re.M)==list('ABCDEFGH'))
check('每节照旧被取代新增', all(back.count('### '+x)==8 for x in ['照旧','被取代','新增']))
missing=[]
for n,s in texts.items():
    for target in re.findall(r'\]\(([^\n]+?)\)',s):
        t=unquote(target.strip('<>').split('#',1)[0])
        if not t or '://' in t:continue
        if not (E/t).exists():missing.append([n,target])
check('全部文档文件链接可达',not missing,missing)
hashrows = re.findall(r'^\| \[[^\]]+\]\(([^)]+)\) \| `([a-f0-9]{64})` \|',main,re.M)
hashbad=[p for p,h in hashrows if sha(E/p)!=h]
check('本轮成果来源与34核心指纹',len(hashrows)==34 and not hashbad,{'entries':len(hashrows),'mismatch':hashbad})
check('保留新增整数环境缺口',all('F29' in texts[n] for n in names))
check('新桥界与旧恢复撤回分开',all('18/23' in texts[n] and '106' in texts[n] and 'null' in texts[n] for n in names))
check('owner只留部分扣格',all('同种' in texts[n] and '扣格' in texts[n] for n in names))
check('自审记录存在',(HERE/'读者自审.md').is_file())

argv=['target/release/kernel','verify-batch','会议成果/任务书7执行/证据/终修/runs','--config','规格/内核配置-v1.json']
p=subprocess.run(argv,cwd=ROOT/'求解器',capture_output=True,text=True)
data['readonly_replay']={'cwd':str(ROOT/'求解器'),'argv':argv,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
try: result=json.loads(p.stdout)
except json.JSONDecodeError:
    start=p.stdout.find('{');result=json.loads(p.stdout[start:]) if start>=0 else {}
cycles=result.get('cycles',[])
check('当前三周期实际只读重放',p.returncode==0 and result.get('read_only') is True and len(cycles)==3 and all(x['verification'].get('cycle_replayed') is True for x in cycles))
statuses=[]
for f in sorted((E/'证据/终修/runs').glob('*.json')):
    o=json.loads(f.read_text());statuses.append([f.name,o.get('status')])
check('三份仍为诊断',len(statuses)==3 and all(x[1]=='diagnostic_cycle' for x in statuses),statuses)
check('验收后原输入仍保持',all(sha(Path(x['path']))==x['sha256'] for x in data['inputs']))
data['checks']=checks
data['validation']='pass' if all(x['passed'] for x in checks) else 'fail'
data['outputs']=[{'path':str(E/n),'bytes':(E/n).stat().st_size,'sha256':sha(E/n)} for n in names]
data['outputs'] += [{'path':str(f),'bytes':f.stat().st_size,'sha256':sha(f)} for f in [HERE/'核验.py',HERE/'读者自审.md'] if f.is_file()]
data['output_self_hash_note']='输入与核验.json自身不列自身哈希'
REPORT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':data['validation'],'checks':len(checks),'failed':[x for x in checks if not x['passed']],'states':dict(stat),'inputs':len(data['inputs']),'current_cycles':len(cycles)},ensure_ascii=False))
raise SystemExit(0 if data['validation']=='pass' else 1)
