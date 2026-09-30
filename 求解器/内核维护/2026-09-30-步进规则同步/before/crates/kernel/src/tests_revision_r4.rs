//! 第4轮：年龄分组、封闭触发器、阻尼查询域、覆盖及空续跑前缀。
use super::*;

fn load(raw: Value, path: &std::path::Path) -> Result<Engine> {
    Engine::new(Input::parse(raw, path, &config(), false)?)
}

fn stock(raw: &mut Value, slot: &str, contents: Value) {
    let row = raw["initial_state"]["nonwarehouse"]["value"]["inventory"]
        .as_array_mut()
        .unwrap()
        .iter_mut()
        .find(|r| r["slot"] == slot)
        .unwrap();
    row["contents"] = contents;
}

fn cohort(item: &str, quantity: i64, entered: i64) -> Value {
    json!({"item":item,"quantity":q(quantity),"entered_at":tv(entered)})
}

#[test]
fn revision_r4_age_cohorts_seed_capacity_and_key() {
    let original = engine("桥接器双通路");
    let path = original.input.path;
    let mut raw = original.input.raw;
    stock(
        &mut raw,
        "south_box:storage:0",
        json!([cohort("高容谷地电池", 1, -2), cohort("高容谷地电池", 1, -1)]),
    );
    let derived = Input::canonicalize_seed(raw.clone(), path.parent().unwrap(), &config()).unwrap();
    let mut e = load(derived.clone(), &path).unwrap();
    assert_eq!(
        e.state.inventory[e.inv["south_box:storage:0"]]
            .contents
            .len(),
        2
    );
    e.step(false).unwrap();
    assert_eq!(
        e.state.inventory[e.inv["south_box:storage:0"]]
            .contents
            .len(),
        1
    );
    let key = e.cycle_key().unwrap();
    assert!(!key.is_null());
    // 普通格物种、总容量和同种跨格约束仍然生效。
    for contents in [
        json!([cohort("高容谷地电池", 1, -2), cohort("精选荞愈胶囊", 1, -1)]),
        json!([
            cohort("高容谷地电池", 25, -2),
            cohort("高容谷地电池", 26, -1)
        ]),
    ] {
        let mut bad = raw.clone();
        stock(&mut bad, "south_box:storage:0", contents);
        assert!(Input::canonicalize_seed(bad, path.parent().unwrap(), &config()).is_err());
    }
    let mut e = engine("研磨混做核验");
    put(&mut e, "grinder:input:0", "蓝铁粉末", 1);
    put(&mut e, "grinder:input:1", "蓝铁粉末", 1);
    assert!(e.validate_inventory().is_err());
    // 两个年龄组共50件时箱格已满，后续入件应选下一编号格。
    let mut full = derived;
    stock(
        &mut full,
        "north_box:storage:0",
        json!([
            cohort("高容谷地电池", 25, -2),
            cohort("高容谷地电池", 25, -1)
        ]),
    );
    let e = load(
        Input::canonicalize_seed(full, path.parent().unwrap(), &config()).unwrap(),
        &path,
    )
    .unwrap();
    let port = e
        .input
        .geometry
        .ports
        .iter()
        .find(|(_, p)| p.unit == "north_box" && p.role == "input")
        .unwrap()
        .0;
    assert_eq!(
        e.target(port, "高容谷地电池").unwrap(),
        Some("north_box:storage:1".into())
    );
}

