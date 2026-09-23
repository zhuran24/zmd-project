//! 第四轮§4.7：独立机制断言与表示/停止/守恒回归。
use super::*;
use crate::{
    config::{Axis, Disposition},
    model::*,
    output::*,
    value::*,
};
use serde_json::{json, Value};
use std::{collections::BTreeMap, path::PathBuf};
#[path = "tests_revision.rs"]
mod revision;
#[path = "tests_revision_r2.rs"]
mod revision_r2;
#[path = "tests_revision_r3.rs"]
mod revision_r3;
#[path = "tests_revision_r4.rs"]
mod revision_r4;
#[path = "tests_round5.rs"]
mod round5;
/// 第四轮§4.7：只读样例路径。
fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .unwrap()
}
/// 受限模型声明§2：加载当前配置。
fn config() -> Config {
    Config::parse(read_json(&root().join("规格/内核配置-v1.json")).unwrap()).unwrap()
}
/// 内核输入§6：提供已验起点，不从样例名决定转移。
fn engine(name: &str) -> Engine {
    let p = root().join(format!("数据/样例/{name}.json"));
    Engine::new(Input::load(&p, &config(), false).unwrap()).unwrap()
}
/// 内核输入§5：测试赋值同时更新当前参数，不制造隐式差异。
fn set_axis(raw: &mut Value, axis: &str, value: Value) {
    for g in ["fixed", "offline_mutable", "fixedness_unproven"] {
        if raw["parameters"][g].get(axis).is_some() {
            raw["parameters"][g][axis]["value"] = value.clone();
        }
    }
    if let Some(rows) = raw["initial_state"]["nonwarehouse"]["value"]["semantic_context"]
        ["parameter_values"]
        .as_array_mut()
    {
        for row in rows {
            if row["axis"] == axis {
                row["value"]["value"] = value.clone();
            }
        }
    }
}
/// 受限转移§4.1：构造匿名空格，且显式给 O 的位置。
fn empty(e: &mut Engine, id: &str) {
    let i = e.state.warehouse.slots.len();
    e.state.warehouse.slots.push(WarehouseSlot {
        slot: id.into(),
        item: None,
        quantity: Quantity::calc(0),
        empty_identity: Decision::specified(Value::Null, "受限转移§4.1：试验匿名空格"),
    });
    e.warehouse.insert(id.into(), i);
    e.state
        .semantic_context
        .arbitration
        .warehouse_empty_slot_order
        .push(id.into());
}
/// 受限转移§4.1：测试有限库存内容，所有量仍经过真实 put。
fn put(e: &mut Engine, slot: &str, item: &str, n: i64) {
    e.put(slot, item, n).unwrap()
}
/// 内核输入§6：测试普通格件数。
fn count(e: &Engine, slot: &str) -> i64 {
    e.state.inventory[e.inv[slot]]
        .contents
        .iter()
        .map(|c| c.quantity.integer(slot).unwrap())
        .sum()
}
/// 第四轮§4.7：99轴身份唯一、18个停止轴逐项拒绝非 stop 值。
#[test]
fn config_axes_and_all_stop_values() {
    let c = config();
    assert_eq!(c.axes.len(), 99);
    let stops: Vec<_> = c
        .axes
        .iter()
        .filter(|(_, r)| r.disposition == Disposition::Stop)
        .map(|(a, _)| *a)
        .collect();
    assert_eq!(stops.len(), 18);
    let original = read_json(&root().join("数据/样例/混做粉碎机两下游.json")).unwrap();
    for axis in stops {
        let mut raw = original.clone();
        set_axis(&mut raw, axis.name(), json!("unsupported_test_value"));
        let p: crate::config::Parameters = decode(raw["parameters"].clone(), "parameters").unwrap();
        let err = c.validate(&p, false).unwrap_err();
        assert_eq!(err.axis, axis.name());
        assert!(err.location.contains(axis.name()));
        assert_eq!(c.request(axis, "request").unwrap_err().axis, axis.name());
    }
}
/// 第四轮§4.7：三个结构例都由 Rust 静态检查，v2 不冒充可运行。
#[test]
fn three_examples_static() {
    for name in ["混做粉碎机两下游", "分流器三路轮询", "桥接器双通路"] {
        let p = root().join(format!("数据/样例/{name}.json"));
        let raw = read_json(&p).unwrap();
        let structural = raw["schema"] == "kernel-input-v2";
        Input::load(&p, &config(), structural).unwrap();
    }
}
/// 第四轮§4.7：两个参数投影逐轴决定、处置、声明指纹全部检查。
#[test]
fn projections() {
    for (name, projection) in [
        ("混做粉碎机两下游", "kernel_profile_v1参数赋值.json"),
        ("分流器三路轮询", "分流器三路轮询-参数赋值.json"),
    ] {
        let e = engine(name);
        validate_projection(
            &root().join("数据/样例").join(projection),
            &e.input,
            &config(),
        )
        .unwrap();
    }
}
/// 第四轮§4.7：相同输入重复运行逐字节一致；单位及 PC/BC 数组反转不改变完整轨迹。
#[test]
fn byte_determinism_and_layout_permutation() {
    for name in ["混做粉碎机两下游", "分流器三路轮询"] {
        let mut a = engine(name);
        let mut b = engine(name);
        let mut raw = b.input.raw.clone();
        for k in ["units", "physical_channels", "buffer_channels"] {
            raw["layout"][k].as_array_mut().unwrap().reverse();
        }
        let mut shuffled =
            Engine::new(Input::parse(raw, &b.input.path, &config(), false).unwrap()).unwrap();
        for _ in 0..4 {
            let x = a.step(true).unwrap().unwrap();
            let y = b.step(true).unwrap().unwrap();
            let z = shuffled.step(true).unwrap().unwrap();
            assert_eq!(
                serde_json::to_vec(&x).unwrap(),
                serde_json::to_vec(&y).unwrap()
            );
            assert_eq!(x, z);
        }
    }
}
/// 第四轮§4.7：目录机型、配方数及 SHA 都来自正式文件。
#[test]
fn catalog_and_geometry() {
    let e = engine("混做粉碎机两下游");
    assert_eq!(e.input.catalog.kinds.len(), 18);
    assert_eq!(e.input.catalog.recipes.len(), 18);
    assert_eq!(e.input.geometry.channels.len(), 11);
    assert_eq!(e.input.geometry.buffers.len(), 8);
    assert_eq!(
        e.input.catalog.sha256,
        crate::catalog::sha256(&root().join("数据/正式静态目录.json")).unwrap()
    );
}
/// 受限转移§5.1：失败循环收敛到规定重复边界，不只检测库存不变。
#[test]
fn closure_and_resources() {
    let mut e = engine("分流器三路轮询");
    let t = e.step(true).unwrap().unwrap();
    assert!(t["closure"]["scan_rounds"].as_u64().unwrap() >= 2);
    let mut limited = engine("分流器三路轮询");
    limited.max_sweeps = 1;
    let err = limited.step(true).unwrap_err();
    assert_eq!(err.status, "inconclusive");
    assert_eq!(err.axis, "resource.sweeps");
}
/// 受限转移§4.1：匿名 E 严格递减，留存身份清空后不回 E，同种重用原格。
#[test]
fn warehouse_identity_monotone() {
    let mut e = engine("混做粉碎机两下游");
    empty(&mut e, "spare_b");
    empty(&mut e, "spare_a");
    let before = e.empty_slots();
    assert!(e
        .deposit(BTreeMap::from([("高容谷地电池".into(), 2)]))
        .unwrap());
    assert!(e.empty_slots().is_subset(&before));
    assert_eq!(
        e.state
            .semantic_context
            .arbitration
            .warehouse_empty_slot_order,
        vec!["spare_a"]
    );
    assert_eq!(
        e.state.warehouse.slots[e.warehouse["spare_b"]]
            .item
            .as_deref(),
        Some("高容谷地电池")
    );
    e.remove("spare_b", "高容谷地电池", 2).unwrap();
    assert!(!e.empty_slots().contains("spare_b"));
    e.deposit(BTreeMap::from([("高容谷地电池".into(), 1)]))
        .unwrap();
    assert_eq!(
        e.state.warehouse.slots[e.warehouse["spare_b"]]
            .quantity
            .integer("q")
            .unwrap(),
        1
    );
    assert_eq!(e.delivery["高容谷地电池"], 3);
}
/// 受限转移§4.3：被指派匿名格与两种新物种竞争即停，并保持整个判前状态。
#[test]
fn warehouse_competition_atomic_stop() {
    let mut e = engine("分流器三路轮询");
    empty(&mut e, "assigned");
    e.input
        .assignments
        .insert("ore_source:north:1".into(), "assigned".into());
    e.input
        .switches
        .insert(("south_box".into(), "transfer".into()), true);
    assert!(e.enabled("south_box", "transfer"));
    put(&mut e, "south_box:storage:0", "高容谷地电池", 1);
    put(&mut e, "south_box:storage:1", "精选荞愈胶囊", 1);
    let before = json!(e.state);
    let err = e.transfer("south_box", "unit-test-transfer").unwrap_err();
    assert_eq!(err.axis, "warehouse.empty_slot_identity");
    assert_eq!(json!(e.state), before);
    assert!(e.delivery.is_empty());
}
/// 受限转移§4.3：未指派匿名格可以按 UTF-8 规范映射，不以箱格遍历顺序决定。
#[test]
fn warehouse_unassigned_species_order() {
    let mut e = engine("分流器三路轮询");
    empty(&mut e, "first");
    empty(&mut e, "second");
    let items: BTreeMap<String, i64> =
        BTreeMap::from([("高容谷地电池".into(), 1), ("精选荞愈胶囊".into(), 1)]);
    let first = items.keys().next().unwrap().clone();
    e.deposit(items).unwrap();
    assert_eq!(
        e.state.warehouse.slots[e.warehouse["first"]]
            .item
            .as_deref(),
        Some(first.as_str())
    );
    assert!(e.empty_slots().is_empty());
}
/// 受限转移§4.3：有身份目标和单种新物种不触发多种竞争停止。
#[test]
fn warehouse_single_unknown_with_assigned_empty() {
    let mut e = engine("分流器三路轮询");
    empty(&mut e, "assigned");
    e.input
        .assignments
        .insert("ore_source:north:1".into(), "assigned".into());
    e.state.warehouse.slots[e.warehouse["warehouse_0"]].quantity = Quantity::calc(79999);
    assert!(e
        .deposit(BTreeMap::from([
            ("源矿".into(), 1),
            ("高容谷地电池".into(), 1)
        ]))
        .unwrap());
    assert_eq!(
        e.state.warehouse.slots[e.warehouse["assigned"]]
            .item
            .as_deref(),
        Some("高容谷地电池")
    );
}
/// 受限转移§4.1：错误 O、重复历史物种、新标签冲突均拒收，失败不改变 O。
#[test]
fn warehouse_invalid_identity_and_order() {
    let mut e = engine("混做粉碎机两下游");
    empty(&mut e, "spare");
    e.state
        .semantic_context
        .arbitration
        .warehouse_empty_slot_order
        .push("warehouse_0".into());
    assert_eq!(
        e.deposit(BTreeMap::from([("高容谷地电池".into(), 1)]))
            .unwrap_err()
            .status,
        "invalid_input"
    );
    e.state
        .semantic_context
        .arbitration
        .warehouse_empty_slot_order
        .pop();
    let i = e.warehouse["spare"];
    e.state.warehouse.slots[i].empty_identity = Decision::specified(json!("源矿"), "冲突负例");
    e.state
        .semantic_context
        .arbitration
        .warehouse_empty_slot_order
        .clear();
    assert!(e.warehouse_targets().is_err());
}
/// 受限转移§4.3：容量拒收整箱保留，但确有判定并起冷却；空箱亦起冷却。
#[test]
fn transfer_capacity_and_empty_cooldown() {
    let mut e = engine("分流器三路轮询");
    e.input
        .switches
        .insert(("south_box".into(), "transfer".into()), true);
    put(&mut e, "south_box:storage:0", "源矿", 1);
    let warehouse = e.state.warehouse.clone();
    assert_eq!(
        e.transfer("south_box", "unit-test-transfer").unwrap().0,
        "failure"
    );
    assert_eq!(count(&e, "south_box:storage:0"), 1);
    assert_eq!(e.state.warehouse, warehouse);
    let pi = e.progress["south_box"];
    assert_eq!(
        e.state.progress[pi].cooldowns[0]
            .remaining
            .integer("q")
            .unwrap(),
        5
    );
    e.state.inventory[e.inv["south_box:storage:0"]]
        .contents
        .clear();
    e.state.progress[pi].cooldowns[0].remaining = Time::at(0);
    let (status, details) = e.transfer("south_box", "unit-test-transfer").unwrap();
    assert_eq!(status, "success");
    assert_eq!(serde_json::from_str::<Value>(&details).unwrap(),
        json!({"cooldown_restarted": true, "retained": {}, "sent": {}}));
    assert_eq!(
        e.state.progress[pi].cooldowns[0]
            .remaining
            .integer("q")
            .unwrap(),
        5
    );
}
/// 受限转移§4.3：完整传输入仓保持全基地逐物种计数，交付单独记账。
#[test]
fn transfer_conservation() {
    let mut e = engine("分流器三路轮询");
    e.input
        .switches
        .insert(("south_box".into(), "transfer".into()), true);
    put(&mut e, "south_box:storage:0", "高容谷地电池", 7);
    put(&mut e, "south_box:storage:1", "精选荞愈胶囊", 2);
    let total = e.inventory_totals().unwrap();
    assert_eq!(
        e.transfer("south_box", "unit-test-transfer").unwrap().0,
        "success"
    );
    assert_eq!(e.inventory_totals().unwrap(), total);
    assert_eq!(
        e.delivery,
        BTreeMap::from([("高容谷地电池".into(), 7), ("精选荞愈胶囊".into(), 2)])
    );
}
/// 受限转移§4.1：箱源严格编号最小非空格；不因物种拒收跳到下一格。
#[test]
fn box_selectors() {
    let mut e = engine("分流器三路轮询");
    put(&mut e, "south_box:storage:2", "钢块", 1);
    put(&mut e, "south_box:storage:1", "源矿", 1);
    assert_eq!(
        e.source("south_box:north:0").unwrap().unwrap().0,
        "south_box:storage:1"
    );
    put(&mut e, "south_box:storage:0", "砂叶", 50);
    assert_eq!(
        e.target("south_box:south:0", "砂叶").unwrap().unwrap(),
        "south_box:storage:3"
    );
    assert_eq!(
        e.source("south_box:north:0").unwrap().unwrap().1.item,
        "砂叶"
    );
}
/// 受限转移§4.2：双物种原料整批归集，原料留缓存直到完成，额外数量留输入。
#[test]
fn manufacturing_two_material_batch() {
    let mut e = engine("混做粉碎机两下游");
    put(&mut e, "grinder_a:input:0", "源石粉末", 3);
    put(&mut e, "grinder_a:input:1", "砂叶粉末", 2);
    let before = e.inventory_totals().unwrap();
    e.step(true).unwrap();
    assert_eq!(count(&e, "grinder_a:input:0"), 1);
    assert_eq!(count(&e, "grinder_a:input:1"), 1);
    assert_eq!(count(&e, "grinder_a:buffer:0"), 3);
    assert_eq!(
        e.inventory_totals().unwrap().get("源石粉末"),
        before.get("源石粉末")
    );
    e.step(true).unwrap();
    assert_eq!(count(&e, "grinder_a:output:0"), 1);
    assert_eq!(
        e.state.inventory[e.inv["grinder_a:output:0"]].contents[0].item,
        "致密源石粉末"
    );
}
/// 受限转移§4.2：停用只阻止开工，缓存内部归集仍发生且不减进度。
#[test]
fn manufacture_disabled_intake_and_pause() {
    let mut e = engine("混做粉碎机两下游");
    e.input
        .switches
        .insert(("crusher".into(), "manufacture".into()), false);
    put(&mut e, "crusher:input:0", "荞花", 1);
    e.step(true).unwrap();
    assert_eq!(e.state.progress[e.progress["crusher"]].phase, "intake");
    assert_eq!(count(&e, "crusher:buffer:0"), 1);
    e.step(true).unwrap();
    assert_eq!(e.state.progress[e.progress["crusher"]].phase, "intake");
    assert!(e.pending.is_empty());
}
/// 受限转移§4.2：产物在任一输入格占位时，整批出缓存不能非法跨格。
#[test]
fn completed_output_conflict_retains_batch() {
    let mut e = engine("混做粉碎机两下游");
    put(&mut e, "crusher:input:0", "源石粉末", 1);
    put(&mut e, "crusher:buffer:0", "源石粉末", 1);
    let i = e.progress["crusher"];
    e.state.progress[i].phase = "completed".into();
    e.state.progress[i].recipe = Some("粉碎-源矿".into());
    e.state.progress[i].locked_recipe = Some("粉碎-源矿".into());
    e.state.progress[i].candidate_recipes = vec!["粉碎-源矿".into()];
    e.state.progress[i].remaining = Some(Time::at(0));
    e.step(true).unwrap();
    assert_eq!(count(&e, "crusher:buffer:0"), 1);
    assert_eq!(count(&e, "crusher:output:0"), 0);
    assert_eq!(e.state.progress[i].phase, "completed");
}
/// 受限转移§2.2、§3.4：身份不符断边；当前身份条件满足且其它守卫解除后恢复。
#[test]
fn identity_current_condition_restores_disconnected_channel() {
    let mut e = engine("分流器三路轮询");
    e.input.gate_settings.get_mut("probe_gate_a").unwrap()["item"] = json!("蓝铁矿");
    for _ in 0..7 {
        if e.t >= 6 {
            break;
        }
        e.step(true).unwrap();
    }
    let g = &e.state.logistics.gate_counters[e.gate_index["probe_gate_a"]];
    assert!(g.blocked_reasons.contains(&"identity_mismatch".into()));
    let incoming = "PC|probe_left:west:0|probe_gate_a:south:0";
    assert!(!e.active.contains(incoming));
    e.input.gate_settings.get_mut("probe_gate_a").unwrap()["item"] = json!("源矿");
    e.maintain_identity().unwrap();
    assert!(e.active.contains(incoming));
    let g = &e.state.logistics.gate_counters[e.gate_index["probe_gate_a"]];
    assert!(!g.blocked_reasons.contains(&"identity_mismatch".into()));
}
/// 受限转移§3.4：累计与窗口两原因并存，到期仅移除窗口。
#[test]
fn total_exhaustion_survives_window_expiry() {
    let mut e = engine("分流器三路轮询");
    e.input.gate_settings.get_mut("probe_gate_a").unwrap()["total_limit"] = q(1);
    for _ in 0..7 {
        e.step(true).unwrap();
    }
    let g = &e.state.logistics.gate_counters[e.gate_index["probe_gate_a"]];
    assert_eq!(g.blocked_reasons, vec!["total_exhausted"]);
    assert_eq!(g.window_received.integer("q").unwrap(), 0);
    assert_eq!(g.total_received.integer("q").unwrap(), 1);
}
/// 受限转移§3.4：旧游标存活即保留，否则沿旧环找存活者，新边不抢位。
#[test]
fn membership_projection() {
    let mut e = engine("分流器三路轮询");
    let i = e.side_index[&("splitter".into(), "output".into())];
    let members = e.memory.sides[i].levels[0].members.clone();
    assert_eq!(members.len(), 3);
    e.memory.sides[i].levels[0].next_channel = members[1].clone();
    e.active.remove(&members[1]);
    e.rebuild_memory().unwrap();
    assert_eq!(e.memory.sides[i].levels[0].next_channel, members[2]);
    e.active.insert(members[1].clone());
    e.rebuild_memory().unwrap();
    assert_eq!(e.memory.sides[i].levels[0].next_channel, members[2]);
}
/// 受限转移§3.1：沿路径的连续带串只计一个元件，分叉无选择则 unresolved。
#[test]
fn damping_paths_and_missing_branch() {
    let e = engine("混做粉碎机两下游");
    assert_eq!(e.damping("PC|crusher:north:0|belt_a0:south:0").unwrap(), 1);
    assert_eq!(e.damping("PC|crusher:north:2|belt_b0:south:0").unwrap(), 1);
    let mut s = engine("分流器三路轮询");
    let origin = "PC|south_box:north:2|splitter:south:0";
    let key = (
        "splitter".into(),
        s.input
            .geometry
            .channels
            .iter()
            .filter(|(_, c)| s.input.geometry.ports[&c.source_port].unit == "splitter")
            .map(|(id, _)| id.clone())
            .collect::<Vec<_>>(),
    );
    let old = s.input.branches.remove(&key).unwrap();
    assert_eq!(s.damping(origin).unwrap_err().axis, "damping.branch");
    s.input.branches.insert(key, old);
    assert_eq!(s.damping(origin).unwrap(), 1);
}
/// 受限转移§3.1：无终点不能冒充零阻尼，断边后不能沿旧图计算。
#[test]
fn damping_no_terminal() {
    let mut e = engine("混做粉碎机两下游");
    e.active.remove("PC|belt_a2:north:0|grinder_a:south:5");
    let err = e.damping("PC|crusher:north:0|belt_a0:south:0").unwrap_err();
    assert_eq!(err.status, "unresolved");
    assert_eq!(err.axis, "damping.no_terminal");
}
/// 第四轮§4.7：从80000起逐物种核算，制造完成才扣原料加产物。
#[test]
fn warehouse_80000_and_recipe_conservation() {
    let mut e = engine("混做粉碎机两下游");
    let mut expected = e.inventory_totals().unwrap();
    assert_eq!(expected["源矿"], 80000);
    for _ in 0..4 {
        let tick = e.step(true).unwrap().unwrap();
        for event in tick["events"].as_array().unwrap() {
            if event["operation"] == "manufacture_complete" {
                let uid = event["target"].as_str().unwrap();
                let rid = tick["state"]["progress"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .find(|p| p["unit"] == uid)
                    .unwrap()["recipe"]
                    .as_str()
                    .unwrap();
                let recipe = &e.input.catalog.recipes[rid];
                for (i, n) in &recipe.inputs {
                    *expected.entry(i.clone()).or_insert(0) -= n;
                }
                for (i, n) in &recipe.outputs {
                    *expected.entry(i.clone()).or_insert(0) += n;
                }
            }
        }
        expected.retain(|_, n| *n != 0);
        assert_eq!(e.inventory_totals().unwrap(), expected);
        e.validate_inventory().unwrap();
        assert!(e.usage.values().all(|n| *n <= 1));
    }
    assert_eq!(e.completed_batches, 2);
}
/// 受限转移§1：玩家拿取、离线、调试与周期提升均携带正确轴停止。
#[test]
fn external_stop_positions() {
    for (kind, axis) in [
        ("withdraw_product", "warehouse.withdrawal_timing"),
        ("offline", "offline.events"),
        ("debug_operation", "initialization.debug_actions"),
        ("unit_rebuilt", "initialization.rebuild_inventory"),
        ("build", "initialization.build_timing"),
    ] {
        let mut e = engine("混做粉碎机两下游");
        e.input.raw["timeline"]["events"]
            .as_array_mut()
            .unwrap()
            .push(json!({"id":"external_test","kind":kind,"time":tv(1)}));
        e.step(true).unwrap();
        let before = json!(e.state);
        let err = e.step(true).unwrap_err();
        assert_eq!(err.axis, axis);
        assert_eq!(err.location, "external_test");
        assert_eq!(json!(e.state), before);
    }
    let err = config()
        .request(Axis::WarehousePeriodicLift, "certify.cycle")
        .unwrap_err();
    assert_eq!(err.axis, "warehouse.periodic_lift");
}
/// 内核输出§2.1：增量逐字段重建；篡改、重复、穿数组和无变化替换拒收。
#[test]
fn checkpoint_delta_negative_cases() {
    let a = json!({"a":{"x":1,"y":[1,2]},"b":true});
    let b = json!({"a":{"x":2,"y":[3]},"b":false});
    let ops = delta(&a, &b).unwrap();
    assert_eq!(apply_delta(&a, &ops).unwrap(), b);
    let mut duplicate = ops.clone();
    duplicate.push(ops[0].clone());
    assert!(apply_delta(&a, &duplicate).is_err());
    assert!(apply_delta(
        &a,
        &[json!({"op":"replace","path":["a","y","0"],"value":9})]
    )
    .is_err());
    assert!(apply_delta(&a, &[json!({"op":"replace","path":["b"],"value":true})]).is_err());
    assert!(apply_delta(&a, &[json!({"op":"replace","path":[],"value":b})]).is_err());
}
/// 第四轮§4.8：关闭输出仍保留合法状态账，与开输出的游戏后态一致。
#[test]
fn output_off_preserves_game_state() {
    let mut a = engine("混做粉碎机两下游");
    let mut b = engine("混做粉碎机两下游");
    for _ in 0..4 {
        a.step(true).unwrap();
        b.step(false).unwrap();
        assert_eq!(a.state, b.state);
        assert!(b.records.is_empty());
    }
}
/// 内核输入§6：JSON完整边界后态可恢复，不能再次补满仓库或重复完成。
#[test]
fn after_closure_restart() {
    let mut e = engine("混做粉碎机两下游");
    e.step(true).unwrap();
    e.step(true).unwrap();
    let mut raw = e.input.raw.clone();
    raw["initial_state"]["nonwarehouse"]["value"] = json!(e.state);
    let mut resumed =
        Engine::new(Input::parse(raw, &e.input.path, &config(), false).unwrap()).unwrap();
    let next = e.step(true).unwrap().unwrap();
    let got = resumed.step(true).unwrap().unwrap();
    assert_eq!(next, got);
}
/// 内核输入§1.1：不把非法物理数值近似或溢出成整数。
#[test]
fn integer_validation() {
    assert_eq!(
        Quantity {
            value: "6/3".into(),
            category: "候选".into()
        }
        .integer("q")
        .unwrap(),
        2
    );
    assert!(Quantity {
        value: "1/2".into(),
        category: "候选".into()
    }
    .integer("q")
    .is_err());
    assert!(Quantity {
        value: "1/0".into(),
        category: "候选".into()
    }
    .integer("q")
    .is_err());
    assert_eq!(add(i64::MAX, 1, "q").unwrap_err().status, "inconclusive");
}
/// 受限转移§1：未完成中途扫描不冒充边界，缺轴或参数偷改拒收。
#[test]
fn seed_and_parameter_negatives() {
    let e = engine("混做粉碎机两下游");
    let mut premature = e.input.raw.clone();
    let seed = &mut premature["initial_state"]["nonwarehouse"]["value"];
    seed["environment"]["time"] = tv(-1);
    seed["semantic_context"]["judgment_context"]["value"]["instant"] = tv(-1);
    seed["semantic_context"]["tick_context"]["value"]["window_start"] = tv(-1);
    seed["semantic_context"]["tick_context"]["value"]["window_end"] = tv(0);
    assert_eq!(
        Engine::new(Input::parse(premature, &e.input.path, &config(), false).unwrap())
            .unwrap_err()
            .location,
        "StateSeed.environment.time"
    );
    let mut alias = e.input.raw.clone();
    alias["timeline"]["events"]
        .as_array_mut()
        .unwrap()
        .push(json!({"id":"C|2|crusher","kind":"runtime","time":tv(2)}));
    assert_eq!(
        Input::parse(alias, &e.input.path, &config(), false)
            .and_then(Engine::new)
            .unwrap_err()
            .location,
        "timeline.events.C|2|crusher"
    );

    let mut raw = e.input.raw.clone();
    raw["initial_state"]["nonwarehouse"]["value"]["semantic_context"]["judgment_context"]
        ["value"]["phase"] = json!("in_closure");
    let err = Engine::new(Input::parse(raw, &e.input.path, &config(), false).unwrap()).unwrap_err();
    assert_eq!(err.status, "unsupported");
    let mut raw = e.input.raw.clone();
    set_axis(
        &mut raw,
        "judgment.order",
        json!({"schema":"event-order-v2"}),
    );
    assert_eq!(
        Input::parse(raw, &e.input.path, &config(), false)
            .unwrap_err()
            .axis,
        "judgment.order"
    );
    let mut raw = e.input.raw.clone();
    raw["parameters"]["fixedness_unproven"]
        .as_object_mut()
        .unwrap()
        .remove("time.domain");
    assert!(Input::parse(raw, &e.input.path, &config(), false).is_err());
}
/// 受限转移§2.1：外部历史未覆盖后续时刻时停止，禁止沿用一个短前缀。
#[test]
fn ore_history_horizon_stop() {
    let mut e = engine("混做粉碎机两下游");
    for _ in 0..4 {
        e.step(false).unwrap();
    }
    assert_eq!(e.step(false).unwrap_err().axis, "warehouse.external_supply");
}
/// 内核输出§2.1、§3：两格式完整字段同值，末残段篡改即使能解码也不能通过重算。
#[test]
fn full_and_delta_record_recompute() {
    let path = root().join("规格/内核配置-v1.json");
    let full = run_record(
        engine("混做粉碎机两下游"),
        &config(),
        &path,
        4,
        "full_state_each_instant",
        3,
    )
    .unwrap();
    let delta = run_record(
        engine("混做粉碎机两下游"),
        &config(),
        &path,
        4,
        "checkpoint_delta",
        3,
    )
    .unwrap();
    let mut expanded = delta.clone();
    expanded["trace"] = decode_trace(&delta["trace"]).unwrap();
    assert_eq!(expanded, full);
    verify_record(&delta, engine("混做粉碎机两下游").input, &config(), &path).unwrap();
    let mut tampered = delta;
    tampered["trace"]["ticks"][3]["state"]["inventory"][0]["contents"] = json!([]);
    tampered["trace"]["ticks"][3]["summary"]["warehouse_ore"] = json!("123");
    assert!(verify_record(
        &tampered,
        engine("混做粉碎机两下游").input,
        &config(),
        &path
    )
    .is_err());
}
/// 受限转移§2.1：真实补矿记录按输入历史办理，补给不混入交付账。
#[test]
fn explicit_ore_supply() {
    let e = engine("混做粉碎机两下游");
    let mut raw = e.input.raw.clone();
    let mut supply =
        raw["parameters"]["fixedness_unproven"]["warehouse.external_supply"]["value"].clone();
    supply["events"] = json!([{"event":"ore_refill","time":tv(1),"item":"源矿","quantity":q(1)}]);
    set_axis(&mut raw, "warehouse.external_supply", supply);
    raw["timeline"]["events"]
        .as_array_mut()
        .unwrap()
        .push(json!({"id":"ore_refill","kind":"runtime","time":tv(1)}));
    let mut e = Engine::new(Input::parse(raw, &e.input.path, &config(), false).unwrap()).unwrap();
    e.step(true).unwrap();
    let tick = e.step(true).unwrap().unwrap();
    assert_eq!(e.supplied["源矿"], 1);
    assert!(e.delivery.is_empty());
    assert_eq!(tick["events"][0]["operation"], "ore_supply");
    assert_eq!(
        e.state.warehouse.slots[e.warehouse["warehouse_0"]]
            .quantity
            .integer("q")
            .unwrap(),
        79999
    );
}
/// 内核输入§6：重复/遗漏格、仓库冒名、错误容量及参数当前值均拒收。
#[test]
fn malformed_state_rejected() {
    let e = engine("混做粉碎机两下游");
    for case in 0..6 {
        let mut raw = e.input.raw.clone();
        let state = &mut raw["initial_state"]["nonwarehouse"]["value"];
        match case {
            0 => {
                state["inventory"].as_array_mut().unwrap().pop();
            }
            1 => {
                let first = state["inventory"][0].clone();
                state["inventory"].as_array_mut().unwrap().push(first);
            }
            2 => state["warehouse"]["slots"][0]["slot"] = json!("crusher:input:0"),
            3 => state["warehouse"]["slots"][0]["quantity"] = q(80001),
            4 => state["semantic_context"]["parameter_values"][0]["lifetime"] = json!("X"),
            _ => {
                state["semantic_context"]["arbitration"]["warehouse_empty_slot_order"] =
                    json!(["warehouse_0"])
            }
        }
        let result = Input::parse(raw, &e.input.path, &config(), false).and_then(Engine::new);
        assert!(result.is_err(), "case {case}");
    }
}
/// 受限转移§4.1：物种不兼容的运输格是容量失败原因，不能误报无目标格。
#[test]
fn transport_wrong_item_rejects() {
    let mut e = engine("混做粉碎机两下游");
    put(&mut e, "feed_belt:transport:0", "蓝铁矿", 1);
    let (_, reason) = e
        .physical("PC|ore_source:north:1|feed_belt:south:0")
        .unwrap();
    assert_eq!(reason, "target_capacity");
}
/// 第四轮§4.7：独立布局都从公开装载入口进入，几何和目录属性不由测试绕过。
fn fixture(name: &str) -> Engine {
    let path =
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(format!("tests/fixtures/{name}.json"));
    Engine::new(Input::load(&path, &config(), false).unwrap()).unwrap()
}
/// 内核输入§6：显式库存试验再次经 JSON 完整种子装载，验证当前级和缓存约束。
fn reload(mut e: Engine) -> Engine {
    e.refresh().unwrap();
    e.state.logistics.poll_memory.value = json!(e.memory);
    let mut raw = e.input.raw.clone();
    raw["initial_state"]["nonwarehouse"]["value"] = json!(e.state);
    Engine::new(Input::parse(raw, &e.input.path, &config(), false).unwrap()).unwrap()
}
/// 受限转移§3.1、§4.1：桥的双轴各自滞留，物品不换轴，整体存取侧仍共享调度。
#[test]
fn bridge_two_independent_slots_run() {
    let mut e = fixture("bridge");
    put(&mut e, "south_box:storage:0", "源矿", 1);
    put(&mut e, "west_box:storage:0", "蓝铁矿", 1);
    let mut e = reload(e);
    let total = e.inventory_totals().unwrap();
    e.step(true).unwrap();
    assert_eq!(count(&e, "bridge:vertical:0"), 1);
    assert_eq!(count(&e, "bridge:horizontal:0"), 1);
    assert_eq!(count(&e, "north_box:storage:0"), 0);
    assert_eq!(count(&e, "east_box:storage:0"), 0);
    e.step(true).unwrap();
    assert_eq!(
        e.state.inventory[e.inv["north_box:storage:0"]].contents[0].item,
        "源矿"
    );
    assert_eq!(
        e.state.inventory[e.inv["east_box:storage:0"]].contents[0].item,
        "蓝铁矿"
    );
    assert_eq!(e.inventory_totals().unwrap(), total);
}
/// R13桥例外、R23滞留：同种双轴同时占格、各自每tick一件，完整种子可恢复。
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
}
/// 受限转移§3.1：取货级先比较最大阻尼；较早接通的直连汇流器级仍输给较小阻尼。
#[test]
fn output_level_damping_priority() {
    let mut e = fixture("priority");
    put(&mut e, "source:storage:0", "源矿", 2);
    let mut e = reload(e);
    let direct = "PC|source:north:0|merger:south:0";
    let other = "PC|source:north:2|belt_1:south:0";
    assert_eq!(e.damping(direct).unwrap(), 2);
    assert_eq!(e.damping(other).unwrap(), 1);
    assert!(e.input.connection_times[direct] < e.input.connection_times[other]);
    let s = &e.memory.sides[e.side_index[&("source".into(), "output".into())]];
    assert_eq!(s.current_level.as_deref(), Some("L|source|output|other"));
    let tick = e.step(true).unwrap().unwrap();
    let first = tick["events"]
        .as_array()
        .unwrap()
        .iter()
        .find(|r| r["operation"] == "move" && r["outcome"] == "success")
        .unwrap();
    assert_eq!(first["target"], other);
}
/// 受限转移§4.1、§3.3：核心 PC 入库沿真实物理路径；预算/交付与库存同时提交。
#[test]
fn core_inbound_physical_deposit() {
    let mut e = fixture("core_inbound");
    put(&mut e, "box:storage:0", "高容谷地电池", 2);
    let mut e = reload(e);
    let total = e.inventory_totals().unwrap();
    e.step(true).unwrap();
    assert!(e.delivery.is_empty());
    e.step(true).unwrap();
    assert_eq!(e.delivery["高容谷地电池"], 1);
    assert_eq!(e.inventory_totals().unwrap(), total);
    assert_eq!(e.usage["core:south:1"], 1);
}
/// 受限转移§3.1：正式级键平局时独立 level_order 改变胜者，接通顺序仍原样。
#[test]
fn level_tie_reversal_changes_winner() {
    let mut normal = engine("分流器三路轮询");
    let mut raw = normal.input.raw.clone();
    raw["initial_state"]["nonwarehouse"]["value"]["semantic_context"]["arbitration"]["level_order"]
        .as_array_mut()
        .unwrap()
        .reverse();
    let mut reversed =
        Engine::new(Input::parse(raw, &normal.input.path, &config(), false).unwrap()).unwrap();
    for _ in 0..2 {
        normal.step(true).unwrap();
        reversed.step(true).unwrap();
    }
    let a = normal.step(true).unwrap().unwrap();
    let b = reversed.step(true).unwrap().unwrap();
    let winning = |t: &Value| {
        t["events"]
            .as_array()
            .unwrap()
            .iter()
            .find(|r| {
                r["operation"] == "move"
                    && r["outcome"] == "success"
                    && r["target"].as_str().unwrap().contains("|probe_merger:")
            })
            .unwrap()["target"]
            .clone()
    };
    assert_ne!(winning(&a), winning(&b));
    assert_eq!(
        normal.input.connection_times,
        reversed.input.connection_times
    );
}
/// 受限转移§3.4：整环一次恢复才执行 second_cursor，新环不受逐边遍历顺序控制。
#[test]
fn simultaneous_ring_restoration() {
    let mut e = engine("分流器三路轮询");
    let i = e.side_index[&("splitter".into(), "output".into())];
    let members = e.memory.sides[i].levels[0].members.clone();
    for c in &members {
        e.active.remove(c);
    }
    e.rebuild_memory().unwrap();
    assert!(e.memory.sides[i].levels.is_empty());
    for c in members.iter().rev() {
        e.active.insert(c.clone());
    }
    e.rebuild_memory().unwrap();
    assert_eq!(e.memory.sides[i].levels[0].next_channel, members[1]);
}
/// 受限转移§2.1：有电冷却减一，关闭传输后暂停，不受仓库移动影响。
#[test]
fn transfer_cooldown_pause() {
    let mut e = engine("分流器三路轮询");
    let i = e.progress["south_box"];
    e.state.progress[i].cooldowns[0].remaining = Time::at(4);
    e.step(true).unwrap();
    e.step(true).unwrap();
    assert_eq!(
        e.state.progress[i].cooldowns[0]
            .remaining
            .integer("q")
            .unwrap(),
        4
    );
    e.input
        .switches
        .insert(("south_box".into(), "transfer".into()), true);
    e.step(true).unwrap();
    assert_eq!(
        e.state.progress[i].cooldowns[0]
            .remaining
            .integer("q")
            .unwrap(),
        3
    );
}
/// 受限转移§2.1、§4.2：五tick配方按实际工作量完成，不能在同刻子动作链压零。
#[test]
fn five_tick_recipe_completes_only_at_boundary() {
    let original = engine("混做粉碎机两下游");
    let mut raw = original.input.raw.clone();
    for unit in raw["layout"]["units"].as_array_mut().unwrap() {
        if unit["id"] == "grinder_a" {
            unit["kind"] = json!("封装机");
        }
    }
    for moment in raw["construction"]["moments"].as_array_mut().unwrap() {
        if moment["unit"] == "grinder_a" {
            moment["placement"]["kind"] = json!("封装机");
        }
    }
    let mut supply = original
        .input
        .parameters
        .value(Axis::WarehouseExternalSupply)
        .unwrap()
        .clone();
    supply["through"] = tv(6);
    set_axis(&mut raw, "warehouse.external_supply", supply);
    let mut e =
        Engine::new(Input::parse(raw, &original.input.path, &config(), false).unwrap()).unwrap();
    let recipe = e.input.catalog.recipes["封装-电池"].clone();
    for (i, (item, n)) in recipe.inputs.iter().enumerate() {
        put(&mut e, &format!("grinder_a:input:{i}"), item, *n);
    }
    let mut e = reload(e);
    for t in 0..5 {
        let tick = e.step(true).unwrap().unwrap();
        assert!(
            !tick["events"]
                .as_array()
                .unwrap()
                .iter()
                .any(|r| r["operation"] == "manufacture_complete" && r["target"] == "grinder_a"),
            "t={t}"
        );
    }
    let last = e.step(true).unwrap().unwrap();
    assert!(last["events"]
        .as_array()
        .unwrap()
        .iter()
        .any(|r| r["event"] == "C|5|grinder_a"));
    assert_eq!(
        e.state.inventory[e.inv["grinder_a:output:0"]].contents[0].item,
        "高容谷地电池"
    );
}
/// 内核输出§1：五态报告既覆盖99轴，也不把被关闭的传输说成执行。
#[test]
fn coverage_five_states() {
    let mut e = engine("分流器三路轮询");
    let mut ticks = Vec::new();
    for _ in 0..12 {
        ticks.push(e.step(true).unwrap().unwrap());
    }
    let rows = coverage(&config(), &ticks, &e.input);
    let statuses: std::collections::BTreeSet<_> = rows
        .iter()
        .map(|r| r["coverage_status"].as_str().unwrap())
        .collect();
    assert_eq!(
        statuses,
        std::collections::BTreeSet::from([
            "exercised",
            "input_checked",
            "not_exercised",
            "stop_not_triggered",
            "proof_pending"
        ])
    );
    assert_eq!(
        rows.iter()
            .find(|r| r["axis"] == "transfer.cooldown_scope")
            .unwrap()["coverage_status"],
        "not_exercised"
    );
    assert_eq!(
        rows.iter()
            .find(|r| r["axis"] == "gate.concurrent_expiry")
            .unwrap()["coverage_status"],
        "exercised"
    );
}
/// 受限转移§1：两个显式步进入口严格区分边界前与已闭包锚点。
#[test]
fn explicit_step_anchors() {
    let mut e = engine("混做粉碎机两下游");
    assert!(e.step_tick(true).is_err());
    assert_eq!(e.step_instant(true).unwrap().unwrap()["time"], tv(0));
    assert!(e.step_instant(true).is_err());
    assert_eq!(e.step_tick(true).unwrap().unwrap()["time"], tv(1));
}
/// 受限转移§1、§5.2：资源停止实例不能继续推进并把部分工作冒充新后继。
#[test]
fn stopped_engine_cannot_continue() {
    let mut e = engine("混做粉碎机两下游");
    e.max_sweeps = 0;
    let stop = e.step(true).unwrap_err();
    let state = e.state.clone();
    e.max_sweeps = 1000;
    assert_eq!(e.step(true).unwrap_err(), stop);
    assert_eq!(e.state, state);
}

#[path = "tests_revision_r5.rs"]
mod revision_r5;
#[path = "tests_round6.rs"]
mod round6;
