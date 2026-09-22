//! 第1轮修订：存活发现的公开入口负例、有效对照及独立记录验收。
use super::*;
use crate::event_identity::validate_event_identity;

/// 内核输入§1：各变异仍经过公开解析入口。
fn parse(raw: Value, e: &Engine) -> Result<Input> {
    Input::parse(raw, &e.input.path, &config(), false)
}
/// 内核输入§5.4：补给与统一时间线同域登记。
fn supply(raw: &mut Value, rows: Value) {
    let mut value =
        raw["parameters"]["fixedness_unproven"]["warehouse.external_supply"]["value"].clone();
    value["events"] = rows.clone();
    set_axis(raw, "warehouse.external_supply", value);
    for row in rows.as_array().unwrap() {
        raw["timeline"]["events"]
            .as_array_mut()
            .unwrap()
            .push(json!({"id":row["event"],"kind":"runtime","time":row["time"]}));
    }
}
/// KR-r1-L3-01；输入§2：各类非对象成员均返回准确位置，不发生索引panic。
#[test]
fn revision_snapshot_objects() {
    let e = engine("混做粉碎机两下游");
    for value in [
        json!(false),
        json!(null),
        json!(7),
        json!("snapshot"),
        json!([]),
        json!({}),
    ] {
        let mut raw = e.input.raw.clone();
        raw["layout"]["snapshots"] = json!([value]);
        let stop = parse(raw, &e).unwrap_err();
        assert_eq!(stop.status, "invalid_input");
        assert_eq!(stop.location, "layout.snapshots[0]");
    }
    let mut raw = e.input.raw.clone();
    let mut snapshot = raw["layout"].clone();
    for key in ["base", "post_debug", "snapshots"] {
        snapshot.as_object_mut().unwrap().remove(key);
    }
    snapshot["id"] = json!("snapshot_control");
    raw["layout"]["snapshots"] = json!([snapshot]);
    parse(raw, &e).unwrap();
}
/// KR-r1-L3-02；输入§4：门身份须为目录物品名或null，限额仍单独检查。
#[test]
fn revision_gate_item_domain() {
    let e = engine("分流器三路轮询");
    for value in [
        json!(7),
        json!(false),
        json!(""),
        json!("不存在的物品"),
        json!({}),
    ] {
        let mut raw = e.input.raw.clone();
        raw["settings"]["gates"][0]["item"] = value;
        assert_eq!(
            parse(raw, &e).unwrap_err().location,
            "settings.gates[0].item"
        );
    }
    let mut raw = e.input.raw.clone();
    for key in ["item", "total_limit", "window_limit"] {
        raw["settings"]["gates"][0][key] = Value::Null;
    }
    parse(raw, &e).unwrap();
}
/// KR-r1-L3-03；输入§2.3、§6：任务初始格同样先核唯一标签和保留域。
#[test]
fn revision_initial_warehouse_labels() {
    let e = engine("混做粉碎机两下游");
    for label in [
        json!(""),
        json!("warehouse_0"),
        json!("crusher:buffer:0"),
        json!("phantom:input:1"),
        json!(7),
    ] {
        let mut raw = e.input.raw.clone();
        raw["initial_state"]["warehouse"]["slots"][1]["slot"] = label;
        assert_eq!(
            parse(raw, &e).unwrap_err().location,
            "initial_state.warehouse.slots[1].slot"
        );
    }
}
/// KR-r1-L1-01/L2-01；转移§2.1：空史及迟到补给不能让耗矿前缀冒称完成。
#[test]
fn revision_ore_history_sufficiency() {
    let e = fixture("benchmark_1000");
    for delayed in [false, true] {
        let mut raw = e.input.raw.clone();
        raw["initial_state"]["nonwarehouse"]["value"]["warehouse"]["slots"][0]["quantity"] = q(2);
        if delayed {
            supply(
                &mut raw,
                json!([{"event":"late_supply","time":tv(2),"item":"源矿","quantity":q(5)}]),
            );
        }
        let rec = run_record(
            Engine::new(parse(raw, &e).unwrap()).unwrap(),
            &config(),
            &root().join("规格/内核配置-v1.json"),
            4,
            "full_state_each_instant",
            2,
        )
        .unwrap();
        assert_eq!(rec["status"], "invalid_input");
        assert_eq!(rec["trace"]["ticks"].as_array().unwrap().len(), 1);
        assert!(rec["open_items"]
            .to_string()
            .contains("warehouse.external_supply"));
    }
    let mut raw = e.input.raw.clone();
    raw["initial_state"]["nonwarehouse"]["value"]["warehouse"]["slots"][0]["quantity"] = q(2);
    supply(
        &mut raw,
        json!([{"event":"early_supply","time":tv(1),"item":"源矿","quantity":q(4)}]),
    );
    let mut control = Engine::new(parse(raw, &e).unwrap()).unwrap();
    control.run_without_output(4).unwrap();
    assert_eq!(control.supplied["源矿"], 4);
}
/// KR-r1-L1-01；转移§2.1：最后一件出库在提交前停止；另一矿无货同样拒绝。
#[test]
fn revision_ore_depletion_is_not_a_movement_guard() {
    let mut e = engine("混做粉碎机两下游");
    e.state.warehouse.slots[0].quantity = Quantity::calc(1);
    let stop = e.step(true).unwrap_err();
    assert_eq!(stop.location.split(':').next(), Some("J|0|0|0"));
    assert_eq!(count(&e, "feed_belt:transport:0"), 0);
    assert_eq!(e.state.warehouse.slots[0].quantity.value, "1");
    let mut e = engine("混做粉碎机两下游");
    let slot = e
        .state
        .warehouse
        .slots
        .iter()
        .find(|row| row.item.as_deref() == Some("蓝铁矿"))
        .unwrap()
        .slot
        .clone();
    e.remove(&slot, "蓝铁矿", 80000).unwrap();
    let stop = e.step(true).unwrap_err();
    assert!(stop.reason.contains("蓝铁矿"));
}
/// KR-r1-L1-02；输入§3.1：补矿数组与显式关系合图，间接矛盾同样拒收。
#[test]
fn revision_supply_order_intersection() {
    let e = engine("混做粉碎机两下游");
    let mut raw = e.input.raw.clone();
    raw["initial_state"]["nonwarehouse"]["value"]["warehouse"]["slots"][0]["quantity"] = q(100);
    supply(
        &mut raw,
        json!([
        {"event":"supply_a","time":tv(0),"item":"源矿","quantity":q(1)},
        {"event":"supply_b","time":tv(0),"item":"源矿","quantity":q(1)}]),
    );
    for indirect in [false, true] {
        let mut bad = raw.clone();
        let mut pairs = vec![("supply_b", "supply_a")];
        if indirect {
            bad["timeline"]["events"]
                .as_array_mut()
                .unwrap()
                .push(json!({"id":"pivot","kind":"runtime","time":tv(0)}));
            pairs = vec![("supply_b", "pivot"), ("pivot", "supply_a")];
        }
        for (a, b) in pairs {
            bad["timeline"]["relations"]
                .as_array_mut()
                .unwrap()
                .push(json!({"before":a,"after":b,"relation":"occurs_before","basis":["回归"]}));
        }
        assert!(parse(bad, &e).unwrap_err().reason.contains("环"));
    }
    raw["timeline"]["relations"].as_array_mut().unwrap().push(json!({"before":"supply_b","after":"supply_a","relation":"same_time","basis":["同刻不指定先后"]}));
    let mut control = Engine::new(parse(raw, &e).unwrap()).unwrap();
    let tick = control.step(true).unwrap().unwrap();
    assert_eq!(tick["events"][0]["event"], "supply_a");
    assert_eq!(tick["events"][1]["event"], "supply_b");
}
/// KR-r1-L1-04；输入§3.3：错误类型、悬空和重复动作引用不能被忽略。
#[test]
fn revision_external_action_references() {
    let e = engine("混做粉碎机两下游");
    for (key, kind, row, axis) in [
        (
            "offline",
            "offline",
            json!({"event":"external","new_connection_order":Decision::specified(json!([]),"回归"),"effects":{}}),
            "offline.events",
        ),
        (
            "product_withdrawal",
            "withdraw_product",
            json!({"event":"external","rule":null,"action":{"item":"高容谷地电池","slot":"product","quantity":q(0)}}),
            "warehouse.withdrawal_timing",
        ),
    ] {
        let mut raw = e.input.raw.clone();
        raw["timeline"]["events"]
            .as_array_mut()
            .unwrap()
            .push(json!({"id":"external","kind":"runtime","time":tv(1)}));
        raw["environment"][key]["selected_events"] = json!([row.clone()]);
        assert!(parse(raw.clone(), &e)
            .unwrap_err()
            .location
            .contains("selected_events[0].event"));
        raw["timeline"]["events"]
            .as_array_mut()
            .unwrap()
            .last_mut()
            .unwrap()["kind"] = json!(kind);
        let mut control = Engine::new(parse(raw.clone(), &e).unwrap()).unwrap();
        control.step(true).unwrap();
        assert_eq!(control.step(true).unwrap_err().axis, axis);
        raw["environment"][key]["selected_events"] = json!([row.clone(), row]);
        assert!(parse(raw, &e).is_err());
    }
}
/// KR-r1-L1-03；输入§3.1：已注册runtime可以恢复，历史建造和异刻runtime不可以。
#[test]
fn revision_pending_history_alias() {
    let mut e = engine("混做粉碎机两下游");
    e.step(true).unwrap();
    e.step(true).unwrap();
    let mut raw = e.input.raw.clone();
    raw["initial_state"]["nonwarehouse"]["value"] = json!(e.state);
    for kind in ["build", "runtime"] {
        let mut bad = raw.clone();
        let id = if kind == "build" {
            "build_0"
        } else {
            "registered_completion"
        };
        bad["initial_state"]["nonwarehouse"]["value"]["semantic_context"]["pending_events"]
            ["value"][0]["event"] = json!(id);
        if kind == "runtime" {
            bad["timeline"]["events"]
                .as_array_mut()
                .unwrap()
                .push(json!({"id":id,"kind":"runtime","time":tv(3)}));
        }
        assert!(parse(bad, &e).and_then(Engine::new).is_err());
    }
    raw["timeline"]["events"]
        .as_array_mut()
        .unwrap()
        .push(json!({"id":"C|2|crusher","kind":"runtime","time":tv(2)}));
    let mut control = Engine::new(parse(raw, &e).unwrap()).unwrap();
    assert_eq!(
        control.step(true).unwrap().unwrap()["events"][0]["event"],
        "C|2|crusher"
    );
}
/// KR-r1-L1-03；输出§2–§3：独立验收不依赖重算相等，拒绝历史别名、消失、改用、重复和已办待办。
#[test]
fn revision_independent_identity_audit() {
    let mut e = engine("混做粉碎机两下游");
    let start = json!(e.state);
    let ticks: Vec<_> = (0..4).map(|_| e.step(true).unwrap().unwrap()).collect();
    validate_event_identity(&e.input, &start, &ticks).unwrap();
    for variant in 0..5 {
        let mut bad = ticks.clone();
        match variant {
            0 => {
                bad[1]["state"]["semantic_context"]["pending_events"]["value"][0]["event"] =
                    json!("build_0");
            }
            1 => {
                bad[2]["events"][0]["target"] = json!("refiner");
            }
            2 => {
                bad[2]["events"].as_array_mut().unwrap().remove(0);
            }
            3 => {
                bad[2]["events"][0] = bad[0]["events"][0].clone();
            }
            _ => {
                let pending =
                    bad[1]["state"]["semantic_context"]["pending_events"]["value"][0].clone();
                bad[2]["state"]["semantic_context"]["pending_events"]["value"]
                    .as_array_mut()
                    .unwrap()
                    .push(pending);
            }
        }
        assert!(
            validate_event_identity(&e.input, &start, &bad).is_err(),
            "变异{variant}"
        );
    }
}
/// KR-r1-L1-05；输入§5.3：合法分支有对照，无关查询、终点外和断开的表项拒收。
#[test]
fn revision_branch_relevance() {
    let e = engine("分流器三路轮询");
    let mut raw = e.input.raw.clone();
    Engine::new(parse(raw.clone(), &e).unwrap()).unwrap();
    let mut branch = raw["parameters"]["fixedness_unproven"]["damping.branch"]["value"].clone();
    branch["choices"][0]["outgoing_channel"] = json!("PC|probe_left:west:0|probe_gate_a:south:0");
    set_axis(&mut raw, "damping.branch", branch);
    assert!(parse(raw, &e).is_err());
}
/// KR-r1-L2-03；输出§1、转移§4.2：仅归集开工不能证明输出分支，blocked种子必须给真实判定证据。
#[test]
fn revision_manufacturing_axis_evidence() {
    let mut e = engine("混做粉碎机两下游");
    let mut ticks: Vec<_> = (0..2).map(|_| e.step(true).unwrap().unwrap()).collect();
    let rows = coverage(&config(), &ticks, &e.input);
    assert_eq!(
        rows.iter()
            .find(|r| r["axis"] == "manufacturing.output_blocked")
            .unwrap()["coverage_status"],
        "not_exercised"
    );
    ticks.push(e.step(true).unwrap().unwrap());
    let rows = coverage(&config(), &ticks, &e.input);
    let evidence = &rows
        .iter()
        .find(|r| r["axis"] == "manufacturing.output_blocked")
        .unwrap()["evidence"];
    assert!(evidence
        .as_array()
        .unwrap()
        .iter()
        .all(|id| id.as_str().unwrap().starts_with("J|2|")));
    let mut blocked = engine("混做粉碎机两下游");
    put(&mut blocked, "crusher:input:0", "源石粉末", 1);
    put(&mut blocked, "crusher:buffer:0", "源石粉末", 1);
    let index = blocked.progress["crusher"];
    let p = &mut blocked.state.progress[index];
    p.phase = "completed".into();
    p.recipe = Some("粉碎-源矿".into());
    p.locked_recipe = p.recipe.clone();
    p.candidate_recipes = vec!["粉碎-源矿".into()];
    p.remaining = Some(Time::at(0));
    let mut blocked = reload(blocked);
    let tick = blocked.step(true).unwrap().unwrap();
    let rows = coverage(&config(), std::slice::from_ref(&tick), &blocked.input);
    let row = rows
        .iter()
        .find(|r| r["axis"] == "manufacturing.output_blocked")
        .unwrap();
    assert_eq!(row["coverage_status"], "exercised");
    for id in row["evidence"].as_array().unwrap() {
        assert!(tick["events"]
            .as_array()
            .unwrap()
            .iter()
            .any(|e| e["event"] == *id && e["outcome"] == "guard_false"));
    }
}
/// KR-r1-L1-06；受限模型§2：容量与途径互不替代，箱开关与真实核心PC各有对照。
#[test]
fn revision_warehouse_acceptance() {
    let e = engine("混做粉碎机两下游");
    let report = e.acceptance_report().unwrap();
    assert_eq!(report["products"][0]["capacity_available"], true);
    assert_eq!(report["products"][0]["physical_path_exists"], false);
    let mut e = fixture("core_inbound");
    e.deposit(BTreeMap::from([("高容谷地电池".into(), 80000)]))
        .unwrap();
    let report = e.acceptance_report().unwrap();
    assert_eq!(report["products"][0]["capacity_available"], false);
    assert_eq!(report["products"][0]["physical_path_exists"], true);
    assert_eq!(report["products"][1]["capacity_available"], true);
    assert_eq!(report["both_products_capacity_and_path"], false);
    let mut e = engine("分流器三路轮询");
    assert_eq!(
        e.acceptance_report().unwrap()["enabled_transfer_units"],
        json!([])
    );
    e.input
        .switches
        .insert(("north_box".into(), "transfer".into()), true);
    assert_eq!(
        e.acceptance_report().unwrap()["enabled_transfer_units"],
        json!(["north_box"])
    );
}
/// KR-r1-L1-06/07；输出§1–§2：双格式报告逐刻齐全；矛盾的已闭包起点只停止输出，步进仍有效。
#[test]
fn revision_reports_and_after_closure_stop() {
    let path = root().join("规格/内核配置-v1.json");
    for format in ["full_state_each_instant", "checkpoint_delta"] {
        let r = run_record(engine("混做粉碎机两下游"), &config(), &path, 4, format, 3).unwrap();
        for axis in ["warehouse.acceptance", "warehouse.acceptance_quantifier"] {
            let evidence = r["uncovered_axes"]
                .as_array()
                .unwrap()
                .iter()
                .find(|r| r["axis"] == axis)
                .unwrap()["evidence"]
                .as_array()
                .unwrap();
            assert_eq!(evidence.len(), 4);
            for (i, entry) in evidence.iter().enumerate() {
                let report: Value = serde_json::from_str(entry.as_str().unwrap()).unwrap();
                assert_eq!(report["time"], tv(i as i64));
            }
        }
        let mut e = engine("混做粉碎机两下游");
        e.step(true).unwrap();
        let record = run_record(e, &config(), &path, 1, format, 3).unwrap();
        assert_eq!(record["status"], "completed");
        assert_eq!(record["trace"]["start_state"]["environment"]["time"], tv(0));
        assert_eq!(record["trace"]["ticks"][0]["time"], tv(1));
    }
}
