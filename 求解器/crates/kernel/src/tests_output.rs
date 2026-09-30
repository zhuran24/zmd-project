use crate::{cycle::checkpoint_input, output::*, tests_support::*, *};
use serde_json::{json, Value};
fn sample(name: &str) -> Input {
    Input::load(
        &root().join(format!("数据/样例/步进/差分/{name}.json")),
        &config(),
    )
    .unwrap()
}
#[test]
fn records_full_and_delta_roundtrip_and_tampering_rejected() {
    let c = config();
    let cfg = root().join("规格/内核配置-v2.json");
    for format in ["full_state_each_step", "checkpoint_delta"] {
        let input = sample("a-纯链");
        let record =
            run_record(Engine::new(input.clone()).unwrap(), &c, &cfg, 64, format, 7).unwrap();
        assert_eq!(record["schema"], "kernel-output-v5");
        assert_eq!(record["status"], "completed");
        verify_record_at(&record, input.clone(), &c, &cfg, &root()).unwrap();
        for field in ["state", "events", "warehouse_ledger"] {
            let mut bad = record.clone();
            let full = decode_trace(&bad["trace"]).unwrap();
            bad["trace"] = full;
            match field {
                "state" => bad["trace"]["steps"][1]["state"]["environment"]["time"] = value::tv(99),
                "events" => bad["trace"]["steps"][0]["events"][0]["event"] = json!("E|0|99"),
                _ => {
                    bad["trace"]["steps"][0]["warehouse_ledger"]["totals"][0]["actual_inbound"] =
                        value::q(9)
                }
            }
            assert!(
                verify_record_at(&bad, input.clone(), &c, &cfg, &root()).is_err(),
                "{field}"
            );
        }
    }
}
#[test]
fn checkpoint_roundtrip_preserves_fixed_parameters_and_step_successors() {
    let c = config();
    let mut e = Engine::new(
        Input::load(&root().join("数据/样例/步进/机制/无线部分接收.json"), &c).unwrap(),
    )
    .unwrap();
    e.step().unwrap();
    let resumed = checkpoint_input(&e.input, json!(e.state), &c).unwrap();
    assert_eq!(resumed.raw["parameters"], e.input.raw["parameters"]);
    let canonical =
        Input::canonicalize_seed(resumed.raw, resumed.path.parent().unwrap(), &c).unwrap();
    let parsed = Input::parse_with_base(canonical.clone(), &root(), &c).unwrap();
    let mut replay = Engine::new(parsed).unwrap();
    for _ in 0..41 {
        let a = e.step().unwrap();
        let b = replay.step().unwrap();
        assert_eq!(a, b);
        assert_eq!(e.state, replay.state);
    }
    assert_eq!(
        Input::canonicalize_seed(canonical.clone(), &root(), &c).unwrap(),
        canonical
    );
}
#[test]
fn seed_normalization_fills_missing_sides_and_clears_expired_windows() {
    let mut input = sample("e-汇流");
    let seed = &mut input.raw["initial_state"]["nonwarehouse"]["value"];
    seed["logistics"]["poll_state"]["cursors"] = json!([]);
    seed["logistics"]["gate_counters"][0]["total_received"] = value::q(1);
    seed["logistics"]["gate_counters"][0]["window_received"] = value::q(1);
    seed["logistics"]["gate_counters"][0]["window_started_at"] = value::tv(-40);
    let normalized =
        Input::canonicalize_seed(input.raw, input.path.parent().unwrap(), &config()).unwrap();
    let s = &normalized["initial_state"]["nonwarehouse"]["value"];
    assert!(!s["logistics"]["poll_state"]["cursors"]
        .as_array()
        .unwrap()
        .is_empty());
    assert!(s["logistics"]["gate_counters"][0]["window_started_at"].is_null());
    assert_eq!(
        Input::canonicalize_seed(normalized.clone(), &root(), &config()).unwrap(),
        normalized
    );
}
#[test]
fn migrated_mechanisms_load_and_execute_declared_steps_or_expected_stop() {
    let c = config();
    let mut paths = std::fs::read_dir(root().join("数据/样例/步进/机制"))
        .unwrap()
        .map(|e| e.unwrap().path())
        .collect::<Vec<_>>();
    paths.sort();
    assert_eq!(paths.len(), 14);
    for path in paths {
        let input = Input::load(&path, &c).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
        let steps = input.raw["scenario"]["steps"].as_u64().unwrap();
        let expected = input.raw["scenario"]["expected_stop"].clone();
        let mut e = Engine::new(input).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
        let mut stopped = false;
        for _ in 0..steps {
            if let Err(s) = e.step() {
                assert!(expected.is_object(), "{}: {s}", path.display());
                assert_eq!(s.status, expected["status"]);
                assert_eq!(s.axis, expected["axis"]);
                assert_eq!(e.time(), expected["step"].as_i64().unwrap());
                stopped = true;
                break;
            }
        }
        assert_eq!(stopped, expected.is_object(), "{}", path.display());
    }
}
#[test]
fn delta_rejects_conflicts_arrays_and_noops() {
    let a = json!({"a":{"b":1},"c":[1,2]});
    let b = json!({"a":{"b":2},"c":[1,3]});
    let d = delta(&a, &b).unwrap();
    assert_eq!(apply_delta(&a, &d).unwrap(), b);
    let mut dup = d.clone();
    dup.push(d[0].clone());
    assert!(apply_delta(&a, &dup).is_err());
    assert!(apply_delta(&a, &[json!({"op":"replace","path":["c","0"],"value":3})]).is_err());
}

