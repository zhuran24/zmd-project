#!/usr/bin/env python3
"""退回现行材料中的旧桥同种互斥读法；历史证据原件保持。须从求解器运行。"""
from pathlib import Path
import json,re
ROOT=Path.cwd(); OUT=ROOT/'内核维护/2026-09-22'; edits=[]
def edit(name, pairs):
 p=ROOT/name; s=p.read_text(); old=s
 for a,b in pairs:
  assert a in s,(name,a)
  s=s.replace(a,b)
 if s!=old: p.write_text(s); edits.append(name)
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
oldnote='两对端口各自拥有物品格，但同种物品在单位内只能占一个物品格，不能把两轴有格读成同种跨格豁免。容量例外的辖域未定；端口类型由先接端决定；轮询及分级按单位。'
newnote='规则第13行明确豁免桥接器：两对端口各自拥有物品格，可同时存放同一种物品，各轴每tick至多1件。容量例外的辖域未定；端口类型由先接端决定；轮询及分级按单位。'
edit('数据/工具/formal_units.py',[("'exempt' if name == '协议储存箱'", "'exempt' if name in {'协议储存箱', '桥接器'}"),(oldnote,newnote)])
edit('数据/工具/test_formal_catalog.py',[("else: units['桥接器']['inventory_rules']['same_item_across_slots']='exempt'","else: units['桥接器']['inventory_rules']['same_item_across_slots']='at_most_one_slot'")])
p=ROOT/'数据/正式静态目录.json';d=json.loads(p.read_text()); bridge=next(x for x in d['units'] if x['id']=='桥接器');bridge['inventory_rules']['same_item_across_slots']='exempt';bridge['notes']=newnote;dump(p,d);edits.append(str(p.relative_to(ROOT)))
edit('数据/样例/runtime_record.py',[("if units[uid]['kind']=='协议储存箱':continue","if kinds[units[uid]['kind']]['inventory_rules']['same_item_across_slots']=='exempt':continue")])
edit('数据/送料契约.md',[( '协议储存箱、缓存格是明文例外；桥接器两轴各自有格不构成同种跨格豁免','协议储存箱、缓存格和桥接器是明文例外；桥两轴可同时存放同种物品，各自受容量、滞留和端口额度约束'),('桥接器另一轴不被满速独占条款排除，但仍须服从同种跨格唯一性等规则','桥接器另一轴不被满速独占条款排除，且可同时承载同种物品；仍须服从各轴容量、滞留及按单位调度规则')])
for name in ['运行语义','选择点清单']:
 p=ROOT/f'规格/{name}.md';s=p.read_text()
 s=s.replace('R13仍约束同种物品同时只占一轴','R13明确豁免桥接器，两轴可同时装同一种物品，各自至多1件/tick')
 s=s.replace('R13的同种单格守卫继续适用，同一种物品同时只占一轴','R13明确豁免桥接器，同一种物品可同时占两轴，各自至多1件/tick')
 s=s.replace('AX-03补明R13的桥同种跨轴守卫，轴身份与联合占格约束分别保留。','AX-03旧桥同种跨轴守卫已于2026-09-22退回；轴身份、容量、滞留和按单位调度分别保留。')
 s=re.sub(r'> \*\*主会话补记（2026-09-22）：\*\*.*', '> **主会话补记（2026-09-22）：** 旧桥读法及其正文守卫已退回。现行规则第13行明确列「协议储存箱、缓存格和桥接器除外」；桥两轴可同时装同种物品，各自1件/tick。目录、内核装载/收货行为、样例校验和回归断言已同步，详见[维护记录](../内核维护/2026-09-22/记录.md)。',s)
 p.write_text(s);edits.append(str(p.relative_to(ROOT)))
