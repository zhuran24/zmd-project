#!/usr/bin/env python3
"""汇总有明确范围的搜索记录，不把子问题结论升级为全厂结论。"""
import os
os.sched_setaffinity(0, {6})
import datetime
import hashlib
import json
from pathlib import Path

B = Path(__file__).resolve().parents[1]
specs = [
    ('植物2单元-13x16.json', '两套植物单元置于13×16局部框；不是完整植物带。'),
    ('植物2单元-14x16.json', '两套植物单元置于14×16局部框；不是完整植物带。'),
    ('角区18x18.json', '18×18局部角区，固定出口位置的受限模型。'),
    ('角区18x18-自由出口.json', '18×18局部角区，允许模型中的出口位置变化。'),
    ('全机供电修复-status.json', '半径4的机位与供电修复；不是325路联合布通。'),
    ('全厂端口修复-status.json', '半径6内要求端口净空及供电；必要条件模型，不含完整运输。'),
    ('实线联合正例-status.json', '固定机位下单条已知可行进路回放；只验证局部求解器能恢复正例。'),
    ('完整联合-邻域2.json', '全230台、325路，固定模板机器和桩位，其余锚点邻域半径2；旧版端点索引域。'),
    ('完整联合-索引收紧.json', '同一半径2局部范围，端点索引剔除不可能值。实际代码允许相邻桥；原结果bridge_restriction文字未同步，不能按该文字解读。'),
    ('完整联合-邻域5.json', '锚点邻域半径5，6线程、10GiB地址空间上限。'),
    ('完整联合-邻域5-三核可行性.json', '锚点邻域半径5，3线程、16GiB地址空间上限，仅求可行解。'),
    ('完整联合-放开模板-邻域3.json', '放开模板机器及全部仓库取货口身份，仅固定当前供电桩和H6、Q6、F4；锚点邻域半径3，3线程，仅求可行解。'),
    ('完整联合-放开模板-227提示.json', '同放开模板模型，以227路候选提示；锚点邻域半径3，随机种子2227，3线程，时限540秒。'),
]
rows = []
for name, scope in specs:
    p = B / '实验' / name
    if not p.exists():
        continue
    d = json.loads(p.read_text())
    status = d.get('status')
    if status == 'INFEASIBLE':
        meaning = '仅排除该模型的固定范围与额外限制；不排除整个S2B接法。'
    elif status in ('UNKNOWN', 'MEMORY_LIMIT', 'ABORT_MEMORY_LIMIT', 'ERROR_OR_MEMORY_LIMIT', 'STOPPED_TIME_LIMIT'):
        meaning = '未决；没有得到可行布局，也没有不可行结论。'
    elif status in ('FEASIBLE', 'OPTIMAL'):
        meaning = '仅对该子问题有效；实际整厂资格以布局静态检查为准。'
    else:
        meaning = '此记录尚未给出终止结论。'
    rows.append(dict(file=str(p.relative_to(B)), sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                     status=status, seconds=d.get('wall_seconds', d.get('wall')), scope=scope,
                     conclusion=meaning))
result = dict(updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), runs=rows,
              joint_model_limitations='联合格点模型只生成候选；固定单位依各次范围文件而定，桥接器要求两轴在用。即使得到解，也必须经实际自动通道重建和完整静态检查。',
              scope='这是执行记录索引，正式结果为布局.json及其哈希绑定的静态检查。')
(B / '证据/搜索范围汇总.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps([(r['file'], r['status']) for r in rows], ensure_ascii=False))
