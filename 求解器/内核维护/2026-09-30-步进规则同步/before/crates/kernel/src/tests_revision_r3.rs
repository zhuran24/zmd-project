//! 第3轮修订：检查点保真、装载失败与独立全前缀验收回归。
use super::*;

fn checkpoint(name: &str, ticks: usize) -> (Value, PathBuf) {
    let mut e = engine(name);
    for _ in 0..ticks {
        e.step(false).unwrap();
    }
    let mut raw = e.input.raw.clone();
    raw["initial_state"]["nonwarehouse"]["value"] = json!(e.state);
    (raw, e.input.path)
}
fn load(raw: Value, path: &std::path::Path) -> Result<Engine> {
    Engine::new(Input::parse(raw, path, &config(), false)?)
}
fn reject_both(raw: Value, path: &std::path::Path) {
    assert!(load(raw.clone(), path).is_err());
    assert!(Input::canonicalize_seed(raw, path.parent().unwrap(), &config()).is_err());
}

#[test]
fn revision_r3_checkpoint_parameters_are_not_repaired() {
    let (raw, path) = checkpoint("桥接器双通路", 6);
    let derived = Input::canonicalize_seed(raw.clone(), path.parent().unwrap(), &config()).unwrap();
    assert_eq!(
        derived["initial_state"]["nonwarehouse"],
        raw["initial_state"]["nonwarehouse"]
    );
    let mut a = load(raw.clone(), &path).unwrap();
    let mut b = load(derived, &path).unwrap();
    for _ in 0..4 {
        assert_eq!(a.step(true).unwrap(), b.step(true).unwrap());
    }
    for mutation in ["missing", "duplicate", "conflict", "top_only", "lifetime"] {
        let mut bad = raw.clone();
        if mutation == "top_only" {
            bad["parameters"]["fixedness_unproven"]["transfer.phase"]["value"]["values"][0]
                ["remaining"] = tv(4);
        } else {
            let rows = bad["initial_state"]["nonwarehouse"]["value"]["semantic_context"]
                ["parameter_values"]
                .as_array_mut()
                .unwrap();
            match mutation {
                "missing" => rows.clear(),
                "duplicate" => rows.push(rows[0].clone()),
                "conflict" => {
                    rows.iter_mut()
                        .find(|r| r["axis"] == "transfer.phase")
                        .unwrap()["value"]["value"]["values"][0]["remaining"] = tv(4)
                }
                "lifetime" => rows[0]["lifetime"] = json!("wrong"),
                _ => unreachable!(),
            }
        }
        reject_both(bad, &path);
    }
}

#[test]
fn revision_r3_phase_type_and_domain_at_both_anchors() {
    let (closed, path) = checkpoint("桥接器双通路", 3);
    let initial = engine("桥接器双通路").input.raw;
    let mut half = tv(0);
    half["value"]["value"] = json!("1/2");
    for original in [initial, closed] {
        for remaining in [
            tv(-1),
            tv(6),
            half.clone(),
            json!("not-a-Time"),
            json!(true),
            Value::Null,
        ] {
            let mut raw = original.clone();
            let mut phase =
                raw["parameters"]["fixedness_unproven"]["transfer.phase"]["value"].clone();
            phase["values"][0]["remaining"] = remaining;
            set_axis(&mut raw, "transfer.phase", phase);
            reject_both(raw, &path);
        }
    }
    // 合法历史初相位0不必等于t=2的当前冷却3，两个端点相位5也可输入。
    for remaining in [0, 5] {
        let (mut raw, path) = checkpoint("桥接器双通路", 3);
        let mut phase = raw["parameters"]["fixedness_unproven"]["transfer.phase"]["value"].clone();
        phase["values"][0]["remaining"] = tv(remaining);
        set_axis(&mut raw, "transfer.phase", phase);
        let derived =
            Input::canonicalize_seed(raw.clone(), path.parent().unwrap(), &config()).unwrap();
        assert_eq!(
            derived["initial_state"]["nonwarehouse"],
            raw["initial_state"]["nonwarehouse"]
        );
        load(derived, &path).unwrap().step(true).unwrap();
    }
}

#[test]
fn revision_r3_window_deadline_respects_anchor_phase() {
    let (original, path) = checkpoint("分流器三路轮询", 6);
    for offset in [-1, 0, 1] {
        let mut raw = original.clone();
        let state = &mut raw["initial_state"]["nonwarehouse"]["value"];
        let t = instant(&state["environment"]["time"], "test").unwrap();
        let gate = state["logistics"]["gate_counters"]
            .as_array_mut()
            .unwrap()
            .iter_mut()
            .find(|g| !g["window_started_at"].is_null())
            .unwrap();
        let uid = gate["unit"].as_str().unwrap().to_string();
        gate["window_started_at"] = tv(t + offset - 5);
        let pending = state["semantic_context"]["pending_events"]["value"]
            .as_array_mut()
            .unwrap()
            .iter_mut()
            .find(|p| p["target"] == uid)
            .unwrap();
        pending["trigger"]["value"] = tv(t + offset);
        pending["event"] = json!(format!("W|{}|{uid}", t + offset));
        if offset <= 0 {
            reject_both(raw.clone(), &path);
        } else {
            load(raw.clone(), &path).unwrap();
        }
        if offset == 0 {
            state_before_boundary(&mut raw);
            let derived = Input::canonicalize_seed(raw, path.parent().unwrap(), &config()).unwrap();
            let input = Input::parse(derived, &path, &config(), false).unwrap();
            let mut e = Engine::new(input.clone()).unwrap();
            let start = json!(e.state);
            let tick = e.step_instant(true).unwrap().unwrap();
            assert_eq!(tick["time"], tv(t));
            assert!(tick["events"]
                .as_array()
                .unwrap()
                .iter()
                .any(|v| v["event"] == format!("W|{t}|{uid}")));
            crate::event_identity::validate_event_identity(&input, &start, &[tick]).unwrap();
        }
    }
}
fn state_before_boundary(raw: &mut Value) {
    let state = &mut raw["initial_state"]["nonwarehouse"]["value"];
    state["semantic_context"]["judgment_context"]["value"]["phase"] = json!("before_boundary");
}

