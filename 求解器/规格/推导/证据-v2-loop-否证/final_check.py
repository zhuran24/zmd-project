from pathlib import Path
from hashlib import sha256
import json
import re

OUT = Path(__file__).resolve().parent
FILE = OUT.parent/'复核/否证-v2-loop.md'
rows = [
('§0','否证不成立','已收回总数充分性；收支式与达标产率结论成立。'),
('§1','否证不成立','条文、行号和 owner 裁定相符；额外起法条件已明示。'),
('§2.1','否证不成立','库存可保留历史，有界不推出遗忘或达标。'),
('§2.2','否证不成立','完成批次收支及恰 32 台达标循环的零入库证明正确。'),
('§2.3','否证不成立','K 的恒等式、漏仓修正及非负解释正确。'),
('§2.4','否证不成立','有限轮次和条件归零成立；未越界宣布一般终点。'),
('§2.5','否证不成立','拒收与解除条件符合容量、种类、滞留和窗口规则。'),
('§2.6','否证不成立','双带合法；均分前件和满输出过渡已分开。'),
('§2.7','否证不成立','达标产率必为 0.6、0.55；128 仅为必要存量。'),
('§3.1','否证不成立','达标类产率唯一，未把失败类或堵满安全性说成已证。'),
('§3.2','否证不成立','局部调试操作合法；整厂恢复安全仍明确待证。'),
('§3.3','否证不成立','2b+48m 是首次清出需求，不能当全程损失上界。'),
('§3.4','否证不成立','容量和差值算术正确，未把必要下限当安全门槛。'),
('§3.5','否证不成立','认证范围正确，未用达标必要结果循环证明达标。'),
('§3.6 数学裁定','否证不成立','最低粉碎或精炼产能排除额外回炼，不能推出逐通道唯一。'),
('§3.6 引用状态','否证成立','现行总纲已限定六类满载机型，该项批评未同步。'),
('§4 U1','无法判定','缺符合收窄范围的完整同总数产率对照或充分性证明。'),
('§4 U2','无法判定','局部条件结论已证，一般多路结构的终点仍未证。'),
('§4 U3','无法判定','缺具体布局恢复程序及全部可能后置状态的安全证明。'),
('§4 U4','无法判定','缺具体释放过程的更强损失界、停止时刻和库存。'),
('§4 U5','无法判定','缺整厂按种类、位置和节奏给出的充分库存条件。'),
('§4 U6','无法判定','失败前移已定，一般调度与全范围相位、离线安全仍未证。'),
('§4 U7','无法判定','没有完整布局使局部条件联合成立的证明。'),
('§4 U8','否证不成立','原缺件记录属实；本报告补齐一次独立复核，未结清 U1—U7。'),
('§5','否证不成立','旧版被否证说法未恢复，保留结论及旧复核范围记录准确。'),
('§6','否证不成立','终修所记主要修改确已落入正文；引用状态另列纠正。'),
('主会话三审 §2.3 两条件充分性','否证成立','正确配比及小偏差仍允许 A=50、B=0、线头 A 的永久互等。'),
('主会话三审 §2.3 满输入补推','否证不成立','加入初始库存差、实际前缀偏差和持续供排条件，可排除入口互等。'),
('主会话三审 §2.3 三支汇流达标','无法判定','尚未证明各支持续有料及成功 2:1；单汇流口最多支持 1/3 批/tick。'),
('主会话三审 §2.3 比例不等必死','否证不成立','限固定无限字序、无旁路且只做同一配方；有限过渡失衡不在此结论内。'),
]
body = FILE.read_text()
overall = body.split('## 5. 总评\n\n',1)[1].strip()
result = dict(file=str(FILE), verdicts=[dict(section=s,verdict=v,reason=r) for s,v,r in rows],overall=overall)
(OUT/'review-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
for r in json.loads((OUT/'inputs.json').read_text()):
    assert sha256(Path(r['path']).read_bytes()).hexdigest()==r['sha256'],r['path']
links=[]
for target in re.findall(r'\]\(([^)]+)\)',body):
    p=(FILE.parent/target).resolve()
    assert p.exists(),p
    links.append(str(p))
assert all(p.suffix in {'.py','.log','.json','.md'} for p in OUT.iterdir())
assert not (OUT.parents[3]/'求解器/求解器').exists()
assert len(rows)==30
assert sum(v=='否证成立' for _,v,_ in rows)==2
audit = {
    'status':'pass','verdict_count':len(rows),'input_hashes_unchanged':True,
    'markdown_links_exist':links,'evidence_extensions_allowed':True,
    'kernel_scope':'build succeeded; 4 seed loads rejected; no executed trajectory',
    'report_sha256':sha256(FILE.read_bytes()).hexdigest(),
    'reader_review':[
        '报告独立定义对象、符号、枚举含义及局部反例范围。',
        '源文状态与数学否证分列；U8 交付状态与 U1-U7 证明状态分列。',
        '头部与总评一致，L=0、U=1113 保留必要条件上界含义。',
        '失败内核输入未称运行证据；独立 FIFO 模型的供料和出货假设写明。',
        '算术、引用位置与全部链接已核。自审修正了 catalog.rs 行号及无外补条件。',
        '没有借 owner 13:40 给主会话两条件背书，也未把无错料误写成有足够配料。',
        '保护文件、受审文件及指定对话指纹未变。']}
(OUT/'final-check.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
(OUT/'读者自审.md').write_text('# 读者视角自审\n\n日期：2026-09-20。状态：通过。\n\n'+'\n'.join('- '+s for s in audit['reader_review'])+'\n\n详细检查结果见 final-check.json；结构化返回值见 review-result.json。\n')
print(json.dumps({'status':'pass','file':str(FILE),'verdict_count':len(rows),'refuted':2,'report_sha256':audit['report_sha256']},ensure_ascii=False))
