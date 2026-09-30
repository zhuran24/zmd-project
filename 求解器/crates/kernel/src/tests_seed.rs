use crate::{tests_support::*, value::*, Engine};
use serde_json::{json, Value};
fn rejected(r: Value) -> crate::Stop {
    match parse(r).and_then(Engine::new) {
        Err(e) => e,
        Ok(_) => panic!("invalid seed accepted"),
    }
}
#[test]
fn time_domain_and_transport_timestamp_rejections() {
    for entered in [None, Some(1)] {
        let mut r = chain();
        put_seed(&mut r, "b0:transport:0", "源矿", 1, entered);
        assert_eq!(rejected(r).status, "invalid_input");
    }
    let mut r = chain();
    state(&mut r)["environment"]["time"]["kind"] = json!("rational");
    assert_eq!(rejected(r).axis, "time.domain");
    assert!(Quantity {
        value: "1/8".into(),
        category: "候选".into()
    }
    .integer("n")
    .is_err());
    assert!(Quantity {
        value: "--1".into(),
        category: "候选".into()
    }
    .integer("n")
    .is_err());
}
#[test]
fn ordinary_timestamps_last_unit_and_duplicate_rows_are_rejected() {
    let mut r = chain();
    put_seed(&mut r, "m:input:0", "源矿", 1, Some(0));
    assert_eq!(rejected(r).status, "invalid_input");
    let mut r = chain();
    put_seed(&mut r, "b0:transport:0", "源矿", 1, Some(0));
    let row = state(&mut r)["inventory"]
        .as_array_mut()
        .unwrap()
        .iter_mut()
        .find(|r| r["slot"] == "b0:transport:0")
        .unwrap();
    row["contents"][0]["last_unit"] = json!("source");
    assert_eq!(rejected(r).status, "invalid_input");
    let mut r = chain();
    put_seed(&mut r, "m:input:0", "源矿", 1, None);
    put_seed(&mut r, "m:input:0", "源矿", 1, None);
    assert_eq!(rejected(r).status, "invalid_input");
}
#[test]
fn poll_state_missing_extra_and_wrong_members() {
    let original = raw(&[
        ("s", "分流器", 10, 10, 0, 0),
        ("a", "传送带", 10, 11, 0, 0),
        ("b", "传送带", 11, 10, 270, 0),
    ]);
    for kind in 0..3 {
        let mut r = original.clone();
        let c = &mut state(&mut r)["logistics"]["poll_state"]["cursors"];
        match kind {
            0 => *c = json!([]),
            1 => {
                let duplicate = c[0].clone();
                c.as_array_mut().unwrap().push(duplicate);
            }
            _ => c[0]["last_success"] = json!("unknown"),
        };
        assert_eq!(rejected(r).status, "invalid_input");
    }
}
#[test]
fn expired_gate_window_and_bad_progress() {
    let mut r = raw(&[("g", "物品准入口", 10, 10, 0, 0)]);
    state(&mut r)["logistics"]["gate_counters"][0] = json!({"unit":"g","total_received":q(1),"window_received":q(1),"window_started_at":tv(-40)});
    assert_eq!(rejected(r).status, "invalid_input");
    for remaining in [0, 9] {
        let mut r = chain();
        put_seed(&mut r, "m:buffer:0", "源矿", 1, None);
        let p = progress(&mut r, "m");
        p["phase"] = json!("working");
        p["recipe"] = json!("粉碎-源矿");
        p["remaining"] = tv(remaining);
        assert_eq!(rejected(r).status, "invalid_input");
    }
    let mut r = chain();
    progress(&mut r, "m")["phase"] = json!("intake");
    assert_eq!(rejected(r).status, "invalid_input");
}
#[test]
fn old_schema_and_future_build_rejected() {
    let mut r = chain();
    r["schema"] = json!("kernel-input-v3");
    assert_eq!(rejected(r).status, "invalid_input");
    let mut r = chain();
    state(&mut r)["environment"]["time"] = tv(-100);
    assert_eq!(rejected(r).status, "invalid_input");
}
#[test]
fn no_op_failed_judgements_do_not_consume_event_ids() {
    let mut e = engine(chain());
    for r in advance(&mut e, 40) {
        for (i, event) in r.events.iter().enumerate() {
            assert_eq!(event.event, format!("E|{}|{i}", r.step));
            assert!(
                !event.moves.is_empty()
                    || event.phase != "judge"
                    || event
                        .detail
                        .as_ref()
                        .is_some_and(|v| v.get("transfer").is_some())
            );
        }
    }
}
#[test]
fn offline_stops_before_any_step_effect() {
    let mut r = chain();
    r["timeline"]["events"]
        .as_array_mut()
        .unwrap()
        .push(json!({"id":"offline1","kind":"offline","time":tv(2)}));
    r["environment"]["offline"]["selected_events"] =
        json!([{"event":"offline1","new_connection_order":d(json!([])),"effects":d(json!({}))}]);
    let mut e = engine(r);
    advance(&mut e, 2);
    let before = e.state.clone();
    let stop = e.step().unwrap_err();
    assert_eq!(stop.axis, "offline.events");
    assert_eq!(e.state, before);
    assert_eq!(e.step().unwrap_err(), stop);
}
#[test]
fn invalid_recency_and_reserved_runtime_identity_are_rejected() {
    let mut r = chain();
    state(&mut r)["logistics"]["poll_state"]["recency"] = json!([{"unit":"m","order":[]}]);
    assert_eq!(rejected(r).status, "invalid_input");
    let mut r = chain();
    r["timeline"]["events"][0]["id"] = json!("E|0|0");
    assert_eq!(rejected(r).status, "invalid_input");
}