#[test]
fn revision_r3_sufficient_requires_both_positive_ores() {
    for item in ["源矿", "蓝铁矿"] {
        for closed in [false, true] {
            let (mut raw, path) = if closed {
                checkpoint("生产循环环带", 2)
            } else {
                let e = engine("生产循环环带");
                (e.input.raw, e.input.path)
            };
            let row = raw["initial_state"]["nonwarehouse"]["value"]["warehouse"]["slots"]
                .as_array_mut()
                .unwrap()
                .iter_mut()
                .find(|r| r["item"] == item)
                .unwrap();
            row["item"] = Value::Null;
            row["quantity"] = q(0);
            row["empty_identity"] = json!(Decision::specified(json!(item), "测试历史空矿格"));
            reject_both(raw, &path);
        }
    }
}

#[test]
fn revision_r3_malformed_seed_returns_stop_before_indexing() {
    let e = engine("混做粉碎机两下游");
    for slot in [
        "bad",
        "",
        "bad:input:0",
        "crusher:input:999",
        "a:b",
        ":",
        "crusher:input:0:extra",
    ] {
        let mut raw = e.input.raw.clone();
        raw["initial_state"]["nonwarehouse"]["value"]["inventory"][0]["slot"] = json!(slot);
        reject_both(raw, &e.input.path);
    }
    for pointer in [
        "/initial_state/nonwarehouse/value",
        "/initial_state/nonwarehouse/value/semantic_context",
        "/initial_state/nonwarehouse/value/semantic_context/judgment_context",
        "/initial_state/nonwarehouse/value/inventory",
    ] {
        for malformed in [json!(true), json!(5), json!([]), json!("bad"), Value::Null] {
            let mut raw = e.input.raw.clone();
            *raw.pointer_mut(pointer).unwrap() = malformed;
            reject_both(raw, &e.input.path);
        }
    }
    for section in ["progress", "warehouse", "inventory"] {
        let mut raw = e.input.raw.clone();
        let state = &mut raw["initial_state"]["nonwarehouse"]["value"];
        match section {
            "progress" => state["progress"][0]["unit"] = json!("unknown"),
            "warehouse" => state["warehouse"]["slots"] = json!([]),
            _ => {
                let rows = state["inventory"].as_array_mut().unwrap();
                rows.push(rows[0].clone());
            }
        }
        reject_both(raw, &e.input.path);
    }
}

#[test]
fn revision_r3_cycle_checks_prefix_before_recomputation() {
    let e = engine("生产循环环带");
    let cfg = config();
    let cp = root().join("规格/内核配置-v1.json");
    let mut result = crate::cycle::run_cycle(e.input.clone(), &cfg, &cp, 50, 100000).unwrap();
    assert_eq!(
        crate::cycle::verify_cycle(&result, &cfg, &cp).unwrap()["cycle_replayed"],
        true
    );
    let time = instant(&result["cycle"]["start_time"], "start").unwrap();
    let mut record =
        crate::output::run_record(e, &cfg, &cp, 25, "full_state_each_instant", 1).unwrap();
    let rows = record["trace"]["ticks"].as_array_mut().unwrap();
    assert!(instant(&rows[0]["time"], "prefix").unwrap() <= time);
    let duplicate = rows[0]["events"][0].clone();
    let id = duplicate["event"].as_str().unwrap().to_string();
    rows[0]["events"].as_array_mut().unwrap().push(duplicate);
    let err =
        crate::output::verify_record_events(&record, &engine("生产循环环带").input).unwrap_err();
    result["budget"]["completed_ticks"] = json!(0);
    assert!(crate::cycle::verify_cycle(&result, &cfg, &cp).is_err());
    assert_eq!(err.location, id);
    assert!(err.reason.contains("重复执行"));
}

#[test]
fn revision_r3_bridge_moves_are_not_first_contact_events() {
    let mut e = engine("桥接器双通路");
    let mut rows = vec![];
    for _ in 0..5 {
        rows.push(e.step(true).unwrap().unwrap());
    }
    let coverage = coverage(&config(), &rows, &e.input);
    assert_eq!(
        coverage
            .iter()
            .find(|r| r["axis"] == "connection.bridge_first_contact")
            .unwrap()["coverage_status"],
        "input_checked"
    );
    for axis in [
        "bridge.inventory_scope",
        "bridge.capacity",
        "bridge.scheduling_scope",
    ] {
        assert_eq!(
            coverage.iter().find(|r| r["axis"] == axis).unwrap()["coverage_status"],
            "exercised"
        );
    }
}
