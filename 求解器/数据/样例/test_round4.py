#!/usr/bin/env python3
"""第四轮几何边界、轮询轨迹和压缩记录的回归入口。"""
import copy
import json
from pathlib import Path
import check_examples as checker
from checkpoint_delta import encode_trace, decode_trace, apply_delta
from check_golden_trace import run
from check_port_meeting import compare_meeting
from runtime_record import validate_record, same
from runtime_example import make_poll_memory

BASE = Path(__file__).resolve().parent
OUT = BASE.parents[1] / '规格/第四轮前置验证'


def main():
    checks = []

    def passed(condition, name):
        checker.require(condition, name)
        checks.append({'name': name, 'status':'通过'})

    def reject(name, operation):
        try:
            operation()
        except checker.CheckError as error:
            checks.append({'name': name, 'status':'正确拒绝', 'reason':str(error)})
        else:
            raise checker.CheckError('未拒绝: ' + name)

    catalog = checker.load_json(BASE.parent / '正式静态目录.json')
    comparisons = {}
    for name in checker.NAMES:
        data = checker.load_json(BASE / name)
        checker.check(data, BASE / name)
        comparison = compare_meeting(data, catalog)
        comparisons[name] = comparison
        passed(bool(set(comparison['closed_touch_with_opposite_normals']) - set(comparison['shared_edge_opposite'])),
               name + '：即使附加法向相反仍存在端点差异，禁止假报集合相同')

    split = checker.load_json(BASE / '分流器三路轮询.json')
    ticks = run(split)
    passed(same(ticks, run(copy.deepcopy(split))), '分流器重复运行逐字段确定')
    for index, tick in enumerate(ticks):
        summary = tick['summary']
        passed(summary['warehouse_ore'] == str(80000-([3,6][index] if index<2 else 2*index+4)) and summary['delivered_to_boxes'] == {
            'north_box':str(max(0,index-1)), 'east_box':'0', 'west_box':'0'}, '分流器t='+str(index)+'与手工递推收支一致')
        contents = [row for slot in tick['state']['inventory'] for row in slot['contents']]
        passed(all(row['item']=='源矿' for row in contents) and
               sum(checker.quantity(row['quantity']) for row in contents)==80000-int(summary['warehouse_ore']), '分流器t='+str(index)+'仓库扣料与全部格守恒')
    sides = split['initial_state']['nonwarehouse']['value']['logistics']['poll_memory']['value']['sides']
    main_ring = next(s['levels'][0] for s in sides if s['unit']=='splitter' and s['side']=='output')
    sole_ring = next(s['levels'][0] for s in sides if s['unit']=='feed_splitter' and s['side']=='output')
    passed(main_ring['next_channel']==main_ring['members'][1], '三成员环初态second_cursor')
    passed(len(sole_ring['members'])==1 and sole_ring['next_channel']==sole_ring['members'][0], '单成员环初态sole_member')
    first = {e['event']:e for e in ticks[0]['events']}
    passed(first['J|0|0|3']['outcome']=='no_request' and first['J|0|0|4']['outcome']=='failure'
           and first['J|0|0|5']['outcome']=='failure', '首刻按第二条起轮，真实失败前移到第三条；不把起点冒充首件出口')
    expiry=[e for e in ticks[6]['events'] if e['operation']=='gate_window_expiry']
    passed(len(expiry)==2 and {e['target'] for e in expiry}=={'probe_gate_a','probe_gate_b'} and all(e['detail']=='atomic_batch:probe_gate_a,probe_gate_b' for e in expiry), 't=6两门从同一快照批到期')
    passed(all(e['operation']=='gate_window_expiry' for e in ticks[6]['events'][:2]), '批到期完整先于同刻判定')
    passed(all(g['window_started_at'] is None and g['window_received']['value']=='0' and not g['blocked_reasons'] for g in ticks[6]['state']['logistics']['gate_counters']), '满五tick清窗口原因、保留累计和库存')
    passed(all(g['total_received']['value']=='1' for g in ticks[6]['state']['logistics']['gate_counters']), '窗口到期不清累计')
    altered=copy.deepcopy(split)
    arbitration=altered['initial_state']['nonwarehouse']['value']['semantic_context']['arbitration']['level_order']
    indices=[i for i,lid in enumerate(arbitration) if lid.startswith('L|probe_merger|input|')]
    passed(len(indices)==2, '汇流器两个直接单成员级')
    i,j=indices;arbitration[i],arbitration[j]=arbitration[j],arbitration[i]
    reversed_ticks=run(altered)
    def winner(trace):
        return next(e['target'].split('|')[1].split(':')[0] for e in trace[2]['events'] if e['operation']=='move' and e['outcome']=='success' and '|probe_merger:' in e['target'])
    passed(winner(ticks)!=winner(reversed_ticks), '只交换独立级仲裁序即可交换首个汇流胜者，确实执行level_tie')
    altered = copy.deepcopy(split)
    ring = next(s['levels'][0] for s in altered['initial_state']['nonwarehouse']['value']['logistics']['poll_memory']['value']['sides'] if s['unit']=='splitter' and s['side']=='output')
    ring['next_channel']=ring['members'][0]
    reject('拒绝伪造第一条起轮种子', lambda:checker.check(altered, BASE/'分流器三路轮询.json'))
    altered = copy.deepcopy(split)
    altered['settings']['switches'][0]['enabled']=True
    reject('开启未实现无线传输须拒绝', lambda:run(altered))

    altered=copy.deepcopy(split)
    altered['settings']['gates'][0]['window_limit']['value']='2'
    reject('未支持门额度不能静默沿用本例后效', lambda:run(altered))
    altered=copy.deepcopy(split)
    slot=next(r['slot'] for r in altered['initial_state']['warehouse']['slots'] if r['item']=='蓝铁矿')
    next(a for a in altered['settings']['warehouse_assignments'] if a['port'].startswith('probe_left_source:'))['slot']=slot
    reject('未实现身份不符维护的来源须明确拒收', lambda:run(altered))
    altered=copy.deepcopy(split)
    altered['timeline']['events'][0]['id']='W|6|probe_gate_a'
    reject('窗口事件不能与非runtime历史别名', lambda:checker.validate_timeline(altered['timeline']))

    records = {}
    for name in ('混做粉碎机两下游', '分流器三路轮询'):
        data = checker.load_json(BASE/(name+'.json'))
        output = checker.load_json(BASE/(name+'-运行记录.json'))
        validate_record(output,data)
        for interval in (1,2,4,5):
            compact = copy.deepcopy(output)
            compact['trace']=encode_trace(output['trace'],interval)
            passed(same(decode_trace(compact['trace']),output['trace']), name+'：k='+str(interval)+'含末尾残段的无损往返')
            validate_record(compact,data)
        compact = copy.deepcopy(output)
        compact['trace']=encode_trace(output['trace'],2)
        path=BASE/(name+'-运行记录-checkpoint_delta.json')
        # 分流器产物约定k=4，另用k=2作以下破坏性内存检查。
        if name=='混做粉碎机两下游':
            path.write_text(json.dumps(compact,ensure_ascii=False,indent=2)+'\n')
        if name=='分流器三路轮询':
            coverage={row['axis']:row for row in output['uncovered_axes']}
            required=('polling.split_merge_start','polling.split_merge_scope','polling.split_merge_singleton','polling.level_tie','gate.concurrent_expiry')
            event_ids={e['event'] for tick in output['trace']['ticks'] for e in tick['events']}
            passed(all(coverage[axis]['coverage_status']=='exercised' and any(e in event_ids for e in coverage[axis]['evidence']) for axis in required), '五条指定轴全部有真实运行事件证据')
        records[name]={'ticks':len(output['trace']['ticks']), 'last_summary':output['trace']['ticks'][-1]['summary'],
                       'coverage':{r['axis']:r['coverage_status'] for r in output['uncovered_axes'] if r['axis'].startswith('polling.split_merge') or r['axis'] in ('polling.level_tie','gate.concurrent_expiry')}}

        mutations = [
            ('非法零间隔',lambda o:o['trace'].update(checkpoint_interval=0)),
            ('bool不能充当间隔',lambda o:o['trace'].update(checkpoint_interval=True)),
            ('遗漏增量',lambda o:o['trace']['ticks'][1].pop('delta')),
            ('检查点漂移',lambda o:o['trace']['ticks'][2]['state']['warehouse']['slots'][0]['quantity'].update(value='123')),
            ('增量改时间',lambda o:o['trace']['ticks'][1].update(delta=[])),
            ('重复增量路径',lambda o:o['trace']['ticks'][1]['delta'].append(copy.deepcopy(o['trace']['ticks'][1]['delta'][0]))),
            ('不存在的路径',lambda o:o['trace']['ticks'][1]['delta'][0].update(path=['missing'])),
            ('跨段省略事件',lambda o:o['trace']['ticks'][-1]['events'].pop()),
            ('未知增量操作',lambda o:o['trace']['ticks'][1]['delta'][0].update(op='remove')),
            ('增量与全状态并存',lambda o:o['trace']['ticks'][1].update(state=copy.deepcopy(output['trace']['ticks'][1]['state']))),
        ]
        for label, mutate in mutations:
            broken=copy.deepcopy(compact);mutate(broken)
            reject(name+'：'+label,lambda broken=broken:validate_record(broken,data))

    # 压缩器须保持JSON类型，且不能用布尔/数字相等掩盖变化。
    before={'a':1,'b':{'c':[1,2]}}
    after={'a':True,'b':{'c':[2]}}
    from checkpoint_delta import state_delta
    passed(same(apply_delta(before,state_delta(before,after)),after), '增量严格保留JSON类型及数组整体替换')
    reject('祖先后代路径冲突',lambda:apply_delta(before,[{'op':'replace','path':['b'],'value':{}},{'op':'replace','path':['b','c'],'value':[]}]))
    reject('数组索引不属于对象路径',lambda:apply_delta(before,[{'op':'replace','path':['b','c','0'],'value':9}]))
    report={'status':'通过','tests':checks,'test_count':len(checks),'port_meeting':comparisons,'runs':records,
            'scope':'有限参考轨迹和编码验收；集合相同未成立；所列轮询与门控分支有有限执行证据，不是全称认证'}
    (OUT/'回归结果.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'通过','tests':len(checks),'report':str(OUT/'回归结果.json')},ensure_ascii=False))


if __name__=='__main__':
    main()
