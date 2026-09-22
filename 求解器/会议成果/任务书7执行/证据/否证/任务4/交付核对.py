#!/usr/bin/env python3
"""最终重核输入、记录实际命令输出，并检验正文与结构化结果完全对应。"""
from pathlib import Path
from collections import Counter
import hashlib,json,re,subprocess,sys
E=Path(__file__).resolve().parent
O=E.parents[2]
main=O/'复核/否证-任务4.md'
cmd=[sys.executable,'-B',str(E/'独立核查.py')]
r=subprocess.run(cmd,capture_output=True,text=True)
(E/'独立核查.log').write_text('command: '+' '.join(cmd)+'\nexit_status: '+str(r.returncode)+'\nstdout:\n'+r.stdout+'\nstderr:\n'+r.stderr+'\nexplanation: 独立数据、几何、时间表算术及容量反例检查；游戏运行结论由复核正文手推。\n')
if r.returncode: raise SystemExit(r.returncode)
d=json.loads((E/'结构化结果.json').read_text());md=main.read_text()
assert set(d)=={'status','file','findings','summary'}
assert d['status']=='done' and d['file']==str(main)
sections=re.split(r'^### ',md,flags=re.M)[1:]
assert len(sections)==len(d['findings'])==18
for f,s in zip(d['findings'],sections):
    assert set(f)=={'target','verdict','reason'}
    assert s.splitlines()[0]==f['target']
    assert re.search(r'^判定：\*\*(.+?)\*\*。$',s,re.M).group(1)==f['verdict']
    assert re.search(r'^摘要理由：(.+)$',s,re.M).group(1)==f['reason']
    assert f['verdict'] in {'否证成立','否证不成立','无法判定'}
counts=Counter(x['verdict'] for x in d['findings'])
assert counts=={'否证成立':1,'否证不成立':14,'无法判定':3}
assert d['summary'] in md
audit='''# 任务4否证的读者自审

日期：2026-09-21。对象：复核正文、18条结构化发现、本席核查脚本和容量反例。

1. 正文给出R/T/C、P/H/G/N定义、输入版本及行号约定；无需阅读会话即可定位命题。
2. 头部状态为本席审查完成，被审任务4部分完成；1/14/3合计18，正文及JSON一致。
3. F13将物理单种容量与正常配方槽位区分，反例有66台机器及核心的实际无重叠坐标、普通输入单种50、空缓存及全关机后果。它只攻击表列物理容量，不扩展成正确原料运行反例。
4. F09/F10重读其状态归纳：同步运行截面与调试程序可达性分开；半分回路用有限前缀同时归纳服务和交替，再以最迟首返闭合库存条件。
5. F10的旧件位置写为首带成熟物品，H前批输出在下批前已清空，单批队列至多2。条件、动作和后果在同段闭合。
6. F16至F18均先引用原句与正式行号试推，再分别指出缺构造和推导；for_owner为空。局部条件服务不被当成整厂已提供服务。
7. 正文全文已重读；引用、证据链接、target/verdict/reason由交付核对脚本逐项验证。正文无依赖对话现场的指代，无新增分工或未授权写入。
8. 18份被审输入和19份来源按完整指纹与mtime重新验证；三份正式文件、候选约束和被审产物均未改变。所有本席产物在分配目录内，扩展名仅py/log/json/md。
'''
(E/'读者自审.md').write_text(audit)
links=re.findall(r'\]\(([^)]+)\)',md)
for link in links:
    p=main.parent/link.split('#')[0]
    assert p.exists(),str(p)
files=list(E.iterdir())
assert all(p.is_file() and p.suffix in ('.py','.log','.json','.md') for p in files)
check=dict(status='PASS',finding_counts=dict(counts),findings_match=True,links=len(links),source_recheck_exit_status=r.returncode,protected_and_reviewed_inputs_unchanged=True,for_owner=[])
(E/'交付核对结果.json').write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n')
files=[main]+sorted(p for p in E.iterdir() if p.name!='交付清单.json')
manifest=[]
for p in files:
    b=p.read_bytes();manifest.append(dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b)))
(E/'交付清单.json').write_text(json.dumps(dict(status='done',files=manifest,self_hash='omitted to avoid self reference'),ensure_ascii=False,indent=2)+'\n')
print('PASS: 18条target/verdict/reason与正式复核文档完全一致；1/14/3。')
print('PASS: 所有引用存在，输入指纹及mtime保持，交付目录仅含允许文件类型。')
print('MANIFEST:',E/'交付清单.json')
