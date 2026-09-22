#!/usr/bin/env python3
"""只读被审材料；所有输出限本席目录。作者脚本仅在内存重定向write后重放。"""
from pathlib import Path
from fractions import Fraction as F
from itertools import combinations
import ast, contextlib, hashlib, io, json, re, traceback

E = Path(__file__).resolve().parent
B = E.parents[2]
ROOT = B.parents[2]
A = B / '证据/相位认证'
def read(p):
    return json.loads(p.read_text())
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name, value):
    p = E / name
    assert p.resolve().is_relative_to(E.resolve())
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
checks = []
def passed(name, detail):
    checks.append({'name': name, 'result': 'PASS', 'detail': detail})

# 审查对象14份全部逐字节读、UTF-8解码；JSON递归读取用于后续逐项比对。
target_names = ['交付清单.json','工具可用性.json','核验.log','核验.py','核验结果.json',
                '状态与参数.json','窗口与算术.json','结果.json','设计律核查.json','读取核查.json',
                '读者自审.md','输入指纹.json']
targets = [B/'相位离线与认证范围.md', B/'规格修改稿-任务6.md'] + [A/n for n in target_names]
extra = [ROOT/n for n in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt','候选约束.txt']]
extra += [B.parent/'任务书7草案.md', B.parent/'主会话三审-0920.md']
extra += [B/n for n in ['植物运行试点.md','送料与接口.json','调试与释放.md','调试后状态.json',
                      '仓库接收与循环对应.md','复核/否证-任务5.md',
                      '证据/植物运行/局部结构.json','证据/植物运行/交付清单.json',
                      '证据/调试释放/交付清单.json','证据/否证/任务5/审查输入指纹.json',
                      '证据/否证/任务5/结构化结果.json']]
extra += [ROOT/'求解器/规格/受限转移定义.md']
rows = []
for p in targets + extra:
    raw = p.read_bytes(); txt = raw.decode('utf-8')
    if p.suffix == '.json': json.loads(txt)
    if p.suffix == '.py': ast.parse(txt)
    rows.append({'path': str(p), 'sha256': sha(p), 'bytes': len(raw),
                 'lines': len(txt.splitlines()), 'mtime_ns': p.stat().st_mtime_ns,
                 'role': 'review_target' if p in targets else 'dependency'})
write('审查输入指纹.json', {'schema': 'task6-independent-review-inputs-v1', 'files': rows})
assert len(targets) == 14
assert sha(ROOT/'《明日方舟：终末地》游戏规则.txt').startswith('d150b86b398f')
passed('指定14份被审文件完整读取', {'targets': len(targets), 'dependencies': len(extra)})

# 全部清单、读取核查和输出日志的一致性，而非只读PASS标签。
sealed = read(A/'交付清单.json')
for r in sealed['files']:
    p = Path(r['path']); assert sha(p) == r['sha256'] and p.stat().st_size == r['bytes'], str(p)
inputs = read(A/'输入指纹.json')['files']
audit = {r['path']: r for r in read(A/'读取核查.json')['files']}
for r in inputs:
    p = Path(r['path']); raw = p.read_bytes(); txt = raw.decode('utf-8')
    assert sha(p) == r['sha256'] and len(raw) == r['bytes'], str(p)
    assert p.stat().st_mtime_ns == r['mtime_ns'] and len(txt.splitlines()) == r['lines'], str(p)
    if p.suffix == '.json': json.loads(txt)
    if p.suffix == '.py': ast.parse(txt)
    assert audit[str(p)]['sha256'] == r['sha256'] and audit[str(p)]['bytes_read'] == len(raw)
assert len(inputs) == len(audit) == 93
passed('作者交付封存及93份输入读取记录', {'sealed':len(sealed['files']), 'inputs':len(inputs)})

# 作者核验原文已审读。只替换write函数，所有读路径及断言保持原文。
src = A/'核验.py'
tree = ast.parse(src.read_text(), filename=str(src))
replaced = 0
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name == 'write':
        node.body = ast.parse("_review_write('作者重放/' + name, value)").body
        replaced += 1
assert replaced == 1
ast.fix_missing_locations(tree)
log = io.StringIO()
scope = {'__file__': str(src), '__name__':'__review_replay__', '_review_write':write}
try:
    with contextlib.redirect_stdout(log): exec(compile(tree, str(src), 'exec'), scope)
except Exception:
    with contextlib.redirect_stdout(log): traceback.print_exc()
    (E/'作者重放.log').write_text(log.getvalue())
    raise
(E/'作者重放.log').write_text(log.getvalue())
for name in ['读取核查.json','设计律核查.json','窗口与算术.json','核验结果.json']:
    assert read(E/'作者重放'/name) == read(A/name), name
assert log.getvalue() == (A/'核验.log').read_text()
passed('作者核验隔离重放', {'write_redirect_only':True,'checks':len(scope['checks']),
                       'all_four_json_equal':True,'stdout_equal':True,'scope':'作者检查可复现，不替代独立证明'})

# 独立配方矩阵：从规则重新解析，以输入负产出正建矩阵。
recipes = []
kind = None
for line_no, line in enumerate((ROOT/'《明日方舟：终末地》游戏规则.txt').read_text().splitlines(), 1):
    s = line.strip()
    if '→' not in s:
        if s in ['粉碎机','精炼炉','研磨机','塑形机','配件机','种植机','采种机','封装机','灌装机']: kind=s
        continue
    left, rest = s.split(' → '); right, duration = rest.split('，')
    def parse_side(part):
        return {term.split(' ',1)[1]: int(term.split(' ',1)[0]) for term in part.split(' ＋ ')}
    recipes.append({'line':line_no,'kind':kind,'input':parse_side(left),'output':parse_side(right),
                    'duration':int(duration.split()[0])})
items = sorted(set().union(*(r['input'].keys()|r['output'].keys() for r in recipes)) -
               {'蓝铁矿','源矿','高容谷地电池','精选荞愈胶囊'})
base = [[F(r['output'].get(i,0)-r['input'].get(i,0)) for r in recipes]+[F(0)] for i in items]
def eliminate(mat):
    m = [r[:] for r in mat]; pivots = []; row = 0; n=len(recipes)
    for col in range(n):
        found = next((j for j in range(row,len(m)) if m[j][col]),None)
        if found is None: continue
        m[row],m[found]=m[found],m[row]
        div=m[row][col]; m[row]=[x/div for x in m[row]]
        for j in range(len(m)):
            if j != row:
                factor=m[j][col]; m[j]=[x-factor*y for x,y in zip(m[j],m[row])]
        pivots.append(col); row+=1
    assert len(pivots)==n and all(any(r[:n]) or r[n]==0 for r in m)
    x=[F(0)]*n
    for j,c in enumerate(pivots): x[c]=m[j][-1]
    assert all(sum(a*b for a,b in zip(r[:-1],x))==r[-1] for r in mat)
    return x
def work_row(k,n): return [F(r['duration'] if r['kind']==k else 0) for r in recipes]+[F(n)]
d = base + [work_row(k,n) for k,n in [('粉碎机',68),('精炼炉',51),('配件机',6),('种植机',32),('采种机',16),('封装机',3)]]
narrow = base + [work_row('精炼炉',51), work_row('封装机',3), [F(r['line']==89) for r in recipes]+[F(0)]]
rates = eliminate(d); assert rates == eliminate(narrow)
by_line = {str(r['line']):str(v) for r,v in zip(recipes,rates)}
assert by_line['111']=='3/5' and by_line['114']=='11/20' and by_line['89']=='0'
assert all(v>=0 for v in rates)
passed('独立有理数配方消元', {'recipes':len(recipes),'internal_items':len(items),'rates_by_rule_line':by_line,
                     'D_and_219_same_rates':True,'scope':'只核真实周期、零非成品入库及给定连续制造前件'})

# 单门独立事件参考：半tick网格旧窗枚举；不调用作者saturate。
case_count = 0; item_checks = 0; count_checks = 0
for k in range(1,5):
    histories = [()]
    for size in range(1,k+1):
        for tail in combinations(range(2,10),size-1):
            h=(F(0),)+tuple(F(x,2) for x in tail)
            if all(b-a>=1 for a,b in zip(h,h[1:])): histories.append(h)
    for hist in histories:
        start_t = hist[-1] if hist else F(0)
        for delay in [F(0),F(1,3),F(1),F(7,2),F(6)]:
            t0=start_t+delay
            expires=F(5) if hist else None
            used=len(hist)
            release=hist[-1]+1 if hist else t0
            accepts=[]; now=t0
            while len(accepts)<50:
                now=max(now,release)
                if expires is not None and now>=expires: expires=None; used=0
                if expires is not None and used==k: now=expires; expires=None; used=0
                if expires is None: expires=now+5
                accepts.append(now); used+=1; release=now+1
            for j,t in enumerate(accepts):
                assert t<=t0+6+5*(j//k)+(j%k)
                item_checks+=1
            for dur in range(41):
                lower=k*(max(dur-6,0)//5)
                assert sum(t<=t0+dur for t in accepts)>=lower
                count_checks+=1
            case_count+=1
passed('独立单门最晚收件及数量界',{'cases':case_count,'item_checks':item_checks,'count_checks':count_checks,
                        'scope':'条件工作过程的有限样本查错；一般证明见报告，不作全参数枚举'})

# 直接链所有短状态的两种公平工作次序闭包一致；1旧成熟、2新件。
from itertools import product
def close_chain(start, backward):
    s=list(start); moves=0
    while True:
        changed=False
        edges=range(len(s)-2,-1,-1) if backward else range(len(s)-1)
        for i in edges:
            if s[i]==1 and s[i+1]==0:
                s[i],s[i+1]=0,2; moves+=1; changed=True
        if not changed: return s,moves
chain_cases=0
for n in range(1,7):
    for start in product(range(3),repeat=n):
        a,m=close_chain(start,False); b,_=close_chain(start,True)
        assert a==b and m<=start.count(1)
        chain_cases+=1
passed('无争用链旧件闭包',{'states':chain_cases,'lengths':'1..6','scope':'局部闭包，固定闭边界；不含制造或多口权限'})

# 三份接口覆盖边界核对；不把null速率和条件定理升级为整厂通过。
plant=read(B/'送料与接口.json'); phase=read(A/'状态与参数.json'); debug=read(B/'调试后状态.json')
assert len(phase['claims'])==12 and len(phase['open_items'])==9
assert not phase['full_layout_certified'] and not phase['certificate_instantiated']
assert all(f['proven_actual_rate_per_tick'] is None for c in plant['candidates'] for f in c['feeds'])
passed('三席接口的整厂前件状态',{'actual_feed_rates':'629项均为null','phase_full_layout_certified':False,
                              'phase_certificate_instantiated':False,'debug_top_level_keys':list(debug)})

for r in rows:
    p=Path(r['path']); assert sha(p)==r['sha256'] and p.stat().st_mtime_ns==r['mtime_ns'],str(p)
passed('本次核验后全部审查输入字节及mtime保持',len(rows))
result={'status':'PASS','exit_status':0,'command':'python -B '+str(E/'独立核验.py'),
        'checks':checks,'scope':'14份交付覆盖、独立算术查错与作者核验重放；未编译或运行游戏内核',
        'for_owner':[]}
write('独立核验结果.json',result)
print(json.dumps({'status':'PASS','checks':len(checks),'gate_cases':case_count,'gate_item_checks':item_checks,
                  'chain_cases':chain_cases,'review_inputs':len(rows)},ensure_ascii=False))
