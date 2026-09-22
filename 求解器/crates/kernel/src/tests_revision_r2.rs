//! 第2轮修订：全局时序、恢复闭合、强类型输入与整份输出的存活发现回归。
use super::*;
use crate::event_identity::{seed_executed, validate_event_identity};

/// 内核输入§1：所有输入变异均经过公开装载与完整种子校验。
fn load(raw: Value, path: &std::path::Path) -> Result<Engine> {
    Input::parse(raw, path, &config(), false).and_then(Engine::new)
}
/// 内核输入§3.1：保存拥有关系不变，只加入欲核验的历史偏序。
fn relation(raw: &mut Value, before: &str, after: &str, kind: &str) {
    raw["timeline"]["relations"]
        .as_array_mut()
        .unwrap()
        .push(json!({
        "before":before,"after":after,"relation":kind,"basis":["第2轮回归：显式事件关系"]}));
}
/// KR-r2-L1-01；转移§2.1、输入§3.1：固定阶段与直接/传递关系取交集，保留合法及same_time对照。
#[test]
fn revision_r2_phase_intersection() {
    let original = fixture("revision_r2_phase_control");
    let path = original.input.path.clone();
    let mut raw = original.input.raw.clone();
    raw["timeline"]["relations"]
        .as_array_mut()
        .unwrap()
        .retain(|r| r["before"] != "completion_probe");
    for kind in ["occurs_before", "same_time"] {
        let mut control = raw.clone();
        relation(&mut control, "completion_probe", "supply_probe", kind);
        let mut e = load(control, &path).unwrap();
        let start = json!(e.state);
        let ticks = vec![
            e.step(true).unwrap().unwrap(),
            e.step(true).unwrap().unwrap(),
        ];
        assert_eq!(ticks[1]["events"][0]["event"], "completion_probe");
        assert_eq!(ticks[1]["events"][1]["event"], "supply_probe");
        validate_event_identity(&e.input, &start, &ticks).unwrap();
        let mut bad = ticks;
        bad[1]["events"].as_array_mut().unwrap().swap(0, 1);
        assert!(validate_event_identity(&e.input, &start, &bad).is_err());
    }
    for indirect in [false, true] {
        let mut bad = raw.clone();
        if indirect {
            let mut supply = bad["parameters"]["fixedness_unproven"]["warehouse.external_supply"]
                ["value"]
                .clone();
            supply["events"]
                .as_array_mut()
                .unwrap()
                .push(json!({"event":"pivot","time":tv(1),"item":"源矿","quantity":q(1)}));
            set_axis(&mut bad, "warehouse.external_supply", supply);
            bad["timeline"]["events"]
                .as_array_mut()
                .unwrap()
                .push(json!({"id":"pivot","kind":"runtime","time":tv(1)}));
            relation(&mut bad, "supply_probe", "pivot", "occurs_before");
            relation(&mut bad, "pivot", "completion_probe", "occurs_before");
        } else {
            relation(
                &mut bad,
                "supply_probe",
                "completion_probe",
                "occurs_before",
            );
        }
        let stop = load(bad, &path).unwrap_err();
        assert_eq!(stop.status, "invalid_input");
        assert_eq!(stop.location, "timeline.relations");
    }
}
/// KR-r2-L1-02；输入§5.3、转移§3.4：失活前停止，固定表及库存不改；合法完整后态原参数重载。
#[test]
fn revision_r2_fixed_branch_cut_and_reload() {
    let mut e = fixture("revision_r2_branch_cut");
    let query = "PC|source:north:0|merge_a:south:0";
    assert_eq!(e.damping(query).unwrap(), 3);
    e.step(true).unwrap();
    assert_eq!(e.damping(query).unwrap(), 2);
    let mut raw = e.input.raw.clone();
    raw["settings"]["gates"][0]["total_limit"] = Value::Null;
    let mut control = load(raw, &e.input.path).unwrap();
    control.step(true).unwrap();
    assert_eq!(control.damping(query).unwrap(), 3);
    let mut resumed = control.input.raw.clone();
    resumed["initial_state"]["nonwarehouse"]["value"] = json!(control.state);
    let mut resumed = load(resumed, &control.input.path).unwrap();
    assert_eq!(resumed.damping(query).unwrap(), 3);
    assert_eq!(control.step(true).unwrap(), resumed.step(true).unwrap());
    let path = root().join("规格/内核配置-v1.json");
    let record = run_record(
        fixture("revision_r2_branch_cut"),
        &config(),
        &path,
        1,
        "full_state_each_instant",
        1,
    )
    .unwrap();
    assert_eq!(record["status"], "completed");
    assert_eq!(record["trace"]["ticks"].as_array().unwrap().len(), 1);
}
/// KR-r2-L1-02；转移§3.1：即使只剩一条出支，也不能忽略原固定选择。
#[test]
fn revision_r2_damping_does_not_rebind_singleton() {
    let mut e = fixture("revision_r2_branch_cut");
    let query = "PC|source:north:0|merge_a:south:0";
    e.active.remove("PC|fork:north:0|gate:south:0");
    assert_eq!(e.damping(query).unwrap(), 2);
}
/// KR-r2-L1-03；输入§3.1：所有类型都核拥有者；仅作为关系端点不算拥有记录。
#[test]
fn revision_r2_unowned_global_events() {
    let e = engine("混做粉碎机两下游");
    for kind in [
        "runtime",
        "connection_close",
        "connection_open",
        "offline",
        "withdraw_product",
        "build",
        "unit_removed",
        "unit_rebuilt",
        "debug_operation",
        "blueprint_complete",
        "debug_end",
    ] {
        let mut raw = e.input.raw.clone();
        raw["timeline"]["events"]
            .as_array_mut()
            .unwrap()
            .push(json!({"id":"unowned_probe","kind":kind,"time":tv(1)}));
        relation(&mut raw, "debug_end", "unowned_probe", "occurs_before");
        let stop = load(raw, &e.input.path).unwrap_err();
        assert_eq!(stop.status, "invalid_input");
        assert_eq!(stop.location, "timeline.events.unowned_probe", "{kind}");
    }
    fixture("revision_r2_phase_control")
        .run_without_output(2)
        .unwrap();
}
/// KR-r2-L3-01/03；输入§1.1、§6：字段按Decision/仓库类型读取，不让任意JSON跳过校验。
#[test]
fn revision_r2_required_input_shapes() {
    let e = engine("混做粉碎机两下游");
    for value in [
        json!(null),
        json!(7),
        json!({}),
        json!("proof"),
        json!([]),
        json!(false),
        json!({"status":"specified","value":{},"basis":[]}),
        json!({"status":"not_applicable","value":null,"basis":["回归"]}),
    ] {
        let mut raw = e.input.raw.clone();
        raw["initial_state"]["reachability"] = value;
        let stop = load(raw, &e.input.path).unwrap_err();
        assert_eq!(stop.status, "invalid_input");
        assert!(stop.location.ends_with("initial_state.reachability"));
    }
    for value in [
        None,
        Some(json!("filled")),
        Some(Value::Null),
        Some(json!(false)),
    ] {
        let mut raw = e.input.raw.clone();
        if let Some(value) = value {
            raw["initial_state"]["warehouse"]["unlisted"] = value;
        } else {
            raw["initial_state"]["warehouse"]
                .as_object_mut()
                .unwrap()
                .remove("unlisted");
        }
        let stop = load(raw, &e.input.path).unwrap_err();
        assert_eq!(stop.status, "invalid_input");
        assert!(stop.location.starts_with("initial_state.warehouse"));
    }
    load(e.input.raw.clone(), &e.input.path)
        .unwrap()
        .run_without_output(2)
        .unwrap();
}
/// KR-r2-L3-02；输入§3.1、§5.2、§6：恢复身份不能冒用历史、未来时刻或另一模板。
#[test]
fn revision_r2_seed_consumed_identity() {
    let mut e = engine("混做粉碎机两下游");
    e.step(true).unwrap();
    e.step(true).unwrap();
    let mut raw = e.input.raw.clone();
    raw["initial_state"]["nonwarehouse"]["value"] = json!(e.state);
    for id in [
        "build_0",
        "J|2|0|0",
        "J|1|999|0",
        "J|1|0|11",
        "C|1|crusher",
        "missing",
        "",
    ] {
        let mut bad = raw.clone();
        bad["initial_state"]["nonwarehouse"]["value"]["semantic_context"]["tick_context"]
            ["value"]["movements"][0]["event"] = json!(id);
        assert!(load(bad, &e.input.path).is_err(), "{id}");
    }
    let mut control = load(raw.clone(), &e.input.path).unwrap();
    let ids = seed_executed(&control.input, &json!(control.state)).unwrap();
    assert!(!ids.is_empty());
    assert!(ids.is_subset(&control.allocated));
    assert!(ids.is_subset(&control.executed));
    assert!(control.allocate(ids.first().unwrap()).is_err());
    assert!(control.execute(ids.first().unwrap()).is_err());
    assert_eq!(control.step(true).unwrap(), e.step(true).unwrap());
    // 非保留的历史runtime别名由移动拥有且时刻正确，可以恢复，但同样消费一次。
    let id = "past_move";
    raw["initial_state"]["nonwarehouse"]["value"]["semantic_context"]["tick_context"]["value"]
        ["movements"][0]["event"] = json!(id);
    raw["timeline"]["events"]
        .as_array_mut()
        .unwrap()
        .push(json!({"id":id,"kind":"runtime","time":tv(1)}));
    let mut restored = load(raw.clone(), &e.input.path).unwrap();
    assert!(restored.executed.contains(id));
    restored.step(true).unwrap();
    raw["timeline"]["events"]
        .as_array_mut()
        .unwrap()
        .last_mut()
        .unwrap()["time"] = tv(2);
    assert!(load(raw, &e.input.path).is_err());
}
/// KR-r2-L3-02；输出§2：合法多BC制造同属一个实例，篡改其模板或重复穿越均拒收。
#[test]
fn revision_r2_internal_passage_identity() {
    let mut e = engine("混做粉碎机两下游");
    for _ in 0..3 {
        e.step(true).unwrap();
    }
    let mut raw = e.input.raw.clone();
    raw["initial_state"]["nonwarehouse"]["value"] = json!(e.state);
    load(raw.clone(), &e.input.path).unwrap();
    let passages = &mut raw["initial_state"]["nonwarehouse"]["value"]["semantic_context"]
        ["tick_context"]["value"]["internal_passages"];
    assert!(!passages.as_array().unwrap().is_empty());
    let row = passages[0].clone();
    passages.as_array_mut().unwrap().push(row);
    assert!(load(raw, &e.input.path).is_err());
}
/// KR-r2-L2-01/L3-04；输出§1、§3：Rust完整验收继续拒绝双样例双编码的相同元数据变异。
#[test]
fn revision_r2_rust_metadata_controls() {
    let config = config();
    let path = root().join("规格/内核配置-v1.json");
    for (name, count) in [("混做粉碎机两下游", 4), ("分流器三路轮询", 12)] {
        for format in ["full_state_each_instant", "checkpoint_delta"] {
            let e = engine(name);
            let input = e.input.clone();
            let record = run_record(e, &config, &path, count, format, 5).unwrap();
            verify_record(&record, input.clone(), &config, &path).unwrap();
            for variant in 0..8 {
                let mut bad = record.clone();
                match variant {
                    0 => bad["uncovered_axes"][0]["axis"] = json!("forged.axis"),
                    1 => bad["uncovered_axes"][0]["disposition"] = json!("本版选值"),
                    2 => bad["uncovered_axes"][0]["evidence"] = json!(["missing_event"]),
                    3 => bad["uncovered_axes"][0]["coverage_status"] = json!("exercised"),
                    4 => bad["profile_id"] = json!("fake"),
                    5 => bad["producer"]["path"] = json!("fake.rs"),
                    6 => bad["run_id"] = json!("fake"),
                    _ => bad["uncovered_axes"][0]["reason"] = json!("fake"),
                }
                assert_ne!(bad, record);
                assert!(
                    verify_record(&bad, input.clone(), &config, &path).is_err(),
                    "{name}/{format}/{variant}"
                );
            }
        }
    }
}
