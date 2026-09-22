"""生成独立清单的双向对照与交付核验，只写本席复核目录。"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path('/home/zhuran24/zmd-research-fresh')
SPEC = ROOT / '求解器/规格'
BASE = Path(__file__).resolve().parent

# 每行依次为独立项、对应轴、对照结论；数字仅用于本席索引。
ROWS = '''
01|time.domain|T1明确tick不定义格点，非整数相位未被无据排除。
02|time.retry_schedule time.instant_end|T1一般域开放，本版整轮重复K归约已明选；不能以无库存变化结束。
03|time.retry_schedule time.boundary|T1与运行语义4.3区分端口、同侧、内部通道；H只是达标域条件矛盾。
04|time.instant_end polling.both_failure|尝试和访问分开，失败有指针后效；日志计数不作守卫是显式本版限制。
05|judgment.order_scope judgment.order|global/per_instant分开；v1模板重复嵌入与v2周期函数有语法，后者非本版支持。
06|time.manufacture_events time.instant_order judgment.buffer_event_class|完成非判定、先完成再闭包及制造子动作均明选；不压零耗时。
07|residence.nontransport cascade.buffer|T16/T17分开，正停留域仍待审；未由运输滞留推出全部格一tick。
08|time.boundary|满时长与整数窗口为本版值；运输年龄仍按真实时差核，边界组织有覆盖损失。
09|polling.dual_permission polling.both_failure|both只管成功，A非空即尝试且已授权侧前移；未采用待审no_attempt_hold。
10|polling.eligibility_stage polling.internal_scope|physical不读权限，避免定义环；内部分级未实现则不执行。
11|polling.ungraded_blocked|skip/empty_turn分轴；无分级探针的偏流未证明正式均分前件，不升级发现。
12|polling.initial_cursor polling.split_merge_start polling.split_merge_scope polling.split_merge_singleton|起点、计数域、启动条件、单成员级已拆；本版per_level不再写入错误级成员。
13|polling.memory_scope polling.resume|每级续接与当前级分开；回级保留，未新增始终最高前件。
14|polling.level_tie|本版用显式独立级序，不以通道序或id暗补平局。
15|connection.order connection.tie offline.order_domain|初建由较晚端导出，离线两两可变不冒称全部排列可达。
16|offline.cursor_effect offline.inventory_effect offline.progress_effect offline.direction_effect offline.gate_total_effect offline.gate_window_effect offline.gate_window_start_effect|各派生量分别登记，未授权清零；本版离线事件停止。
17|connection.port_meeting polling.direct_peer|相遇排除有发现1；PC另一端为直接接与相遇谓词不同，不重开隔带直接接。
18|damping.belt_component_rule damping.belt_adjacency|路径串/几何块分开，角触连续仍待审，未默认进入允许域。
19|damping.no_terminal|无终点不默填0；准入断边须重核，明确unresolved停止。
20|damping.branch|按(channel,fork)表和固定性编码；运行中变化未覆盖，单次选择不证明时间序列有限。
21|connection.bridge_first_contact connection.bridge_tie offline.direction_effect|已知唯一非桥见证可解；并列与递归依赖明确停止，不以联立有解证明历史可达。
22|connection.belt_shape initialization.belt_shape_lifecycle initialization.rotation_stage|三轨道与四朝向独立；直接改形无授权不执行；重建库存后效未被补造。
23|initialization.rotation_stage connection.port_meeting|不重叠依主席最严义务，坐标四向为本版输入；相遇谓词另见发现1。
24|power.cell_rule|positive_area与closed_touch保留；必要供电义务按最严，额外供电行为损失未省略。
25|connection.build_order initialization.build_timing|带最后且有建成标签，非带期间运行未被默认禁止。
26|manufacturing.input_mixing manufacturing.input_capacity_scope manufacturing.port_slot_relation|甲乙、合计/逐种分开；端口分配为主席已定，不以混装自动授权逐种容量。
27|manufacturing.recipe_match_scope|逐格/并集登记；J只证达标条件矛盾，未据有解假设删物理读法。
28|manufacturing.recipe_completeness manufacturing.recipe_quantity_match manufacturing.recipe_extra_items|三项已分开；exact/forbid只是待审，未被未定直接授权。
29|manufacturing.input_collection manufacturing.recipe_lock_time judgment.buffer_event_class|本版整批制造子动作明选，部分归集缺合法后效不执行。
30|manufacturing.recipe_selection manufacturing.recipe_lock_time|配方非玩家设定；甲下至多一条的物种证明不保证一定可开闸。
31|manufacturing.input_slot_selection manufacturing.empty_slot_identity|已有同种只进原格；新种按显式序；空身份与库存不混。
32|manufacturing.output_blocked|第6轮已补出缓存及收货跨普通格同种检查；缓存例外保留。
33|manufacturing.input_collection manufacturing.output_blocked|受限缓存种子一批是支持条件，非容量改写；其它缓存状态停止，守恒含在制。
34|manufacturing.buffer_power_gate|本版只有制造需电、内部搬运独立；停用功能保进度。
35|time.domain time.boundary manufacturing.buffer_power_gate|剩余时长/暂停边界进入State；本版整数限制与一般实数有限化区分。
36|warehouse.capacity warehouse.empty_slot_identity|单种80000已定；历史身份/新格关系另轴；连续单物种消费仲裁表有发现2。
37|warehouse.empty_slot_identity|空指派必须empty_identity已解，按主席要求沿用轴；身份不生成货物。
38|warehouse.empty_slot_identity transfer.partial_acceptance|多新物种争空格已精确停止且零提交；不重复报告旧发现；普通落格更新见发现2。
39||箱体按R72编号定收发；空后保留历史禁入身份未单列，本席尚未证明该候选通过C80等联合审查，不把仓库身份轴外推或据此新增finding。
40|transfer.judgment transfer.partial_acceptance transfer.failure_cooldown|单位判定已定，整箱成败及每次尝试冷却为明选；其它方向待审。
41|transfer.cooldown_scope transfer.phase|按箱/格冷却与相位另列；0到5残余只属整数试验域，不声称一般相位穷尽。
42|transfer.pause transfer.resume_event|暂停与恢复日程分开；制造进度保留不直接证明冷却计时唯一。
43|gate.identity_subject gate.identity_recovery|当前候选与可能集合分开，身份锁存明选；现PC批维护为显式阶段。
44|gate.counter_start gate.window_clock time.boundary|首件起窗与全局切片区分，累计与窗口分计；满5后下件重起。
45|gate.window_recovery gate.identity_recovery gate.total_recovery gate.window_clock|窗口用尽永闭和全阻断停表未回流；身份专属暂停仍待审。
46|gate.reconnect_record polling.membership_change|当前图重算、保原建造记录及存活指针映射明选；不借恢复伪造新建造。
47|gate.concurrent_expiry time.instant_order|第6轮atomic_batch消除了逐边维护顺序；ordered_recovery须额外序。
48|gate.counter_edit gate.counter_start gate.cancel_limit|改值、起算、取消分开；停机不等于重置；本版操作停止。
49|gate.limit_requires_identity gate.cancel_limit|身份后设两限且正整数范围明确；未设不当零，取消另审。
50|initialization.debug_actions initialization.rebuild_inventory initialization.rotation_stage gate.counter_edit|动作授权与库存/连接后效分开；零干预不借设定权限自动操作。
51|initialization.other_inventory initialization.switches initialization.warehouse_anchor polling.initial_cursor transfer.phase|仓库初始锚点、非仓库内容及相位有入口；完整种子不等于已证可达。
52|initialization.debug_actions initialization.rebuild_inventory initialization.build_timing|有限不精确操作族可表示；任意内部状态写入没有被升级为玩家动作。
53|initialization.debug_end|调试后置域与一个具体快照分开，种子起动义务未省略。
54|offline.events offline.progress_effect offline.order_domain|离线次数时刻、时间推进、排序域登记；本版发生即停。
55|warehouse.external_supply warehouse.capacity|两矿补给保持容量与持续充分；本版有限段历史不足不代表一般供给已证。
56|warehouse.acceptance warehouse.acceptance_quantifier warehouse.withdrawal_policy warehouse.withdrawal_timing warehouse.delivery_count|接收谓词、量词、策略、时刻与交付计数分开；非成品无外部拿取授权。
57|warehouse.periodic_lift offline.events|完整循环提升是证明义务，非任选true；冻结段不能替代离线接续覆盖。
58|warehouse.delivery_count warehouse.periodic_lift|Q2平均及C36周期倍数已入正文，未增每滚动30tick半件条件。
59|time.instant_end warehouse.periodic_lift|无周期空真不充当完整目标证书，缓存有限化与本版闭包终止分开。
60|judgment.order_scope damping.branch transfer.phase offline.order_domain|生命周期与组合关联被明确保留；99轴不宣称任意笛卡儿积合法。
61||运行语义1/内核输入2给目标几何接口，最优同分代表无需冒造行为轴。
62|initialization.other_inventory|四件前置义务3明确完整物种域需证，有限字母表只是受限模型。
'''


def main():
    config = json.loads((SPEC / '内核配置-v1.json').read_text())
    lines = (SPEC / '选择点参数轴.md').read_text().splitlines()
    axis_lines = {match.group(1): index for index, line in enumerate(lines, 1)
                  if (match := re.match(r'^\| `([a-z_]+\.[a-z_]+)` \|', line))}
    rows = []
    reverse = {key: [] for key in config['axes']}
    for line in ROWS.strip().splitlines():
        number, fields, conclusion = line.split('|', 2)
        independent_id = 'I' + number
        axes = fields.split()
        assert set(axes) <= reverse.keys()
        for axis in axes:
            reverse[axis].append(independent_id)
        rows.append({'independent_id': independent_id, 'axes': axes,
                     'conclusion': conclusion})
    # 桥两轴的库存与调度规则是独立清单多个条目的共同固定背景。
    for axis, ids in {'bridge.inventory_scope': ['I18', 'I21', 'I32'],
                      'bridge.scheduling_scope': ['I09', 'I13', 'I21'],
                      'bridge.capacity': ['I08', 'I21', 'I59']}.items():
        reverse[axis] = ids
        for row in rows:
            if row['independent_id'] in ids:
                row['axes'].append(axis)
    assert len(rows) == 62 and len(reverse) == 99
    assert all(reverse.values()), [key for key, value in reverse.items() if not value]
    assert set(reverse) == set(axis_lines)
    data = {'independent_count': len(rows), 'axis_count': len(reverse),
            'forward': rows, 'reverse': reverse, 'axis_lines': axis_lines}
    (BASE / '逐项对照.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    body = ['# 第7轮独立清单与99轴逐项对照', '',
            '日期：2026-09-19。状态：对照完成。独立基线形成后才生成本表；对应不代表取值合法性证明。', '',
            '独立项的正式原文依据和被排除边界见[独立清单](../选择点独立清单-r7.md)；两项发现的完整论证见[复核报告](../复核-r7-独立选择点.md)。', '',
            '| 独立项 | 参数轴落点（行号指被审选择点参数轴.md） | 对照结论 |',
            '|---|---|---|']
    for row in rows:
        fields = '；'.join(f'`{axis}` L{axis_lines[axis]}' for axis in row['axes']) or '无直接轴映射，见本行审查结论'
        body.append(f"| {row['independent_id']} | {fields} | {row['conclusion']} |")
    body += ['', '## 反向检查', '',
             '本表映射覆盖99个现行轴，无未对应字段。下面逐轴列独立项及配置处置；未定方向不能凭处置名称获得规则许可。', '',
             '| 参数轴 | 独立项 | 本版处置 | 复核状态 |', '|---|---|---|---|']
    for axis in axis_lines:
        status = '见S3-r7-L3-1' if axis == 'connection.port_meeting' else '见S3-r7-L3-2的完整后继问题' if axis == 'warehouse.empty_slot_identity' else '未发现新的登记或排除缺陷；一般联合审查未完成'
        body.append(f"| `{axis}` | {', '.join(reverse[axis])} | {config['axes'][axis]['disposition']} | {status} |")
    (BASE / '逐项对照.md').write_text('\n'.join(body) + '\n')
    captured = json.loads((BASE / '开工指纹.json').read_text())
    changed = [row['path'] for row in captured
               if not (ROOT / row['path']).exists()
               or hashlib.sha256((ROOT / row['path']).read_bytes()).hexdigest() != row['sha256']]
    baseline_results = {}
    for name in ['规格自查', '原转移回归', '修订回归', '样例兼容']:
        report = json.loads((BASE / (name + '.json')).read_text())
        baseline_results[name] = {'status': report['status'],
                                  'check_count': len(report.get('checks', []))}
    review = SPEC / '复核/复核-r7-独立选择点.md'
    independent = SPEC / '复核/选择点独立清单-r7.md'
    missing = []
    for path in [review, independent, BASE / '逐项对照.md']:
        for link in re.findall(r'\]\(([^)]+)\)', path.read_text()):
            if not (path.parent / link.split('#')[0]).exists():
                missing.append([str(path), link])
    # 本核验文件在写入前可被主报告引用。
    missing = [row for row in missing if not row[1].endswith('交付核验.json')]
    audit = {'status': 'PASS' if not changed and not missing else 'FAIL',
             'captured_file_count': len(captured), 'changed_captured_files': changed,
             'independent_count': 62, 'axis_count': 99,
             'unmapped_axes': [], 'missing_links': missing,
             'baseline_readonly_reruns': baseline_results,
             'reader_review': '主报告与独立基线逐段重读；两项发现与条件探针分开，路径行号及数字口径核对。',
             'scope': '只写本席复核目录；未运行改写黄金记录的run_checks.py；未commit或push。'}
    (BASE / '交付核验.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == '__main__':
    main()
