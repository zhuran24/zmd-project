"""独立复算几何，并给出非周期排序覆盖反例的有限检验。"""
import copy
import json
import os
import sys
from fractions import Fraction
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[4]
EXAMPLES = ROOT / '求解器/数据/样例'
sys.path.insert(0, str(EXAMPLES))
import check_examples as checker
from event_order import order_at
from runtime_example import quantity, time_value


def write_json(name, value):
    (BASE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def rotate(x, y, width, height, code):
    return {'r0': (x, y), 'r90': (height-1-y, x),
            'r180': (width-1-x, height-1-y), 'r270': (y, width-1-x)}[code]


def rotate_normal(x, y, code):
    return {'r0': (x, y), 'r90': (-y, x), 'r180': (-x, -y), 'r270': (y, -x)}[code]


def geometry(data, catalog):
    # 与被审 geometry 函数独立；仅共用目录数据。
    kinds = {k['id']: k for k in catalog['units']}
    occupied = set()
    ports = {}
    for unit in data['layout']['units']:
        uid = unit['id']; kind = kinds[unit['kind']]
        width = int(kind['dimensions']['width']['value'])
        height = int(kind['dimensions']['height']['value'])
        ox, oy = (int(q['value']) for q in unit['origin'])
        rotation = unit['rotation']
        cells = {(ox+rotate(x,y,width,height,rotation)[0], oy+rotate(x,y,width,height,rotation)[1])
                 for x in range(width) for y in range(height)}
        assert not occupied & cells
        assert all(0 <= x < 70 and 0 <= y < 70 for x,y in cells)
        occupied |= cells
        if unit['kind'] == '桥接器':
            edges = {edge['side']: edge for variant in kind['ports']['layouts'] for edge in variant}
            edges = copy.deepcopy(list(edges.values()))
            for edge in edges:
                state = unit['bridge_axes'][edge['axis']]
                assert state['status'] == 'resolved'
                edge['role'] = 'input' if edge['side'] == state['input_side'] else 'output'
        else:
            edges = kind['ports']['layouts'][unit['port_layout']]
        for edge in edges:
            for position in edge['positions']:
                p = int(position['value']); side = edge['side']
                x,y = {'south':(p,0),'north':(p,height-1),'west':(0,p),'east':(width-1,p)}[side]
                x,y = rotate(x,y,width,height,rotation)
                nx,ny = rotate_normal(*{'south':(0,-1),'north':(0,1),'west':(-1,0),'east':(1,0)}[side],rotation)
                ports[f'{uid}:{side}:{p}'] = {'cell':(x+ox,y+oy),'normal':(nx,ny),'role':edge['role'],'family':kind['family']}
    channels = set()
    for aid,a in ports.items():
        for bid,b in ports.items():
            if a['role'] != 'output' or b['role'] != 'input': continue
            if 'transport' not in (a['family'],b['family']): continue
            if b['cell'] == tuple(x+y for x,y in zip(a['cell'],a['normal'])) and b['normal'] == tuple(-x for x in a['normal']):
                channels.add(f'PC|{aid}|{bid}')
    assert channels == {c['id'] for c in data['layout']['physical_channels']}
    return {'units':len(data['layout']['units']),'occupied':len(occupied),'ports':len(ports),'channels':len(channels),'declared_pc_equal':True}


FIRST = [{'operation':'transfer','target':'box_a'},{'operation':'transfer','target':'box_b'}]


def witness_order(index):
    # 只在正的二次幂次到期取反序；函数在输入前固定。
    power = index > 0 and index & (index-1) == 0
    return list(reversed(FIRST)) if power else FIRST


def main():
    catalog = checker.load_json(EXAMPLES.parent / '正式静态目录.json')
    geometries = {name:geometry(checker.load_json(EXAMPLES/name),catalog) for name in checker.NAMES}
    data = checker.load_json(EXAMPLES / '桥接器双通路.json')
    def unit(uid,kind,x,y):
        return {'id':uid,'kind':kind,'origin':[quantity(x),quantity(y)],'rotation':'r0',
                'port_layout':0,'bridge_axes':None,'occupied_cells':None}
    units = [unit('core','协议核心',50,50),unit('box_a','协议储存箱',10,10),
             unit('box_b','协议储存箱',14,10),unit('power','供电桩',10,14)]
    data['layout'].update(units=units,physical_channels=[],buffer_channels=[])
    events = [{'id':f'build_{i}','kind':'build','time':{'kind':'symbol','value':f't{i}'}} for i in range(4)]
    events += [{'id':e,'kind':e,'time':{'kind':'symbol','value':'t_'+e}} for e in ('blueprint_complete','debug_end')]
    relation = lambda a,b,r:{'before':a,'after':b,'relation':r,'basis':['规则蓝图；候选实际历史']}
    data['timeline'] = {'events':events,'relations':[relation(f'build_{i}',f'build_{i+1}','strict') for i in range(3)] +
                       [relation('build_3','blueprint_complete','occurs_before'),relation('blueprint_complete','debug_end','occurs_before')],
                       'connection_events':[]}
    data['construction'].update(selected_order=[u['id'] for u in units],
        moments=[{'event':f'build_{i}','unit':u['id'],'placement':{k:u[k] for k in ('kind','origin','rotation','port_layout','occupied_cells')}} for i,u in enumerate(units)])
    data['settings']['switches'] = [{'unit':uid,'function':'transfer','enabled':True} for uid in ('box_a','box_b')]
    data['scenario'] = {'name':'二次幂次到期反序的双空箱几何','recipe_intents':[],'expected_paths':[],'assertions':[]}
    data['catalog']['path'] = os.path.relpath(EXAMPLES.parent/'正式静态目录.json', BASE)
    data['parameters']['axis_registry']['path'] = os.path.relpath(checker.AXIS_PATH, BASE)
    structural = checker.check(data, BASE/'双空箱几何.json')
    geometries['双空箱几何.json'] = geometry(data,catalog)
    # 桩中心(11,15)，正面积覆盖(5,17)×(9,21)，两箱均有正面积交集。
    assert all(max(x,5)<min(x+3,17) and max(y,9)<min(y+3,21) for x,y in ((10,10),(14,10)))
    write_json('双空箱几何.json',data)
    finite = {'schema':'event-order-v2','scope':'per_instant','template_order':FIRST,
              'repeat_embedding':'scan_round_then_template','schedule':{'kind':'finite_table',
                'entries':[{'instant':time_value(5*n),'template_order':witness_order(n)} for n in range(65)]}}
    assert all(order_at(finite,time_value(5*n))==witness_order(n) for n in range(65))
    try:order_at(finite,time_value(325))
    except checker.CheckError as error: exhaustion = str(error)
    else:raise AssertionError('有限表应在未列时刻停止')
    periodic_checks=[]
    for width, origin, orders in [('5','0',[FIRST,list(reversed(FIRST))]),
                                 ('7/3','-11/13',[FIRST,FIRST,list(reversed(FIRST))]),
                                 ('13/17','2/19',[list(reversed(FIRST)),FIRST])]:
        value = {'schema':'event-order-v2','scope':'per_instant','template_order':FIRST,
                 'repeat_embedding':'scan_round_then_template','schedule':{'kind':'periodic',
                 'origin':time_value(origin),'slot_width':time_value(width),'orders':orders}}
        period = Fraction(width).numerator*len(orders)
        index = 1 << period.bit_length()
        actual_a = order_at(value,time_value(5*index))
        actual_b = order_at(value,time_value(5*(index+period)))
        assert actual_a == actual_b and witness_order(index) != witness_order(index+period)
        periodic_checks.append({'slot_width':width,'origin':origin,'orders_count':len(orders),
                                'sampled_integer_period':period,'n':index,'n_plus_period':index+period,
                                'implementation_orders_equal':True,'witness_orders_different':True})
    belts = next(k for k in catalog['units'] if k['id']=='传送带')
    normals={'south':(0,-1),'north':(0,1),'west':(-1,0),'east':(1,0)}
    belt_pairs=set()
    for variant in belts['ports']['layouts']:
        for code in ('r0','r90','r180','r270'):
            roles={edge['role']:rotate_normal(*normals[edge['side']],code) for edge in variant}
            belt_pairs.add((roles['input'],roles['output']))
    assert len(belt_pairs)==12 and all(a!=b for a,b in belt_pairs)
    write_json('覆盖反例证据.json',{'scope':'几何和有限函数选点是实测；全时域不可表示由复核报告的代数证明给出。',
        'independent_geometry':geometries,'belt_ordered_pairs':len(belt_pairs),'witness_structure':structural,
        'witness_formula':'n为正的2的幂时B先A后，其余A先B后；共同到期t=5n。',
        'witness_prefix':[{'n':n,'time':5*n,'order':[t['target'] for t in witness_order(n)]} for n in range(33)],
        'finite_table_first_unlisted_time':325,'finite_table_diagnostic':exhaustion,
        'periodic_probe_examples':periodic_checks})
    print(json.dumps({'geometry':'通过','belt_pairs':len(belt_pairs),'finite_table':exhaustion,'periodic_examples':len(periodic_checks)},ensure_ascii=False))


if __name__ == '__main__':
    main()
