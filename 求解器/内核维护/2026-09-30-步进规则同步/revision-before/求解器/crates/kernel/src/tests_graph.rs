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
