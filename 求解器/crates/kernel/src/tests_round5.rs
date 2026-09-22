//! 第五轮K8：派生往返、真实循环、账本守恒、模式差分及缓存失效。
use super::*;
fn sample(name: &str) -> Engine {
    engine(name)
}
#[test]
fn round5_seed_roundtrip() {
    for name in ["混做粉碎机两下游", "分流器三路轮询"] {
        let mut original = sample(name);
        let path = original.input.path.clone();
        let raw = Input::canonicalize_seed(
            original.input.raw.clone(),
            path.parent().unwrap(),
            &config(),
        )
        .unwrap();
        let mut derived = Engine::new(Input::parse(raw, &path, &config(), false).unwrap()).unwrap();
        for _ in 0..4 {
            assert_eq!(original.step(true).unwrap(), derived.step(true).unwrap());
        }
    }
}
#[test]
fn round5_seed_tie_changes_rebuild_ring() {
    let e = sample("分流器三路轮询");
    let mut raw = e.input.raw.clone();
    let mut tie = raw["parameters"]["fixedness_unproven"]["connection.tie"]["value"].clone();
    tie["channels"].as_array_mut().unwrap().reverse();
    raw["parameters"]["fixedness_unproven"]["connection.tie"]["value"] = tie;
    assert!(
        Engine::new(Input::parse(raw.clone(), &e.input.path, &config(), false).unwrap()).is_err()
    );
    let d = Input::canonicalize_seed(raw, e.input.path.parent().unwrap(), &config()).unwrap();
    Engine::new(Input::parse(d, &e.input.path, &config(), false).unwrap())
        .unwrap()
        .step(true)
        .unwrap();
}
#[test]
fn round5_supply_differential_and_last_ore() {
    let mut explicit = sample("混做粉碎机两下游");
    let mut raw = explicit.input.raw.clone();
    set_axis(
        &mut raw,
        "warehouse.external_supply",
        json!({"kind":"sufficient"}),
    );
    let mut sufficient =
        Engine::new(Input::parse(raw, &explicit.input.path, &config(), false).unwrap()).unwrap();
    for _ in 0..4 {
        let a = explicit.step(true).unwrap().unwrap();
        let b = sufficient.step(true).unwrap().unwrap();
        for field in ["inventory", "progress", "logistics"] {
            assert_eq!(a["state"][field], b["state"][field]);
        }
        assert_eq!(a["events"], b["events"]);
        assert_eq!(
            a["warehouse_ledger"]["port_outbound"],
            b["warehouse_ledger"]["port_outbound"]
        );
        assert_eq!(
            a["warehouse_ledger"]["port_outbound"]
                .as_array()
                .unwrap()
                .len(),
            b["warehouse_ledger"]["external_supply"]
                .as_array()
                .unwrap()
                .len()
        );
    }
    let mut raw = sample("混做粉碎机两下游").input.raw;
    set_axis(
        &mut raw,
        "warehouse.external_supply",
        json!({"kind":"sufficient"}),
    );
    for r in raw["initial_state"]["nonwarehouse"]["value"]["warehouse"]["slots"]
        .as_array_mut()
        .unwrap()
    {
        if r["item"] == "源矿" {
            r["quantity"] = q(1);
        }
    }
    let p = root().join("数据/样例/混做粉碎机两下游.json");
    let mut e = Engine::new(Input::parse(raw, &p, &config(), false).unwrap()).unwrap();
    for _ in 0..4 {
        e.step(false).unwrap();
    }
    assert_eq!(
        e.state
            .warehouse
            .slots
            .iter()
            .find(|r| r.item.as_deref() == Some("源矿"))
            .unwrap()
            .quantity
            .integer("ore")
            .unwrap(),
        1
    );
}
fn warehouse_counts(state: &State) -> BTreeMap<String, i64> {
    state
        .warehouse
        .slots
        .iter()
        .filter_map(|r| {
            r.item
                .as_ref()
                .map(|i| (i.clone(), r.quantity.integer(i).unwrap()))
        })
        .collect()
}
#[test]
fn round5_ledgers_conserve_every_species() {
    for name in [
        "桥接器双通路",
        "研磨混做核验",
        "生产循环环带",
        "轮询均分核验",
    ] {
        let mut e = sample(name);
        e.production_abstraction = name == "生产循环环带";
        for _ in 0..20 {
            let before = warehouse_counts(&e.state);
            let tick = e.step(true).unwrap().unwrap();
            let after = warehouse_counts(&e.state);
            let mut expected = before;
            for row in tick["warehouse_ledger"]["totals"].as_array().unwrap() {
                let item = row["item"].as_str().unwrap();
                let n = num(&row["actual_inbound"], item).unwrap()
                    + num(&row["external_supply"], item).unwrap()
                    - num(&row["port_outbound"], item).unwrap()
                    - num(&row["player_withdrawal"], item).unwrap()
                    - num(&row["representative_adjustment"], item).unwrap();
                *expected.entry(item.into()).or_default() += n;
            }
            expected.retain(|_, n| *n != 0);
            assert_eq!(expected, after);
        }
    }
}
#[test]
fn round5_cycle_certificate_replay_and_tamper() {
    let e = sample("生产循环环带");
    let cfg = config();
    let path = root().join("规格/内核配置-v1.json");
    let result = crate::cycle::run_cycle(e.input, &cfg, &path, 50, 10000).unwrap();
    assert_eq!(result["status"], "counterexample");
    assert!(num(&result["cycle"]["period"], "period").unwrap() > 0);
    assert_eq!(
        crate::cycle::verify_cycle(&result, &cfg, &path).unwrap()["cycle_replayed"],
        true
    );
    for key in ["period", "start_key", "rates", "acceptance"] {
        let mut bad = result.clone();
        bad["cycle"][key] = Value::Null;
        assert!(crate::cycle::verify_cycle(&bad, &cfg, &path).is_err());
    }
    let mut bad = result.clone();
    bad["level"] = json!("full_base");
    assert!(crate::cycle::verify_cycle(&bad, &cfg, &path).is_err());
    let mut unpersisted = sample("生产循环环带").input;
    unpersisted.raw["scenario"]["assertions"] = json!(["没有写入所锁定输入文件的变异"]);
    assert!(crate::cycle::run_cycle(unpersisted, &cfg, &path, 50, 10000).is_err());
    let short =
        crate::cycle::run_cycle(sample("生产循环环带").input, &cfg, &path, 1, 10000).unwrap();
    assert_eq!(short["status"], "inconclusive");
    assert!(short["cycle"].is_null());
}
#[test]
fn round5_cache_differential() {
    for name in [
        "混做粉碎机两下游",
        "分流器三路轮询",
        "桥接器双通路",
        "研磨混做核验",
        "阻尼切支恢复核验",
        "阻尼连续带核验",
        "生产循环环带",
        "轮询均分核验",
        "密集结点核验",
    ] {
        let mut a = sample(name);
        let mut b = sample(name);
        b.set_cache_enabled(true);
        let ticks = if ["混做粉碎机两下游", "分流器三路轮询"].contains(&name) {
            4
        } else {
            12
        };
        for _ in 0..ticks {
            assert_eq!(a.step(true).unwrap(), b.step(true).unwrap(), "{name}");
        }
    }
    for name in [
        "benchmark_brick_60",
        "benchmark_brick",
        "benchmark_candidate_b",
    ] {
        let mut a = fixture(name);
        let mut b = fixture(name);
        b.set_cache_enabled(true);
        for _ in 0..2 {
            assert_eq!(a.step(true).unwrap(), b.step(true).unwrap(), "{name}");
        }
    }
}
#[test]
fn round5_completion_after_pause() {
    let mut e = sample("混做粉碎机两下游");
    e.step(false).unwrap();
    e.step(false).unwrap();
    e.input
        .switches
        .insert(("crusher".into(), "manufacture".into()), false);
    e.step(false).unwrap();
    e.input
        .switches
        .insert(("crusher".into(), "manufacture".into()), true);
    let tick = e.step(true).unwrap().unwrap();
    assert!(tick["events"]
        .as_array()
        .unwrap()
        .iter()
        .any(|e| e["operation"] == "manufacture_complete" && e["event"] == "C|2|crusher"));
}

