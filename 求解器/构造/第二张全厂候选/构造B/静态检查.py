#!/usr/bin/env python3
"""S2构造B的静态必要条件检查和不可布线证书核验。

仅用Python标准库，不调用接法生成器、不调用平面性库、不调用旧检查器。
没有坐标候选时，几何检查逐项记为未执行；不得把证书通过报成布局通过。
"""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from fractions import Fraction as Q
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
SUPPORTED_INPUTS = {
    '求解器/候选约束轮次/第98-100轮/前提快照/《明日方舟：终末地》游戏规则.txt': 'c8d3a17b8830baba18aea36c4c66f02f8873895188f8821176cc218aa6135f93',
    '求解器/候选约束轮次/第98-100轮/前提快照/求解任务.txt': '7bec7a1edf2f46644a6e6a75d588f5ff05202cc32d6b42430677ea39b878309b',
    '求解器/候选约束轮次/第98-100轮/前提快照/求解约束.txt': 'dfea46c61f29be5a86659bce3642009d2558ace073d6dbd79f5dd3c6475226db',
    '求解器/候选约束轮次/第98-100轮/推导98S2.md': '5d5d146fb200b34b8b1a7045c6584eac3349e48899cf8c71a7eec7d47f3685af',
    '求解器/构造/第一张全厂候选/格式.md': 'c1da2787a0b8f86201f9e207c897be3b8ddf4e49dca3284d03f34bc334019987',
}


