use crate::{graph::*, tests_support::*};
use serde_json::json;
pub fn fork() -> serde_json::Value {
    raw(&[
        ("s", "分流器", 10, 10, 0, 0),
        ("n", "物品准入口", 10, 11, 0, 0),
        ("e", "物品准入口", 11, 10, 270, 0),
        ("bn", "协议储存箱", 9, 12, 0, 0),
        ("be", "协议储存箱", 12, 9, 270, 0),
    ])
}
pub fn ring() -> serde_json::Value {
    raw(&[
        ("a", "传送带", 10, 10, 180, 2),
        ("b", "传送带", 11, 10, 270, 2),
        ("c", "传送带", 11, 11, 0, 2),
        ("d", "传送带", 10, 11, 90, 2),
    ])
}
#[test]
fn belt_partition_and_layers() {
    let i = parse(chain()).unwrap();
    let g = i.graph;
    let c = &g.components[g.index["C|b1"]];
    assert_eq!(c.cells, ["b0:transport:0", "b1:transport:0"]);
    assert_eq!(c.kind, ComponentKind::BeltChain);
    assert_eq!(g.layers[g.index["C|b1"]], 1);
    assert_eq!(c.inputs.len(), 1);
    assert_eq!(c.outputs.len(), 1);
    let r = parse(ring()).unwrap();
    assert_eq!(r.graph.components.len(), 1);
    assert_eq!(r.graph.components[0].id, "C|ring|a");
    assert_eq!(r.graph.components[0].kind, ComponentKind::BeltRing);
    assert!(r.graph.components[0].outputs.is_empty());
}
#[test]
fn branch_explicit_missing_and_invalid() {
    let original = fork();
    let i = parse(original.clone()).unwrap();
    let g = &i.graph;
    assert_eq!(g.candidates()[g.index["C|s"]].len(), 2);
    assert_eq!(g.layers[g.index["C|s"]], 2);
    let mut r = original.clone();
    let mut o = axis(&r, "step.order").clone();
    o["layer_choices"] = json!([]);
    set_axis(&mut r, "step.order", o);
    let e = parse(r).unwrap_err();
    assert_eq!(e.status, "unresolved");
    assert_eq!(e.axis, "step.order");
    let mut r = original;
    let mut o = axis(&r, "step.order").clone();
    o["layer_choices"][0]["downstream"] = json!("C|s");
    set_axis(&mut r, "step.order", o);
    assert_eq!(parse(r).unwrap_err().status, "invalid_input");
}
#[test]
fn bridge_axes_cycle_and_noncycle_anchors() {
    let original = raw(&[("a", "桥接器", 10, 10, 0, 0), ("b", "桥接器", 11, 10, 0, 0)]);
    let i = parse(original.clone()).unwrap();
    assert_eq!(i.graph.components.len(), 4);
    let g = &i.graph;
    assert_eq!(g.layers[g.index["C|a|horizontal"]], 1);
    assert_eq!(g.layers[g.index["C|b|horizontal"]], 2);
    let mut r = original.clone();
    let mut o = axis(&r, "step.order").clone();
    o["cycle_layers"] = json!([]);
    set_axis(&mut r, "step.order", o);
    assert_eq!(parse(r).unwrap_err().status, "unresolved");
    let mut r = original;
    let mut o = axis(&r, "step.order").clone();
    o["cycle_layers"][0]["component"] = json!("C|a|vertical");
    set_axis(&mut r, "step.order", o);
    assert_eq!(parse(r).unwrap_err().status, "invalid_input");
}
#[test]
fn fixed_component_and_nontransport_orders() {
    let r = raw(&[
        ("box_a", "协议储存箱", 10, 10, 0, 0),
        ("box_b", "协议储存箱", 15, 10, 0, 0),
        ("out_a", "传送带", 11, 13, 0, 0),
        ("out_b", "传送带", 16, 13, 0, 0),
    ]);
    let i = parse(r.clone()).unwrap();
    let labels: Vec<_> = i.graph.order.iter().map(|s| i.graph.label(s)).collect();
    assert_eq!(&labels[..2], ["C|out_a", "C|out_b"]);
    let mut r = r;
    let mut o = axis(&r, "step.order").clone();
    o["nontransport_order"] = json!(["box_b", "box_a", "core"]);
    set_axis(&mut r, "step.order", o);
    assert_eq!(parse(r).unwrap_err().status, "invalid_input");
}
#[test]
fn no_outgoing_components_do_not_count_as_layer_candidates() {
    let r = raw(&[
        ("s", "分流器", 10, 10, 0, 0),
        ("tail", "物品准入口", 10, 11, 0, 0),
    ]);
    let i = parse(r).unwrap();
    assert_eq!(i.graph.layers[i.graph.index["C|s"]], 1);
    assert!(i.graph.candidates()[i.graph.index["C|s"]].is_empty());
}

