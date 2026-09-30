//! 第六轮：摘要碰撞、稀疏恢复、两阶段停止及独立前缀核验。
use super::*;
#[test]
fn round6_hash_collisions_replay_every_candidate() {
    let cfg = config();
    let cp = root().join("规格/内核配置-v1.json");
    let input = engine("生产循环环带").input;
    let expected = crate::cycle::run_cycle(input.clone(), &cfg, &cp, 50, 10000).unwrap();
    let options = crate::cycle::SearchOptions {
        checkpoint_interval: 7,
        force_collision: true,
        ..Default::default()
    };
    let actual =
        crate::cycle::run_cycle_with_options(input.clone(), &cfg, &cp, 50, 10000, &options)
            .unwrap();
    assert_eq!(actual, expected);
    let exhausted = crate::cycle::run_cycle_with_options(
        input,
        &cfg,
        &cp,
        50,
        10000,
        &crate::cycle::SearchOptions {
            replay_limit: 0,
            ..options
        },
    )
    .unwrap();
    assert_eq!(exhausted["status"], "inconclusive");
    assert_eq!(exhausted["stop"]["axis"], "resource.replay");
    assert!(exhausted["cycle"].is_null());
}
#[test]
fn round6_compact_step_preserves_full_checkpoint() {
    let mut a = engine("桥接器双通路");
    let mut b = engine("桥接器双通路");
    for _ in 0..15 {
        let row = a.step(true).unwrap().unwrap();
        b.step_compact().unwrap();
        assert_eq!(row["state"], json!(b.state));
        assert_eq!(row["events"], json!(b.records));
        assert_eq!(row["warehouse_ledger"], b.ledger);
    }
}
#[test]
fn round6_no_record_retains_loaded_zero_prefix() {
    let cfg = config();
    let cp = root().join("规格/内核配置-v1.json");
    let result = crate::cycle::run_cycle(engine("生产循环环带").input, &cfg, &cp, 5, 1).unwrap();
    assert_eq!(result["status"], "inconclusive");
    assert_eq!(result["budget"]["completed_ticks"], 0);
    assert!(!result["replay_input_ref"].is_null());
    assert!(!result["last_state"].is_null());
    assert!(!result["seed"].is_null());
    assert!(crate::cycle::verify_cycle(&result, &cfg, &cp).is_ok());
    let stop = Stop::new(
        "inconclusive",
        "resource.integer",
        "entered_at",
        "时差超出i64运行域",
    );
    let shell = crate::cycle::load_stopped_cycle(&stop, 5, 1, "");
    assert!(shell["seed"].is_null());
    assert!(shell["port_meeting"].is_null());
    assert_eq!(shell["stop"]["kind"], "resource");
    assert_eq!(shell["domain_report"].as_array().unwrap().len(), 5);
    assert!(crate::cycle::verify_cycle(&shell, &cfg, &cp).is_err());
}
#[test]
fn round6_put_rejects_without_partial_write() {
    let mut e = engine("混做粉碎机两下游");
    e.put("crusher:output:0", "源石粉末", 50).unwrap();
    let before = json!(e.state);
    for (item, n) in [("蓝铁粉末", 1), ("源石粉末", 1), ("源石粉末", i64::MAX)] {
        let stop = e.put("crusher:output:0", item, n).unwrap_err();
        assert_eq!(stop.status, "invalid_input");
        assert_eq!(stop.location, "crusher:output:0");
        assert_eq!(json!(e.state), before);
    }
    assert!(e.put("missing:output:0", "源矿", 1).is_err());
}
#[test]
fn round6_test_only_two_product_recipe_keeps_buffer_exception() {
    let mut e = engine("混做粉碎机两下游");
    let recipe = e
        .input
        .catalog
        .recipes
        .values_mut()
        .find(|r| r.kind == "粉碎机" && r.inputs.contains_key("源矿"))
        .unwrap();
    recipe.outputs.insert("蓝铁粉末".into(), 1);
    for _ in 0..4 {
        e.step(false).unwrap();
    }
    let buffer = &e.state.inventory[e.inv["crusher:buffer:0"]].contents;
    assert_eq!(buffer.len(), 2);
    assert!(e.state.inventory[e.inv["crusher:output:0"]]
        .contents
        .is_empty());
    // 规则L18缓存的多物种例外保留；普通取货格整批守卫禁止两产物挤进一个格。
    assert_eq!(e.state.progress[e.progress["crusher"]].phase, "completed");
    assert_eq!(e.completed_batches, 1);
}
#[test]
fn round6_static_domain_reports_all_without_tick() {
    let mut e = engine("生产循环环带");
    let before = json!(e.state);
    let report = e.domain_report("static");
    assert_eq!(json!(e.state), before);
    assert_eq!(report.as_array().unwrap().len(), 5);
    assert!(report
        .as_array()
        .unwrap()
        .iter()
        .all(|r| r["status"] == "pass" && r["scope"] == "static"));
    e.state.environment.online = false;
    e.state
        .semantic_context
        .arbitration
        .warehouse_empty_slot_order = vec!["unresolved_slot".into()];
    let report = e.domain_report("static");
    assert_eq!(report[0]["status"], "fail");
    assert_eq!(report[2]["status"], "fail");
    assert_eq!(report[4]["status"], "pass");
}
#[test]
fn round6_static_pass_does_not_replace_dynamic_d2() {
    let mut e = fixture("core_inbound");
    put(&mut e, "box:storage:0", "源矿", 1);
    let mut raw = e.input.raw.clone();
    raw["initial_state"]["nonwarehouse"]["value"] = json!(e.state);
    set_axis(
        &mut raw,
        "warehouse.external_supply",
        json!({"kind":"sufficient"}),
    );
    let raw = Input::canonicalize_seed(raw, e.input.path.parent().unwrap(), &config()).unwrap();
    let e = Engine::new(Input::parse(raw, &e.input.path, &config(), false).unwrap()).unwrap();
    assert_eq!(e.domain_report("static")[1]["status"], "pass");
    let (result, _) = crate::cycle::search(
        e.input,
        &config(),
        &root().join("规格/内核配置-v1.json"),
        5,
        10000,
        &Default::default(),
    )
    .unwrap();
    assert_eq!(result["status"], "stopped");
    assert_eq!(result["stop"]["axis"], "cycle.domain.D2");
    assert_eq!(result["domain_report"][1]["status"], "fail");
    assert_eq!(result["domain_report"][1]["scope"], "executed_prefix");
    assert!(result["cycle"].is_null());
}

#[test]
fn round6_independent_ledger_conservation_rejects_state_and_total_tampering() {
    let mut e = engine("桥接器双通路");
    for _ in 0..12 {
        let before = json!(e.state);
        let tick = e.step(true).unwrap().unwrap();
        crate::ledger::verify_tick(&before, &tick).unwrap();
        let mut bad = tick.clone();
        bad["state"]["warehouse"]["slots"][0]["quantity"] = q(79999);
        assert!(crate::ledger::verify_tick(&before, &bad).is_err());
        let mut bad = tick;
        bad["warehouse_ledger"]["totals"][0]["actual_inbound"] = q(99);
        assert!(crate::ledger::verify_tick(&before, &bad).is_err());
    }
}