def read(path):
    def unique(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                raise ValueError('重复JSON键：'+k)
            d[k] = v
        return d
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recipes():
    data = {
        '粉碎-源矿': ('粉碎机', {'源矿':1}, {'源石粉末':1}, 1),
        '粉碎-蓝铁块': ('粉碎机', {'蓝铁块':1}, {'蓝铁粉末':1}, 1),
        '精炼-蓝铁矿': ('精炼炉', {'蓝铁矿':1}, {'蓝铁块':1}, 1),
        '精炼-致密蓝铁': ('精炼炉', {'致密蓝铁粉末':1}, {'钢块':1}, 1),
        '塑形-钢质瓶': ('塑形机', {'钢块':2}, {'钢质瓶':1}, 1),
        '配件-钢制零件': ('配件机', {'钢块':1}, {'钢制零件':1}, 1),
        '封装-电池': ('封装机', {'钢制零件':10, '致密源石粉末':15}, {'高容谷地电池':1}, 5),
        '灌装-胶囊': ('灌装机', {'钢质瓶':10, '细磨荞花粉末':10}, {'精选荞愈胶囊':1}, 5),
    }
    for plant, output in [('砂叶', 3), ('荞花', 2)]:
        data['粉碎-'+plant] = ('粉碎机', {plant:1}, {plant+'粉末':output}, 1)
        data['采种-'+plant] = ('采种机', {plant:1}, {plant+'种子':2}, 1)
        data['种植-'+plant] = ('种植机', {plant+'种子':1}, {plant:1}, 1)
    for name, main, product in [('致密蓝铁', '蓝铁粉末', '致密蓝铁粉末'),
                                 ('致密源石', '源石粉末', '致密源石粉末'),
                                 ('细磨荞花', '荞花粉末', '细磨荞花粉末')]:
        data['研磨-'+name] = ('研磨机', {main:2, '砂叶粉末':1}, {product:1}, 1)
    return data


def expected_structure():
    """按机器出路逐项核对第2节，而不复用生成器的数据或函数。"""
    expected = Counter()
    recipe_by_id = {}

    def assign(ids, recipe):
        for uid in ids:
            recipe_by_id[uid] = recipe

    def link(source, target, item):
        expected[source, target, item] += 1

    assign((f'T{i}' for i in range(1, 35)), '精炼-蓝铁矿')
    assign((f'KB{i}' for i in range(1, 35)), '粉碎-蓝铁块')
    assign((f'U{i}' for i in range(1, 19)), '粉碎-源矿')
    assign((f'B{i}' for i in range(1, 18)), '研磨-致密蓝铁')
    assign((f'R{i}' for i in range(1, 18)), '精炼-致密蓝铁')
    assign((f'O{i}' for i in range(1, 10)), '研磨-致密源石')
    assign((f'Q{i}' for i in range(1, 7)), '研磨-细磨荞花')
    assign((f'P{i}' for i in range(1, 7)), '配件-钢制零件')
    assign((f'H{i}' for i in range(1, 7)), '塑形-钢质瓶')
    assign((f'E{i}' for i in range(1, 4)), '封装-电池')
    assign((f'F{i}' for i in range(1, 5)), '灌装-胶囊')
    for b in range(1, 18):
        for ore in [2*b-1, 2*b]:
            link(f'OB{ore}', f'T{ore}', '蓝铁矿')
            link(f'T{ore}', f'KB{ore}', '蓝铁块')
            link(f'KB{ore}', f'B{b}', '蓝铁粉末')
        link(f'B{b}', f'R{b}', '致密蓝铁粉末')
    for o in range(1, 10):
        for ore in [2*o-1, 2*o]:
            link('CORE' if ore <= 6 else f'OO{ore}', f'U{ore}', '源矿')
            link(f'U{ore}', f'O{o}', '源石粉末')
    for p in range(1, 7):
        link(f'R{p}', f'P{p}', '钢块')
    for h, refiners in enumerate([[7,8], [9,10], [11,12], [13,14], [15,16], [17]], 1):
        for r in refiners:
            link(f'R{r}', f'H{h}', '钢块')
    for e, pairs in enumerate([([1,2], [1,2,3]), ([3,4], [4,5,6]), ([5,6], [7,8,9])], 1):
        for p in pairs[0]:
            link(f'P{p}', f'E{e}', '钢制零件')
        for o in pairs[1]:
            link(f'O{o}', f'E{e}', '致密源石粉末')
        link(f'E{e}', 'CORE', '高容谷地电池')
    for f, supply in enumerate([[1,2], [3,4], [5], [6]], 1):
        for j in supply:
            link(f'H{j}', f'F{f}', '钢质瓶')
            link(f'Q{j}', f'F{f}', '细磨荞花粉末')
        link(f'F{f}', 'CORE', '精选荞愈胶囊')
    groups = {
        1:['B1','B2','O1'], 2:['O2','O3'], 3:['B3','B4','O4'], 4:['O5','O6'],
        5:['B5','B6','O7'], 6:['O8','O9'], 7:['B7','B8','B9'], 8:['B10','Q1','Q2'],
        9:['B11','B12','B13'], 10:['B14','Q3','Q4'], 11:['B15','B16','Q5'],
        12:['B17'], 13:['Q6'],
    }
    for p, plant, n in [('S','砂叶',13), ('Q','荞花',6)]:
        for i in range(1, n+1):
            a, b, c = f'{p}A{i}', f'{p}B{i}', f'{p}C{i}'
            k = f'S{i}' if p == 'S' else f'KQ{i}'
            assign([a,b], '种植-'+plant)
            assign([c], '采种-'+plant)
            assign([k], '粉碎-'+plant)
            for source, target, item in [(c,a,plant+'种子'), (c,b,plant+'种子'),
                                         (a,c,plant), (b,k,plant)]:
                link(source,target,item)
            if p == 'S':
                for target in groups[i]:
                    link(k,target,'砂叶粉末')
            else:
                link(k,f'Q{i}','荞花粉末')
                if i <= 5:
                    link(k,f'Q{i}','荞花粉末')
    return expected, recipe_by_id


def check_contract(d):
    errors = []
    if d.get('schema')!='s2-logical-contract-v1' or d.get('is_layout') is not False:
        errors.append('逻辑接法版本或非布局标记不符')
    if d.get('core') != {'id':'CORE','kind':'协议核心'}:
        errors.append('唯一协议核心身份不符')
    if d.get('geometry_requirements') != dict(W=70,H=70,pure_belts=True,
            minimum_transport_cells_per_feed=1,disjoint_transport_cells=True,
            no_extra_channels=True,equal_lengths=[['H6','F4'],['Q6','F4']]):
        errors.append('S2几何要求不符')
    expected, er = expected_structure()
    actual = Counter((f['source'], f['target'], f['item']) for f in d['feeds'])
    if expected != actual:
        errors.append(dict(kind='接法不符', missing=list((expected-actual).elements()),
                           extra=list((actual-expected).elements())))
    mr = {m['id']:m['recipe_id'] for m in d['machines']}
    if mr != er or len(mr) != len(d['machines']):
        errors.append('逐机配方或机器身份不符')
    if len({f['id'] for f in d['feeds']}) != 325 or len(d['feeds']) != 325:
        errors.append('进路身份或数量不符')
    expected_sources = {f'OB{i}':'蓝铁矿' for i in range(1,35)}
    expected_sources.update({f'OO{i}':'源矿' for i in range(7,19)})
    sources = {s['id']:s['item'] for s in d['boundary_sources']}
    if sources != expected_sources or len(d['boundary_sources']) != 46:
        errors.append('边界矿源不符')
    if any(s['kind'] != '仓库取货口' for s in d['boundary_sources']):
        errors.append('将非边界单位冒充边界取货口')
    core_out = [f for f in d['feeds'] if f['source']=='CORE']
    if sorted((f['target'],f['item'],f.get('source_port_index')) for f in core_out) != \
       sorted((f'U{i}', '源矿', i-1) for i in range(1,7)):
        errors.append('协议核心六个源矿端口不符')
    incoming, outgoing = defaultdict(Counter), defaultdict(Counter)
    for f in d['feeds']:
        rate = Q(f['rate'])
        if not 0 < rate <= 1:
            errors.append('进路平均流超出端口容量：'+f['id'])
        outgoing[f['source']][f['item']] += rate
        incoming[f['target']][f['item']] += rate
    catalog = recipes()
    for m in d['machines']:
        model, ins, outs, duration = catalog[m['recipe_id']]
        rate = Q(m['batch_rate'])
        if model != m['model'] or not 0 < rate*duration <= 1:
            errors.append('配方/制造能力不符：'+m['id'])
        if incoming[m['id']] != Counter({k:rate*v for k,v in ins.items()}):
            errors.append('原料守恒不符：'+m['id'])
        if outgoing[m['id']] != Counter({k:rate*v for k,v in outs.items()}):
            errors.append('产物守恒不符：'+m['id'])
    for source, item in expected_sources.items():
        if outgoing[source] != Counter({item:Q(1)}) or incoming[source]:
            errors.append('边界取矿率不符：'+source)
    if outgoing['CORE'] != Counter({'源矿':Q(6)}):
        errors.append('核心取矿率不符')
    if incoming['CORE'] != Counter({'高容谷地电池':Q(3,5),'精选荞愈胶囊':Q(11,20)}):
        errors.append('成品入库率不符')
    return dict(status='PASS' if not errors else 'FAIL', errors=errors,
                machine_count=len(d['machines']), feed_count=len(d['feeds']),
                average_flow='逐机精确有理数守恒；不表示路径已摆放或运行已认证')


def verify_witness(w, edges, boundary):
    errors = []
    left, right, paths = w['left'], w['right'], w['paths']
    branch = set(left + right)
    if len(left)!=3 or len(right)!=3 or len(branch)!=6 or 'EXT' not in branch:
        errors.append('分支顶点不为含EXT的互异3+3组')
    seen_internal, pairs = set(), Counter()
    used_edges = set()
    for path in paths:
        if len(path) < 2 or len(set(path)) != len(path):
            errors.append('路径为空或重复经过顶点')
            continue
        if path[0] not in left or path[-1] not in right:
            errors.append('路径端点分组不符')
        pairs[path[0],path[-1]] += 1
        inner = set(path[1:-1])
        if inner & branch:
            errors.append('路径内部经过分支顶点')
        if inner & seen_internal:
            errors.append('九条路径内部不相交条件违反')
        seen_internal |= inner
        for a,b in zip(path,path[1:]):
            edge = frozenset([a,b])
            if 'EXT' in edge:
                other = b if a=='EXT' else a
                if other not in boundary:
                    errors.append('辅助外点连接了非边界来源：'+other)
            elif edge not in edges:
                errors.append('S2没有这条边：'+a+'--'+b)
            if edge in used_edges:
                errors.append('证书路径共用边')
            used_edges.add(edge)
    if pairs != Counter({(a,b):1 for a in left for b in right}):
        errors.append('缺少或重复三对三的九对端点')
    vertices = branch | seen_internal
    degree = Counter()
    for edge in used_edges:
        for v in edge:
            degree[v] += 1
    if any(degree[v]!=3 for v in branch) or any(degree[v]!=2 for v in seen_internal):
        errors.append('不是六个三度顶点加二度细分顶点')
    return dict(id=w['id'], status='PASS' if not errors else 'FAIL', errors=errors,
                vertices=len(vertices), edges=len(used_edges),
                suppressed_vertices=6, suppressed_edges=9, bipartite_planar_edge_limit=8,
                contradiction='平面简单二部图应满足m≤2n−4；缩去二度点后9>2×6−4=8。',
                degree_three_vertices=left+right, interior_vertices=sorted(seen_internal))


def verify_certificate(d, cert, contract_path):
    boundary = {s['id'] for s in d['boundary_sources']}
    edges = {frozenset([f['source'],f['target']]) for f in d['feeds']}
    errors = []
    if cert.get('schema')!='s2-boundary-k33-v1' or cert.get('exterior_vertex')!='EXT':
        errors.append('证书版本或外部辅助点身份不符')
    if cert['contract_sha256'] != sha(contract_path):
        errors.append('证书与接法文件哈希不符')
    expected_exterior = {frozenset(['EXT',s]) for s in boundary}
    exterior = [frozenset(e) for e in cert['exterior_edges']]
    if set(exterior)!=expected_exterior or len(exterior)!=46:
        errors.append('外侧辅助边列表不符')
    results = [verify_witness(w, edges, boundary) for w in cert['witnesses']]
    partitions = {(frozenset(w['left']),frozenset(w['right'])) for w in cert['witnesses']}
    if len(results)!=4 or len(partitions)!=4 or any(r['status']!='PASS' for r in results):
        errors.append('四份证书未全部通过')
    return dict(status='PASS' if not errors else 'FAIL', errors=errors, witnesses=results,
                meaning='通过表示不可平面布线证书有效，不是布局通过。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default='静态检查结果.json')
    args = parser.parse_args()
    output = (BASE/args.out).resolve()
    if not output.is_relative_to(BASE):
        parser.error('输出只能在构造B目录内')
    path = BASE/'S2接法.json'
    d, cert = read(path), read(BASE/'不可平面布线证书.json')
    fingerprints = read(BASE/'输入指纹.json')
    declared = {r['path']:r['sha256'] for r in fingerprints}
    input_results = [dict(path=p,supported=h,declared=declared.get(p),actual=sha(ROOT/p),
                          matches=declared.get(p)==h==sha(ROOT/p)) for p,h in SUPPORTED_INPUTS.items()]
    inventory_matches = len(fingerprints)==5 and set(declared)==set(SUPPORTED_INPUTS)
    contract_result = check_contract(d)
    certificate_result = verify_certificate(d,cert,path)
    proven = inventory_matches and all(r['matches'] for r in input_results) and contract_result['status']=='PASS' and certificate_result['status']=='PASS'
    fields = ['占格不重叠','全部单位在70×70内','端口与实际自动通道（无多余通道）',
              '每条进路纯有向传送带、至少一格且运输格互不共用',
              '各机器配方与实体端口','供电桩覆盖','协议核心和仓库存取货口位置',
              'H6→F4与Q6→F4运输格数相同','最大空矩形面积、同面积短边优先及短边至少6格']
    result = dict(checker='s2-boundary-certificate-standard-library-v1',
                  checker_sha256=sha(Path(__file__)), contract_sha256=sha(path),
                  input_fingerprints=input_results,input_inventory_matches=inventory_matches,
                  contract=contract_result,
                  boundary_planarity=dict(status='FAIL' if proven else 'UNRESOLVED',
                      evidence='不可平面布线证书.json',
                      reason='S2所需边界增广图含四个K3,3细分子图。' if proven else '证书未全部核验'),
                  certificate_verification=certificate_result,
                  geometric_checks=[dict(check=k,status='NOT_RUN_NO_LAYOUT',
                                        reason='平面性必要条件失败，未产生坐标候选。') for k in fields],
                  status='S2_GEOMETRY_IMPOSSIBLE' if proven else 'UNRESOLVED',
                  static_pass=False, layout_path='', empty_rect='',
                  runtime_certified=False, L_updated=False,
                  scope='仅第98轮S2第2节的固定接法、纯带和边界取货口要求；不排除修改接法或允许运输交叉后的布局。')
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'],static_pass=False,
                          certificate_pass=proven,output=str(output)),ensure_ascii=False))
    return 0 if proven else 1


if __name__ == '__main__':
    raise SystemExit(main())
