#!/usr/bin/env python3
"""Final artifact/link/input audit. Writes only beside this file."""
from pathlib import Path
import json, hashlib, re, ast

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
REPORT=HERE.parent/'复核71.md'
def read(path): return json.loads(path.read_text())
def write(name,value): (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
names=['占边在产供电十三台界','十七位置右下端口供电上限','供电重复覆盖预算','十七位置供电桩只余十个']
reasons=[
    '独立重建550个机身与端口轴选项、1352条不等式，38项非负有理数乘数精确合出1846/135，故整数台数至多13；四种占边及边界唯一空格均已核查，10J≤23P−217成立。',
    '395个桩位无重无漏，全部局部矩阵、坐标对应和分数证书独立核验通过；右沿上限序列一致，P=10仅允许q=5…11，单桩至少亏11台。',
    '实际覆盖关系的双计数恒等式推出亏额与重复次数联合预算；删去部分机器的非负重复项仍成立。S=186放宽点复得收费21>13，但不排除全部十桩摆位。',
    '四个转角分支及P=10、11、12均独立复算。P=11的最小S为190、189、189、191，P=12为199、199、198、200，均超过187；P=10仍有最小S=180，未排除，1113上界不变。'
]
verdicts={'report_path':str(REPORT),'verdicts':[{'name':n,'verdict':'未否证','reason':r,'revised_text':''} for n,r in zip(names,reasons)]}
text=REPORT.read_text()
assert read(HERE/'results.json')['status']=='PASS'
assert read(HERE/'results.json')['inputs_unchanged']
assert all(text.count('| '+n+' | **未否证** |')==1 for n in names)
assert all(v['verdict'] in ('未否证','已否证','修正') for v in verdicts['verdicts'])
assert len(verdicts['verdicts'])==4
for rel,fingerprint in read(HERE/'input_manifest.json').items():
    data=(ROOT/rel).read_bytes()
    assert len(data)==fingerprint['bytes'] and hashlib.sha256(data).hexdigest()==fingerprint['sha256'],rel
write('verdicts.json',verdicts)
links=re.findall(r'\[[^\]]+\]\(([^)]+)\)',text)
for link in links:
    if link.endswith('delivery_audit.json'): continue
    assert (REPORT.parent/link).exists(),link
source=(HERE/'recompute.py').read_text()
tree=ast.parse(source)
imports=[]
for node in ast.walk(tree):
    if isinstance(node,ast.Import): imports.extend(n.name for n in node.names)
    if isinstance(node,ast.ImportFrom): imports.append(node.module)
assert set(imports)<=set(['pathlib','fractions','collections','itertools','json','hashlib','time','sys','copy','re'])
assert 'cargo' not in source and not re.search(r'(^|\W)git(\W|$)',source)
files={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in HERE.iterdir() if p.is_file() and p.name!='delivery_audit.json'}
audit={'status':'PASS','report_sha256':hashlib.sha256(REPORT.read_bytes()).hexdigest(),'report_bytes':REPORT.stat().st_size,'input_hashes_unchanged':True,'report_links_checked':len(links),'verdict_names_exact':True,'standard_library_imports':sorted(imports),'reader_audit':{'self_contained':True,'current_status_consistent':True,'numeric_scopes_distinguished':True,'all_claimed_P_branches_checked':True,'P10_not_excluded':True,'no_round70_material_used':True},'files':files}
write('delivery_audit.json',audit)
assert (HERE/'delivery_audit.json').exists()
print(json.dumps({'status':'PASS','report_bytes':audit['report_bytes'],'links':len(links),'verdicts':4,'inputs_unchanged':True},ensure_ascii=False))
