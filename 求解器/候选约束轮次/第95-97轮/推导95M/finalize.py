"""交付结构、链接、输入指纹和关键计算结果核验；只写本目录。"""
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
import datetime, hashlib, json, math, re

OUT=Path(__file__).resolve().parent
REPORT=OUT.parent/'推导95M.md'


def read(name): return json.loads((OUT/name).read_text())


def main():
    notes = [
      ('分叉分支','必要条件','按单位重建所得接通先后，遍历临时规则允许的数层选择。','层数；临时2、4。','§1量词及绕回边界。','修订正式及92版；采纳94量词，按临时规则限定。'),
      ('取货分级','必要条件','需固定级序时，各允许已定层数下须L高<L低。','取货优先级；临时4。','§2用单位重建构造反转等层级序。','修订正式及92版；采纳94严格差，不采纳93仅充分之说。'),
      ('来源定序','必要条件','运输格或制造存货格有q+b=Q；所需份额要求Q−b≥r。','循环守恒；临时收货。','§3排除缓存转化，区分实际流量与容量。','修订正式及92版；采纳93集合限定，保留94认可部分。'),
      ('面积预算','必要条件','保留1182、4639、1110配置及增配≤1107结论，取消位置限制。','内带缺口、供电、占地守恒。','§5完整面积及外边分段证明。','修订正式及92版；采纳两轮恢复全范围，统一X/Y。'),
      ('内带缺口','必要条件','指定无箱配置：4(T+F)+2P≥921，4(T+F)+2J≥921+X+Y。','端口、方向、近边补偿。','§4两编码重算15,697个有效分支。','修订正式及92版；采纳93补偿，94删Y矿石格不必采用。'),
      ('专用进路下缓存格不空的传递','充分条件','§6的纯带、正确物品与单出口来源前提保证X步末缓存非空。','制造、滞留；临时1、5。','§6逐格回填、供料计数及周期性。','修订正式及92版；采纳94矿石限定，临时规则下输入限纯带。'),
      ('分流先判的首段带容量','必要条件','完整n格带元件在分流器后判：流量≤8n/(8n+1)。','滞留、实际判定、周期收支。','§7格步占用两侧界，并得其他支下界。','修订92候选；采纳94完整元件限定。'),
      ('研磨单路换主料步数余量','必要条件','8B+W≤NK，N−a/9≥31.5；N=32时W平均≤4、a≤4。','存货格、研磨配方、滞留。','§8九步间隔和周期余量。','修订92候选；采纳94作用域及一般式，保留93计数。'),
      ('无分流网络的判定先后无关','简化','§9结构子类可合并同层及非运输判定排列，仍覆盖轮询和少过。','临时收货；层数、通道结构。','§9稳定可送集合及独立动作交换。','修订92候选；采纳94诊断，限每桥一轴有通道，不另立调度规则。'),
      ('全厂专用进路接法的调试办法','充分条件','关A/C后清理、分次装料，统一开机结束；Φ=100或100+L。','接法、开关、整批入格、库存。','§10有限清理和终点直接记账。','修订92候选；采纳两轮关机、腾格、统一开启，只保证起态。'),
    ]
    keys=('name','kind','text','basis','derivation','relation')
    candidates=[dict(zip(keys,x)) for x in notes]
    payload={'report_path':str(REPORT.resolve()),'candidates':candidates,
             'status':'已完成，十条待审','summary':'合并十条修正候选；临时规则下收窄两项范围，完整证明及核算留档。','error':''}
    listed=json.loads((OUT.parent/'修正清单.json').read_text())
    assert [(x['name'],x['kind']) for x in candidates]==[(x['name'],x['kind']) for x in listed]
    assert Counter(x['kind'] for x in candidates)=={'必要条件':7,'充分条件':2,'简化':1}
    assert all(set(x)==set(keys) and all(isinstance(v,str) and v for v in x.values()) for x in candidates)
    doc=REPORT.read_text()
    assert doc.count('状态：待审。')==10
    for x in candidates:
        assert len(re.findall(r'^'+re.escape(x['name'])+'：',doc,re.M))==1,x['name']
    assert len(re.findall(r'^据：',doc,re.M))==10
    assert len(re.findall(r'^推导：',doc,re.M))==10
    assert len(re.findall(r'^relation：',doc,re.M))==10
    (OUT/'result.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')

    # Full row comparison, not just matching maxima.
    a,b=read('scope_a.json'),read('scope_b.json')
    assert a['cases']==b['cases']
    assert a['maximum']==b['maximum']==91
    assert not a['violations'] and not b['violations']
    assert len(a['cases'])==15697
    assert a['incompatible_fixed_machine']==b['incompatible_fixed_machine']==1042
    ca,cb=read('corner_a.json')['cases'],read('corner_b.json')['cases']
    assert len(ca)==len(cb)==135
    for x,y in zip(ca,cb):
        assert x['status']==y['status']=='OPTIMAL'
        for k in ('left_gap','bottom_gap','mode','options','bound'):assert x[k]==y[k]
    aa,ab=read('arithmetic_a.json'),read('arithmetic_b.json')
    matched=('recipe_rates_r0','machine_counts','manufacturing_area','total_item_output',
             'machine_input_ports','machine_output_ports_active_products','interfaces',
             'single_costs_doubled','weight_tables','pj_1110')
    for key in matched:assert aa[key]==ab[key],key

    # Outer-boundary formula vs independent enumeration of both inequalities.
    boundary=[]
    for length,segments,extra in ((71,2,1),(101,3,2),(138,2,2),(71,2,0),(101,3,0),(138,2,0)):
        closed=max(0,math.ceil(F(length-14-8*extra-5*segments,6)))
        brute=min(x for x in range(50) if any(
            m<=x+c+t+segments and length<=5*m+9*c+3*t+x
            for c in (0,1) for t in range(extra+1) for m in range(100)))
        assert closed==brute
        boundary.append({'length':length,'segments':segments,'extra_segments':extra,'min_X':closed})
    extra_bound=max(F(2*4751-32*p+4*j-287,8)
                    for p in range(10,348) for j in range(p+1)
                    if 23*p-10*j>=217 and 54*p-25*j>=520)
    assert str(extra_bound)==ab['extra_global_area_upper']=='8895/8'
    allowed_pj=[[p,j] for p in range(10,348) for j in range(p+1)
                if 23*p-10*j>=217 and 54*p-25*j>=520 and 16*p-2*j<=199]
    assert max(p for p,j in allowed_pj)==13
    assert min(j for p,j in allowed_pj if p==13)==5
    assert read('core_checks.json')['all_checks_pass']
    assert read('startup_checks.json')['all_checks_pass']
    assert read('startup_checks.json')['unrepaired']['first_C_full_after_steps']==3249

    changed=[]
    for x in read('inputs.json')['files']:
        h=hashlib.sha256(Path(x['path']).read_bytes()).hexdigest()
        if h!=x['sha256']:changed.append(x['path'])
    assert not changed,changed
    # Link targets must exist, except validation itself, created below.
    missing=[]
    for raw in re.findall(r'\]\(([^)]+)\)',doc):
        if '://' in raw:continue
        target=raw.split('#',1)[0]
        if target and not (REPORT.parent/target).exists():missing.append(raw)
    assert not missing,missing
    for p in OUT.rglob('*'):
        if p.is_file():
            assert p.suffix in ('.py','.log','.json','.md','.gz'),p
            assert p.stat().st_size<100*1024*1024 or p.suffix=='.gz',p
    result={'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'report_sha256':hashlib.sha256(REPORT.read_bytes()).hexdigest(),
            'candidate_count':len(candidates),'kind_counts':dict(Counter(x['kind'] for x in candidates)),
            'input_files_unchanged':True,'input_file_count':len(read('inputs.json')['files']),
            'scope_valid_branches':len(a['cases']),'scope_fixed_conflicts':a['incompatible_fixed_machine'],
            'scope_rows_equal':True,'corner_branches':len(ca),'arithmetic_fields_equal':list(matched),
            'outer_boundary_two_encodings':boundary,'extra_area_upper':str(extra_bound),
            'allowed_PJ_at_1110':allowed_pj,'all_local_links_exist':True,
            'core_checks_pass':True,'startup_checks_pass':True,
            'schema_checks_pass':True,'all_checks_pass':True}
    (OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    manifest={str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    (OUT/'manifest.json').write_text(json.dumps({'report_sha256':result['report_sha256'],'files':manifest},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'candidate_count':len(candidates),'input_files_unchanged':True,'scope_rows_equal':True,
                      'outer_boundary_min_X':[x['min_X'] for x in boundary],
                      'extra_area_upper':str(extra_bound),'all_checks_pass':True},ensure_ascii=False))


if __name__=='__main__':main()