edit('规格/受限转移定义.md',[('桥的目标格虽独立，仍须核同一单位同种单格通则，不能与另一轴已有同种物品同时占两格','桥属于R13同种单格例外，可与另一轴已有同种物品同时占两格；各轴仍独立核容量和滞留，按单位核轮询权限')])
edit('规格/参数扫描约减.md',[( '桥目标读另一轴防同种单格','桥目标按本轴核库存；另一轴仅在Peers及按单位调度依赖中读取'),('桥跨轴也因全机同种与按单位调度保留','桥跨轴因按单位调度保留'),('桥跨轴同种约束','桥跨轴调度依赖')])
edit('crates/kernel/src/tests.rs',[( '''/// 受限转移§4.1：桥格独立不豁免同单位同种单格，第二轴同种在此刻拒收。
#[test]
fn bridge_same_item_cannot_occupy_both_axes() {
    let mut e = fixture("bridge");
    put(&mut e, "south_box:storage:0", "源矿", 1);
    put(&mut e, "west_box:storage:0", "源矿", 1);
    let mut e = reload(e);
    e.step(true).unwrap();
    assert_eq!(
        count(&e, "bridge:vertical:0") + count(&e, "bridge:horizontal:0"),
        1
    );
    e.validate_inventory().unwrap();
}''','''/// R13桥例外、R23滞留：同种双轴同时占格、各自每tick一件，完整种子可恢复。
#[test]
fn bridge_same_item_occupies_both_axes_at_full_rate() {
    let mut e = fixture("bridge");
    put(&mut e, "south_box:storage:0", "源矿", 4);
    put(&mut e, "west_box:storage:0", "源矿", 4);
    let mut e = reload(e);
    let total = e.inventory_totals().unwrap();
    e.step(true).unwrap();
    for axis in ["vertical", "horizontal"] {
        assert_eq!(count(&e, &format!("bridge:{axis}:0")), 1);
    }
    // 新入桥物品必须滞留，不能在该tick进入对端箱。
    assert_eq!(count(&e, "north_box:storage:0"), 0);
    assert_eq!(count(&e, "east_box:storage:0"), 0);
    e.validate_inventory().unwrap();
    let mut e = reload(e);
    for delivered in 1..=4 {
        e.step(true).unwrap();
        assert_eq!(count(&e, "north_box:storage:0"), delivered);
        assert_eq!(count(&e, "east_box:storage:0"), delivered);
        assert_eq!(e.inventory_totals().unwrap(), total);
        e.validate_inventory().unwrap();
    }
}''')])
# 植物满线和计数的跨轴同种限制一并退回。
edit('会议成果/任务书7执行/植物运行试点.md',[( '桥使用已确定方向的轴，并满足R13：同一座桥同时承载的两轴物种相异，或另有证明保证同种从不同时请求占格且首格服务保持；无额外入流、门限或分级争用。本节满线切面两轴同时非空，适用桥的两轴必须为异种。','桥使用已确定方向的轴；R13豁免桥接器，两轴可同时承载同种或异种物品，各自1件/tick；无额外入流、门限或分级争用。'),('桥结构有两个物品格；按R13，同一种种子或植株在同桥同时至多占一格，两种不同物品才能同时占两轴。某植物形态的实际可占量按轴连接与跨轴身份守卫共同核算。','桥有两个物品格；按R13例外，同一种种子或植株也可同时占两轴。某植物形态的实际可占量按轴连接和每格容量核算。')])
# 几何、服务以现行R13重新给出；历史终修原件不改写。
p=ROOT/'会议成果/任务书7执行/密排布局.json';d=json.loads(p.read_text())
for r in d['routes']:
 if r['source_unit'] not in [f'M{x}' for x in range(213,219)]:continue
 r['service_capacity_given_receiving_boundary']='1 item/tick per independent path, including same-species bridge axes; requires continuously receiving downstream'
 c=r['service_contract'];c.update(kind='independent_axis_service',completion_to_box_bound_ticks=r['transport_slots']+1,completion_to_warehouse_bound_ticks=r['transport_slots']+6,same_species_bridge_guard='exempt under R13; capacity and residence checked per axis',preloaded_recovery_bound_ticks=106,proof='成品输出通路.md#4-突发在途恢复及产率账')
d['product_start_contract'].update(bridge_guard='R13 exemption: same species may occupy both axes',latency_proof='成品输出通路.md',preloaded_recovery_bound_ticks=106)
d['open_items']=[x for x in d['open_items'] if '共享桥服务' not in x and '空输出跨桥证明' not in x]
d['终修记录'].append({'date':'2026-09-22','summary':'旧桥读法已退回：逐轴同种1/tick，六路服务字段恢复，长路17/22及条件恢复106；实际产率null、认证false保持。'})
dump(p,d);edits.append(str(p.relative_to(ROOT)))
dump(OUT/'bridge-edit-files.json',edits)
print('\n'.join(edits))