#[test]
fn round5_inventory_order_is_canonical() {
    let mut original = sample("混做粉碎机两下游");
    let mut raw = original.input.raw.clone();
    raw["initial_state"]["nonwarehouse"]["value"]["inventory"]
        .as_array_mut()
        .unwrap()
        .reverse();
    let mut changed =
        Engine::new(Input::parse(raw, &original.input.path, &config(), false).unwrap()).unwrap();
    for _ in 0..4 {
        assert_eq!(original.step(true).unwrap(), changed.step(true).unwrap());
    }
}
#[test]
fn round5_ore_return_candidate_stops_before_capacity_or_age() {
    for quantity in [79999, 80000] {
        let mut e = fixture("core_inbound");
        for r in &mut e.state.warehouse.slots {
            if r.item.as_deref() == Some("源矿") {
                r.quantity = Quantity::calc(quantity);
            }
        }
        put(&mut e, "belt:transport:0", "源矿", 1);
        let mut raw = e.input.raw.clone();
        raw["initial_state"]["nonwarehouse"]["value"] = json!(e.state);
        set_axis(
            &mut raw,
            "warehouse.external_supply",
            json!({"kind":"sufficient"}),
        );
        let seed =
            Input::canonicalize_seed(raw, e.input.path.parent().unwrap(), &config()).unwrap();
        let e = Engine::new(Input::parse(seed, &e.input.path, &config(), false).unwrap()).unwrap();
        assert_eq!(e.production_domain().unwrap_err().axis, "cycle.domain.D2");
        let stop = crate::cycle::search(
            e.input,
            &config(),
            &root().join("规格/内核配置-v1.json"),
            2,
            100,
            &Default::default(),
        )
        .unwrap_err();
        // 修订r5：生产装载必须在派生可动级之前拒绝，不能先形成已装载前缀。
        assert_eq!(stop.status, "unsupported");
        assert_eq!(stop.axis, "cycle.domain.D2");
    }
}

#[test]
fn round5_cycle_age_overflow_is_resource_not_wrap() {
    let mut e = sample("阻尼连续带核验");
    e.step(false).unwrap();
    let slot = e.inv["source:storage:0"];
    e.state.inventory[slot].contents[0].entered_at = Some(Time::at(i64::MIN));
    let stop = e.cycle_key().unwrap_err();
    assert_eq!(stop.status, "inconclusive");
    assert_eq!(stop.axis, "resource.integer");
    let mut input = e.input.clone();
    input.raw["initial_state"]["nonwarehouse"]["value"] = json!(e.state);
    let result = crate::cycle::search(
        input,
        &config(),
        &root().join("规格/内核配置-v1.json"),
        2,
        100,
        &Default::default(),
    )
    .unwrap()
    .0;
    assert_eq!(result["status"], "inconclusive");
    assert!(result["cycle"].is_null());
    assert_eq!(result["budget"]["completed_ticks"], 0);
    assert!(!result["seed"].is_null());
}
