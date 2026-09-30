use crate::{cycle::checkpoint_input, output::*, tests_support::*, *};
use serde_json::json;
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