#[test]
fn revision_r4_cohorts_manufacture_remove_and_arrival_age() {
    let original = engine("研磨混做核验");
    let path = original.input.path;
    let mut raw = original.input.raw;
    stock(
        &mut raw,
        "grinder:input:0",
        json!([cohort("蓝铁粉末", 1, -2), cohort("蓝铁粉末", 1, -1)]),
    );
    stock(
        &mut raw,
        "grinder:input:1",
        json!([cohort("砂叶粉末", 1, -1)]),
    );
    let raw = Input::canonicalize_seed(raw, path.parent().unwrap(), &config()).unwrap();
    let mut e = load(raw, &path).unwrap();
    let tick = e.step(true).unwrap().unwrap();
    assert!(tick["events"]
        .as_array()
        .unwrap()
        .iter()
        .any(|v| v["operation"] == "manufacture" && v["outcome"] == "success"));
    assert_eq!(count(&e, "grinder:input:0"), 0);
    assert_eq!(count(&e, "grinder:buffer:0"), 3);
    // 缓存按物种合计核一批，不把后一个年龄组覆盖前一个。
    let mut checkpoint = e.input.raw.clone();
    checkpoint["initial_state"]["nonwarehouse"]["value"] = json!(e.state);
    stock(
        &mut checkpoint,
        "grinder:buffer:0",
        json!([
            cohort("蓝铁粉末", 1, -2),
            cohort("蓝铁粉末", 1, -1),
            cohort("砂叶粉末", 1, 0)
        ]),
    );
    load(checkpoint, &path).unwrap().step(true).unwrap();
    let mut e = engine("桥接器双通路");
    put(&mut e, "south_box:storage:0", "高容谷地电池", 1);
    let rows = &e.state.inventory[e.inv["south_box:storage:0"]].contents;
    assert_eq!(rows.len(), 2);
    assert_eq!(
        rows[0]
            .entered_at
            .as_ref()
            .unwrap()
            .integer("test")
            .unwrap(),
        -1
    );
    assert_eq!(
        rows[1]
            .entered_at
            .as_ref()
            .unwrap()
            .integer("test")
            .unwrap(),
        0
    );
    let before = e.state.clone();
    assert!(e.remove("south_box:storage:0", "高容谷地电池", 10).is_err());
    assert_eq!(e.state, before);
}

#[test]
fn revision_r4_pending_trigger_is_closed_before_derivation_and_key() {
    let mut e = engine("研磨混做核验");
    for _ in 0..12 {
        e.step(false).unwrap();
        if !e.pending.is_empty() {
            break;
        }
    }
    let path = e.input.path.clone();
    let mut raw = e.input.raw.clone();
    raw["initial_state"]["nonwarehouse"]["value"] = json!(e.state);
    assert!(!e.pending.is_empty());
    e.cycle_key().unwrap();
    for phase in ["after_closure", "before_boundary"] {
        let mut bad = if phase == "before_boundary" {
            engine("研磨混做核验").input.raw
        } else {
            raw.clone()
        };
        bad["initial_state"]["nonwarehouse"]["value"]["semantic_context"]["pending_events"]
            ["value"] = json!(e.pending);
        bad["initial_state"]["nonwarehouse"]["value"]["semantic_context"]["pending_events"]
            ["value"][0]["trigger"]["extra"] = json!(true);
        for error in [
            load(bad.clone(), &path).unwrap_err(),
            Input::canonicalize_seed(bad, path.parent().unwrap(), &config()).unwrap_err(),
        ] {
            assert_eq!(error.status, "invalid_input");
            assert!(error.location.contains("trigger"), "{error}");
        }
    }
    let mut bad = e.state.clone();
    bad.semantic_context.pending_events.value[0]["trigger"]["extra"] = json!(true);
    assert!(crate::cycle::cycle_key(&bad, &e.input).is_err());
    e.state = bad;
    assert!(e.cycle_key().is_err());
}