fn coverage_of(mut e: Engine, steps: usize) -> Vec<Value> {
    let mut rows = vec![];
    for _ in 0..steps {
        let report = e.step().unwrap();
        rows.push(step_row(&e, &report));
    }
    coverage(&config(), &rows, &e.input)
}
fn status(rows: &[Value], axis: &str) -> String {
    rows.iter().find(|r| r["axis"] == axis).unwrap()["coverage_status"]
        .as_str()
        .unwrap()
        .into()
}
#[test]
fn coverage_distinguishes_first_success_singleton_and_existing_cursor() {
    let mut r = crate::tests_graph::fork();
    put_seed(&mut r, "s:transport:0", "源矿", 1, Some(-8));
    let rows = coverage_of(engine(r.clone()), 1);
    assert_eq!(status(&rows, "polling.split_merge_start"), "exercised");
    assert_eq!(
        status(&rows, "polling.split_merge_singleton"),
        "not_exercised"
    );
    assert_eq!(status(&rows, "polling.initial_cursor"), "not_exercised");
    let i = parse(r.clone()).unwrap();
    let ch = i.graph.components[i.graph.index["C|s"]].outputs[0].clone();
    for cursor in state(&mut r)["logistics"]["poll_state"]["cursors"]
        .as_array_mut()
        .unwrap()
    {
        if cursor["side"] == "C|s:output" {
            cursor["last_success"] = json!(ch);
        }
    }
    let rows = coverage_of(engine(r), 1);
    assert_eq!(status(&rows, "polling.split_merge_start"), "not_exercised");
    let mut r = raw(&[
        ("s", "分流器", 10, 10, 0, 0),
        ("n", "物品准入口", 10, 11, 0, 0),
    ]);
    put_seed(&mut r, "s:transport:0", "源矿", 1, Some(-8));
    let rows = coverage_of(engine(r), 1);
    assert_eq!(status(&rows, "polling.split_merge_singleton"), "exercised");
    assert_eq!(status(&rows, "polling.split_merge_start"), "not_exercised");
}
#[test]
fn coverage_ordinary_cursor_requires_no_prior_success() {
    for initialized in [false, true] {
        let mut r = raw(&[
            ("m", "粉碎机", 10, 10, 0, 0),
            ("a", "物品准入口", 10, 9, 0, 0),
            ("b", "物品准入口", 11, 9, 0, 0),
            ("power", "供电桩", 14, 10, 0, 0),
        ]);
        put_seed(&mut r, "a:transport:0", "源矿", 1, Some(-8));
        put_seed(&mut r, "b:transport:0", "源矿", 1, Some(-8));
        let i = parse(r.clone()).unwrap();
        let ch = i.graph.inputs_nt["m"][0].clone();
        assert_eq!(i.graph.inputs_nt["m"].len(), 2);
        if initialized {
            for cursor in state(&mut r)["logistics"]["poll_state"]["cursors"]
                .as_array_mut()
                .unwrap()
            {
                if cursor["side"] == "m:input" {
                    cursor["last_success"] = json!(ch);
                }
            }
        }
        let rows = coverage_of(engine(r), 1);
        assert_eq!(
            status(&rows, "polling.initial_cursor"),
            if initialized {
                "not_exercised"
            } else {
                "exercised"
            }
        );
        assert_eq!(
            status(&rows, "polling.split_merge_singleton"),
            "not_exercised"
        );
    }
}
#[test]
fn coverage_does_not_infer_manufacturing_family_or_partial_transfer() {
    let rows = coverage_of(Engine::new(sample("a-纯链")).unwrap(), 64);
    assert_eq!(
        status(&rows, "manufacturing.recipe_completeness"),
        "exercised"
    );
    for axis in [
        "manufacturing.output_blocked",
        "manufacturing.input_mixing",
        "manufacturing.empty_slot_identity",
    ] {
        assert_eq!(status(&rows, axis), "not_exercised", "{axis}");
    }
    for (case, partial) in [
        ("无线空箱", false),
        ("无线全拒收", false),
        ("无线多格全收", false),
        ("无线部分接收", true),
    ] {
        let i = Input::load(
            &root().join(format!("数据/样例/步进/机制/{case}.json")),
            &config(),
        )
        .unwrap();
        let rows = coverage_of(Engine::new(i).unwrap(), 1);
        assert_eq!(status(&rows, "transfer.judgment"), "exercised");
        assert_eq!(status(&rows, "transfer.failure_cooldown"), "exercised");
        assert_eq!(
            status(&rows, "transfer.partial_acceptance"),
            if partial {
                "exercised"
            } else {
                "not_exercised"
            },
            "{case}"
        );
        assert_eq!(status(&rows, "transfer.pause"), "not_exercised");
    }
}