fn same_step_builds(r: &mut serde_json::Value) {
    for event in r["timeline"]["events"].as_array_mut().unwrap() {
        if event["kind"] == "build" || event["kind"] == "connection_open" {
            event["time"] = crate::value::tv(-1);
        }
    }
}
#[test]
fn same_step_connection_tie_respects_sequential_builds() {
    let mut r = chain();
    let input = parse(r.clone()).unwrap();
    let mut channels = input.tie_order.clone();
    channels.sort_by_key(|c| input.connection_times[c]);
    same_step_builds(&mut r);
    set_axis(
        &mut r,
        "connection.tie",
        json!({"kind":"explicit_order","channels":channels}),
    );
    parse(r.clone()).unwrap();
    channels.reverse();
    set_axis(
        &mut r,
        "connection.tie",
        json!({"kind":"explicit_order","channels":channels}),
    );
    let error = parse(r).unwrap_err();
    assert_eq!(error.status, "invalid_input");
    assert_eq!(error.axis, "connection.tie");
}
#[test]
fn one_build_can_open_channels_in_either_tie_order() {
    let mut r = raw(&[("a", "桥接器", 10, 10, 0, 0), ("b", "桥接器", 11, 10, 0, 0)]);
    same_step_builds(&mut r);
    let mut channels = axis(&r, "connection.tie")["channels"]
        .as_array()
        .unwrap()
        .clone();
    assert_eq!(channels.len(), 2);
    parse(r.clone()).unwrap();
    channels.reverse();
    set_axis(
        &mut r,
        "connection.tie",
        json!({"kind":"explicit_order","channels":channels}),
    );
    parse(r).unwrap();
}
#[test]
fn component_identity_collision_is_rejected_before_indexing() {
    let r = raw(&[
        ("horizontal", "传送带", 10, 10, 180, 2),
        ("z1", "传送带", 11, 10, 270, 2),
        ("z2", "传送带", 11, 11, 0, 2),
        ("z3", "传送带", 10, 11, 90, 2),
        ("cross", "桥接器", 20, 20, 0, 0),
    ]);
    parse(r.clone()).unwrap();
    let r = serde_json::from_str(&r.to_string().replace("cross", "ring")).unwrap();
    let error = parse(r).unwrap_err();
    assert_eq!(error.status, "invalid_input");
    assert_eq!(error.location, "C|ring|horizontal");
    assert_eq!(error.reason, "元件身份重复");
}
#[test]
fn equal_layer_connection_order_overrides_component_name_order() {
    let mut r = raw(&[
        ("m", "汇流器", 10, 11, 0, 0),
        ("z", "物品准入口", 10, 10, 0, 0),
        ("a", "物品准入口", 9, 11, 270, 0),
        ("out", "传送带", 10, 12, 0, 0),
    ]);
    put_seed(&mut r, "z:transport:0", "源矿", 1, Some(-8));
    put_seed(&mut r, "a:transport:0", "蓝铁矿", 1, Some(-8));
    let mut e = engine(r);
    let g = &e.input.graph;
    assert_eq!(g.layers[g.index["C|z"]], g.layers[g.index["C|a"]]);
    let order: Vec<_> = g.order.iter().map(|s| g.label(s)).collect();
    assert!(order.iter().position(|s| s == "C|z") < order.iter().position(|s| s == "C|a"));
    let report = e.step().unwrap();
    let moved = report
        .events
        .iter()
        .find(|event| !event.moves.is_empty())
        .unwrap();
    assert_eq!(moved.subject, "C|z");
    // 两上游被同组带动；汇流器首次按第二条接通的 a 通道收货。
    assert!(moved.moves[0].channel.contains("a:"));
}