#[test]
fn revision_r4_single_level_empty_branch_table_matches_full_table() {
    let original = engine("分流器三路轮询");
    let path = original.input.path;
    let mut raw = original.input.raw;
    let mut branch = raw["parameters"]["fixedness_unproven"]["damping.branch"]["value"].clone();
    assert!(!branch["choices"].as_array().unwrap().is_empty());
    branch["choices"] = json!([]);
    set_axis(&mut raw, "damping.branch", branch);
    let derived = Input::canonicalize_seed(raw.clone(), path.parent().unwrap(), &config()).unwrap();
    let mut a = engine("分流器三路轮询");
    let mut b = load(derived, &path).unwrap();
    for _ in 0..12 {
        let mut x = a.step(true).unwrap().unwrap();
        let mut y = b.step(true).unwrap().unwrap();
        // 唯一输入差异是未被查询的表；状态参数点必须如实保留，物理/事件字段逐项相同。
        x["state"]["semantic_context"]["parameter_values"] = Value::Null;
        y["state"]["semantic_context"]["parameter_values"] = Value::Null;
        assert_eq!(x, y);
    }
    let mut bad = raw;
    let mut branch = bad["parameters"]["fixedness_unproven"]["damping.branch"]["value"].clone();
    branch["choices"] =
        json!([{"fork_unit":"missing","available_channels":["bad"],"outgoing_channel":"bad"}]);
    set_axis(&mut bad, "damping.branch", branch);
    assert_eq!(
        Input::parse(bad, &path, &config(), false)
            .unwrap_err()
            .status,
        "invalid_input"
    );
}

#[test]
fn revision_r4_multilevel_branch_table_includes_dormant_subsets() {
    let original = engine("阻尼切支恢复核验");
    let path = original.input.path;
    let raw = original.input.raw;
    let branch = raw["parameters"]["fixedness_unproven"]["damping.branch"]["value"].clone();
    for index in 0..branch["choices"].as_array().unwrap().len() {
        let mut bad = raw.clone();
        let mut missing = branch.clone();
        missing["choices"].as_array_mut().unwrap().remove(index);
        set_axis(&mut bad, "damping.branch", missing);
        let error = Input::parse(bad, &path, &config(), false).unwrap_err();
        assert_eq!(error.axis, "damping.branch");
        assert_eq!(error.status, "unresolved");
    }
    let mut e = engine("阻尼切支恢复核验");
    for _ in 0..18 {
        e.step(false).unwrap();
    }
}

#[test]
fn revision_r4_path_runs_never_exercises_geometric_adjacency() {
    let e = engine("阻尼连续带核验");
    let record = output::run_record(
        e,
        &config(),
        &root().join("规格/内核配置-v1.json"),
        3,
        "full_state_each_instant",
        1,
    )
    .unwrap();
    let axis = |name| {
        record["uncovered_axes"]
            .as_array()
            .unwrap()
            .iter()
            .find(|r| r["axis"] == name)
            .unwrap()
    };
    assert_eq!(
        axis("damping.belt_component_rule")["coverage_status"],
        "exercised"
    );
    assert_eq!(
        axis("damping.belt_adjacency")["coverage_status"],
        "not_exercised"
    );
    assert!(!record["trace"]["ticks"]
        .to_string()
        .contains("belt_adjacency:"));
}

#[test]
fn revision_r4_first_resumed_sweep_stop_preserves_checkpoint() {
    for format in ["full_state_each_instant", "checkpoint_delta"] {
        let mut e = engine("混做粉碎机两下游");
        e.step(false).unwrap();
        e.step(false).unwrap();
        let start = json!(e.state);
        e.max_sweeps = 1;
        let record = output::run_record(
            e,
            &config(),
            &root().join("规格/内核配置-v1.json"),
            1,
            format,
            5,
        )
        .unwrap();
        assert_eq!(record["status"], "inconclusive");
        let trace = output::decode_trace(&record["trace"]).unwrap();
        assert_eq!(trace["start_state"], start);
        assert_eq!(trace["ticks"], json!([]));
        assert_eq!(trace["end_time"], start["environment"]["time"]);
        assert_eq!(
            record["validation_scope"]["from"],
            start["environment"]["time"]
        );
        assert_eq!(
            record["validation_scope"]["through"],
            start["environment"]["time"]
        );
        assert!(record["open_items"].to_string().contains("instant=2"));
    }
}
