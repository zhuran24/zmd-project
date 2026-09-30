use crate::{tests_support::*, value::*};
use serde_json::json;
fn box_input() -> serde_json::Value {
    raw(&[
        ("box", "协议储存箱", 10, 10, 0, 0),
        ("out", "传送带", 11, 13, 0, 0),
        ("power", "供电桩", 14, 10, 0, 0),
    ])
}
#[test]
fn transfer_before_or_after_port_send() {
    for timing in ["before_send", "after_send"] {
        let mut r = box_input();
        put_seed(&mut r, "box:storage:0", "源石粉末", 5, None);
        set_axis(
            &mut r,
            "transfer.timing",
            json!({"schema":"transfer-timing-v1","values":[{"unit":"box","timing":timing}]}),
        );
        let mut e = engine(r);
        e.step().unwrap();
        assert_eq!(
            count(&e, "out:transport:0"),
            i64::from(timing == "after_send")
        );
        assert_eq!(
            e.delivery["源石粉末"],
            if timing == "after_send" { 4 } else { 5 }
        );
        assert_eq!(
            e.state.progress[e.progress["box"]]
                .cooldown
                .as_ref()
                .unwrap()
                .integer("box")
                .unwrap(),
            40
        );
    }
}
#[test]
fn empty_and_rejected_transfers_restart_forty_steps() {
    for full in [false, true] {
        let mut r = box_input();
        if full {
            put_seed(&mut r, "box:storage:0", "源矿", 1, None);
            put_seed(&mut r, "out:transport:0", "蓝铁矿", 1, Some(0));
        }
        let mut e = engine(r);
        let reports = advance(&mut e, 81);
        let attempts: Vec<_> = reports
            .iter()
            .filter(|r| {
                r.events.iter().any(|e| {
                    e.detail
                        .as_ref()
                        .is_some_and(|d| d.get("transfer").is_some())
                })
            })
            .map(|r| r.step)
            .collect();
        assert_eq!(attempts, [0, 40, 80]);
        assert!(e.delivery.values().all(|n| *n == 0));
    }
}
#[test]
fn partial_receipt_and_ambiguous_multislot_stop() {
    let mut r = box_input();
    put_seed(&mut r, "box:storage:0", "源矿", 10, None);
    state(&mut r)["warehouse"]["slots"][0]["quantity"] = q(79997);
    let mut e = engine(r);
    e.step().unwrap();
    assert_eq!(e.delivery["源矿"], 3);
    assert_eq!(count(&e, "box:storage:0"), 6);
    let mut r = box_input();
    put_seed(&mut r, "box:storage:0", "源矿", 10, None);
    put_seed(&mut r, "box:storage:1", "源矿", 10, None);
    state(&mut r)["warehouse"]["slots"][0]["quantity"] = q(79997);
    let mut e = engine(r);
    let before = e.state.clone();
    let stop = e.step().unwrap_err();
    assert_eq!(stop.axis, "transfer.partial_acceptance");
    assert_eq!(e.state.warehouse, before.warehouse);
    assert_eq!(e.step().unwrap_err(), stop);
}
fn gate() -> serde_json::Value {
    raw(&[
        ("source", "仓库取货口", 10, 0, 0, 0),
        ("g", "物品准入口", 11, 1, 0, 0),
        ("b", "传送带", 11, 2, 0, 0),
        ("box", "协议储存箱", 10, 3, 0, 0),
    ])
}
#[test]
fn gate_identity_total_and_static_order() {
    let mut r = gate();
    r["settings"]["gates"][0]["item"] = json!("蓝铁矿");
    let mut e = engine(r);
    let graph = e.graph().order.clone();
    assert!(moves(&advance(&mut e, 16)).is_empty());
    assert_eq!(e.graph().order, graph);
    let mut r = gate();
    r["settings"]["gates"][0]["item"] = json!("源矿");
    r["settings"]["gates"][0]["total_limit"] = q(2);
    let mut e = engine(r);
    let layers = e.graph().layers.clone();
    advance(&mut e, 64);
    assert_eq!(
        e.state.logistics.gate_counters[0]
            .total_received
            .integer("g")
            .unwrap(),
        2
    );
    assert_eq!(e.graph().layers, layers);
}
#[test]
fn gate_window_covers_zero_through_thirty_nine_then_reopens() {
    let mut r = gate();
    r["settings"]["gates"][0]["item"] = json!("源矿");
    r["settings"]["gates"][0]["window_limit"] = q(1);
    let mut e = engine(r);
    advance(&mut e, 39);
    assert_eq!(
        e.state.logistics.gate_counters[0]
            .window_received
            .integer("g")
            .unwrap(),
        1
    );
    e.step().unwrap();
    assert_eq!(e.time(), 40);
    assert!(e.state.logistics.gate_counters[0]
        .window_started_at
        .is_none());
    assert_eq!(
        e.state.logistics.gate_counters[0]
            .window_received
            .integer("g")
            .unwrap(),
        0
    );
    e.step().unwrap();
    assert_eq!(
        e.state.logistics.gate_counters[0].window_started_at,
        Some(Time::at(40))
    );
    assert_eq!(
        e.state.logistics.gate_counters[0]
            .total_received
            .integer("g")
            .unwrap(),
        2
    );
}
#[test]
fn gate_max_limits_come_from_settings_not_window_steps() {
    let mut r = gate();
    r["settings"]["gates"][0]["item"] = json!("源矿");
    r["settings"]["gates"][0]["window_limit"] = q(6);
    assert_eq!(parse(r).unwrap_err().status, "invalid_input");
}
#[test]
fn empty_box_receives_and_sends_in_same_step() {
    let mut r = raw(&[
        ("box", "协议储存箱", 10, 10, 0, 0),
        ("in", "传送带", 11, 9, 0, 0),
        ("out", "传送带", 11, 13, 0, 0),
    ]);
    put_seed(&mut r, "in:transport:0", "源矿", 1, Some(-8));
    let mut e = engine(r);
    let all = moves(&advance(&mut e, 1));
    assert_eq!(all.len(), 2);
    assert_eq!(count(&e, "out:transport:0"), 1);
    assert_eq!(count(&e, "box:storage:0"), 0);
}
#[test]
fn disabled_transfer_cooldown_is_frozen() {
    let mut r = box_input();
    switch(&mut r, "box", false);
    progress(&mut r, "box")["cooldown"] = tv(12);
    set_axis(
        &mut r,
        "transfer.phase",
        json!({"kind":"explicit_residuals","values":[{"unit":"box","slot":null,"remaining":tv(12)}]}),
    );
    let mut e = engine(r);
    advance(&mut e, 20);
    assert_eq!(
        e.state.progress[e.progress["box"]].cooldown,
        Some(Time::at(12))
    );
}
#[test]
fn all_slots_can_transfer_and_lowest_receivable_slot_is_used() {
    let mut r = box_input();
    for j in 0..6 {
        put_seed(&mut r, &format!("box:storage:{j}"), "源石粉末", 50, None);
    }
    let mut e = engine(r);
    e.step().unwrap();
    assert_eq!(e.delivery["源石粉末"], 300);
    assert_eq!(e.inventory_totals().unwrap()["源石粉末"], 300);
}
#[test]
fn missing_or_duplicate_transfer_timing_is_invalid() {
    let original = box_input();
    for values in [
        json!([]),
        json!([{"unit":"box","timing":"before_send"},{"unit":"box","timing":"after_send"}]),
    ] {
        let mut r = original.clone();
        set_axis(
            &mut r,
            "transfer.timing",
            json!({"schema":"transfer-timing-v1","values":values}),
        );
        let stop = parse(r).unwrap_err();
        assert_eq!(stop.axis, "transfer.timing");
        assert_eq!(stop.status, "invalid_input");
    }
}
