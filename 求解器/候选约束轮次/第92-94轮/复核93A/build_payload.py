#!/usr/bin/env python3
from pathlib import Path
import json
D=Path(__file__).resolve().parent
candidates=json.loads((D.parent/'推导92A'/'candidates.json').read_text())
reasons={
'分叉分支':'选择范围及成环未定性的处理符合现行规则。',
'传输相位':'40步间隔成立，且未误要求相位任意独立组合。',
'判定先后':'按层序、收货联判和每步一次派生步序正确。',
'取货分级':'逐相容取值比较正确，严格层数差仅作充分办法。',
'密集结点':'双编码复现比例变化；未将局部见证当成全厂反例。',
'来源定序':'补回件数守恒集合的范围，排除制造缓存格。',
'存货误料停机与可用台数':'不可恢复停机及同一后续扣除成立，九项台数双算一致。',
'传输按仓库余量判定':'实际传输前逐次检查min(箱内量,余量)=0成立。',
'混做清空':'当步开工前清空的截止点及通道数下界成立。',
'回路存量':'半开窗与件时记账成立，64、22、42双算一致。',
'传输箱不满':'持续全收下18件保守上界及附条件不堵塞成立。',
'轮询均分':'任意组数归纳闭合，双编码1851008例及子集检查未见反例。',
'混料轮询分料':'实际成功顺序下公式成立，38430个等式复算一致。',
'满速箱头限存':'满速强制每口每8步成功，箱头超量导致矛盾。',
'传输与送货先后':'规则第37行仍保留两种安排，不能补入固定性。'
}
assert len(candidates)==15 and set(reasons)=={c['name'] for c in candidates}
original=next(c['text'] for c in candidates if c['name']=='来源定序')
old='选定一组接货物品格'
assert original.count(old)==1
revised=original.replace(old,'选定一组运输物品格或制造单位的存货物品格（不含缓存格）')
payload={'status':'done','report_path':str(D.parent/'复核93A.md'),'verdicts':[
 {'name':c['name'],'verdict':'修正' if c['name']=='来源定序' else '未否证',
  'reason':reasons[c['name']],'revised_text':revised if c['name']=='来源定序' else ''} for c in candidates]}
(D/'final_payload.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
report=D.parent/'复核93A.md'
s=report.read_text()
s=s.replace('{{SOURCE_REVISION}}',revised)
s=s.replace('因此共核对16个不同名称，但最终', '这两部分合计16个不同名称，最终')
report.write_text(s)
print(json.dumps({'status':'PASS','actual_candidates':len(payload['verdicts']),'verdict_counts':{'未否证':14,'修正':1,'已否证':0}},ensure_ascii=False))
