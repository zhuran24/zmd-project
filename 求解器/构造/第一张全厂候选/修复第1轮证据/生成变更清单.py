#!/usr/bin/env python3
"""以本轮起始哈希为基准列出所有新增/修改文件；拒绝未授权的原文件变动。"""
from pathlib import Path
import json, hashlib
HERE=Path(__file__).resolve().parent
BASE=HERE.parent
A=BASE/'检查器A'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
initial=json.loads((HERE/'起始哈希.json').read_text())
allowed={str(BASE/'生成/候选.json'),str(BASE/'生成/报告.md')}
protected=[Path(p) for p in initial if not Path(p).is_relative_to(A) and p not in allowed]
assert all(p.exists() and sha(p)==initial[str(p)] for p in protected)
files=[p for p in A.rglob('*') if p.is_file() and p.name!='artifact_manifest.json']
(A/'artifact_manifest.json').write_text(json.dumps({'directory':str(A),'self_path':str(A/'artifact_manifest.json'),'files':[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(files)],'file_count_including_manifest':len(files)+1,'write_scope':str(BASE)},ensure_ascii=False,indent=2)+'\n')
specific={
 '生成/候选.json':'重摆219台和核心、重新指派供矿与布线、补供电；135路径/48接通矿口，规范化16项登记；仍拒绝。',
 '生成/报告.md':'当前候选状态、逐项修订依据、新旧数值对照、全部复验、搜索覆盖与未完成项。',
 '检查器A/catalog.py':'D1：支持当前72条正式约束指纹。',
 '检查器A/projections.py':'D1：新增1113位置投影，迁移旧64–71编号及植物回路投影。',
 '检查器A/design.py':'D2/D3：实际配方子集登记、未知登记未决；仅显式保持声明触发候选B逐项核对。',
 '检查器A/geometry.py':'单端桥真实边重建；分开P2_structure与完整P2。',
 '检查器A/check_full.py':'D1/D7：当前编号依赖、P2精确等速阶段、blocked状态及失败分类。',
 '检查器A/selftest.py':'将原61项自测迁移到当前指纹、72条编号及分阶段P2断言。',
 '检查器A/gate1_regression.py':'7组闸门针对性回归：版本、1113位置、登记、B来源、单端桥、原候选不回归。',
 '检查器A/说明.md':'当前规则版本、72条覆盖表与本轮逐项修复/验证记录。',
 '修复第1轮证据/起始哈希.json':'本轮操作前原文件的SHA-256基线。',
 '修复第1轮证据/候选-修复前.json':'第1轮原候选的字节备份。',
 '修复第1轮证据/报告-修复前.md':'原生成报告的字节备份。',
 '修复第1轮证据/候选登记修正.json':'仅规范化登记时的字段差分与前后哈希，不冒充布线修复。',
 '修复第1轮证据/供矿摆放试验.py':'整条端口边预留与48口直供的受限摆放搜索；300.2秒UNKNOWN。',
 '修复第1轮证据/逐机端口摆放试验.py':'按B逐机端口数量分组预留；168.5秒取得本轮使用的满足性摆放。',
 '修复第1轮证据/完整供矿摆放试验.py':'另加52源单位容量首加工矿流必要筛子；600.9秒UNKNOWN。',
 '修复第1轮证据/修复指派布线.py':'本轮独立副本：摆放中的机器/矿源指派及60轮A*拆线重布。',
 '修复第1轮证据/修复导出候选.py':'导出完整路径及实体通道，重算空矩形、补供电并保留规范登记。',
 '修复第1轮证据/候选-新摆放.json':'两份检查器预验的新摆放文件，与最终生成/候选.json字节相同。',
 '修复第1轮证据/布线输入摆放.json':'将端口分组摆放按尺寸转换为布线器的输入结构。',
 '修复第1轮证据/成品路径可达诊断.json':'当前六台末级机器到核心的无向空格道路放宽可达性；仅M218可达。',
 '修复第1轮证据/独立LP.py':'原闸门独立LP脚本的字节副本；重建当前候选并重跑全部诊断。',
 '修复第1轮证据/独立证书回放.py':'不调用求解器，核五条空行矛盾及780列零流最优性证书。',
 '修复第1轮证据/复验.py':'顺序调用A、B和A证书回放，逐端口对照独立LP及候选声明。',
 '修复第1轮证据/完整性检查.json':'164个受保护原文件未变、B32文件和旧闸门54证据未变；最终候选/实现哈希一致。',
 '修复第1轮证据/生成变更清单.py':'重新生成A工件哈希与本轮完整文件变更清单；只允许既定原文件变化。',
}
def purpose(p):
    rel=p.relative_to(BASE).as_posix()
    if rel in specific:return specific[rel]
    if p.name=='文件变更清单.md':return '所有新增/修改文件的绝对路径、变化类型及用途。'
    if p.name=='文件变更清单.json':return '机器可读变更清单，含逐文件SHA-256；自身不自引用哈希。'
    if p.name.startswith('独立LP-诊断见证-'):return '对应物品的供矿放宽、去目标诊断与精确原始/对偶见证。'
    if p.name=='独立LP矩阵.json':return '当前候选的独立严格LP完整780变量、18629行矩阵。'
    if p.name=='artifact_manifest.json':return '检查器A当前全部工件的绝对路径、大小与SHA-256。'
    if p.suffix=='.log':return '同名脚本或检查命令的本轮原始标准输出/错误日志。'
    if p.suffix=='.json':return '同名检查、回归、摆放、布线、导出或证书的本轮机器可读结果。'
    return '本轮修复与复验工件，具体输入及结果见生成报告。'
md=HERE/'文件变更清单.md';js=HERE/'文件变更清单.json'
changed=[p for p in BASE.rglob('*') if p.is_file() and p not in (md,js) and (str(p) not in initial or sha(p)!=initial[str(p)])]
changed=sorted(changed+[md,js])
entries=[]
for p in changed:
    entries.append({'path':str(p),'change':'modified' if str(p) in initial else 'added','description':purpose(p),
                    'sha256':None if p in (md,js) else sha(p),
                    'before_sha256':initial.get(str(p))})
text='# 第1轮修复文件变更清单\n\n日期：2026-09-22。状态：修复记录已汇总；候选仍被拒绝，任务未完全达成。\n\n'
text+=f'共 {len(entries)} 个新增或修改文件。完整哈希见同目录文件变更清单.json；本清单列出所有文件的绝对路径。\n\n'
text+='| 变化 | 绝对路径 | 修改或新增内容 |\n|---|---|---|\n'
for row in entries:text+=f"| {'修改' if row['change']=='modified' else '新增'} | [{row['path']}]({row['path']}) | {row['description']} |\n"
md.write_text(text)
for row in entries:
    if row['path']==str(md):row['sha256']=sha(md)
js.write_text(json.dumps({'candidate_sha256':sha(BASE/'生成/候选.json'),'task_complete':False,'pass':False,'files':entries,'file_count':len(entries),'self_hash_excluded':str(js)},ensure_ascii=False,indent=2)+'\n')
actual={str(p) for p in BASE.rglob('*') if p.is_file() and (str(p) not in initial or sha(p)!=initial[str(p)])}
assert actual=={x['path'] for x in entries}
assert all(Path(x['path']).is_relative_to(BASE) for x in entries)
assert all(sha(Path(x['path']))==x['sha256'] for x in entries if x['sha256'])
print(json.dumps({'total':len(entries),'modified':sum(x['change']=='modified' for x in entries),'added':sum(x['change']=='added' for x in entries),'protected_unchanged':len(protected),'list':str(md)},ensure_ascii=False))
