//! 规则 743f18b：永久双向桥、来路守卫和逐轴调度。
use super::*;
use crate::catalog::Geometry;
use std::collections::BTreeSet;

fn unit(id: &str, kind: &str, x: i64, y: i64, rotation: &str) -> Value {
    json!({"id":id,"kind":kind,"origin":[q(x),q(y)],"rotation":rotation,
        "port_layout":if kind=="桥接器" {Value::Null} else {json!(0)},
        "bridge_axes":null,"occupied_cells":null})
}

// 构造显式有限历史和空种子；所有案例经过公开解析、派生及严格装载。
fn case(extra: Vec<Value>) -> Engine {
    let original = fixture("bridge");
    let path = original.input.path.clone();
    let cat = &original.input.catalog;
    let mut raw = original.input.raw.clone();
    let mut units = vec![raw["layout"]["units"][0].clone()];
    units.extend(extra);
    units.sort_by_key(|u| u["kind"] == "传送带");
    raw["layout"]["units"] = json!(units);
    raw["layout"]["physical_channels"] = Value::Null;
    raw["layout"]["buffer_channels"] = json!([]);
    raw["scenario"] =
        json!({"name":"bridge_rules","recipe_intents":[],"expected_paths":[],"assertions":[]});
    raw["settings"]["switches"] = json!([]);
    let geometry = Geometry::build(&raw["layout"], cat).unwrap();
    raw["layout"]["physical_channels"] = json!(geometry.channels.values().collect::<Vec<_>>());
    let n = units.len() as i64;
    let rank: BTreeMap<_, _> = units
        .iter()
        .enumerate()
        .map(|(i, u)| (u["id"].as_str().unwrap().to_string(), i))
        .collect();
    let mut events = vec![];
    let mut moments = vec![];
    let mut relations = vec![];
    let mut connections = vec![];
    for (i, u) in units.iter().enumerate() {
        events.push(json!({"id":format!("build_{i}"),"kind":"build","time":tv(i as i64-n)}));
        let placement: serde_json::Map<String, Value> = [
            "kind",
            "origin",
            "rotation",
            "port_layout",
            "occupied_cells",
        ]
        .into_iter()
        .map(|k| (k.into(), u[k].clone()))
        .collect();
        moments.push(json!({"unit":u["id"],"event":format!("build_{i}"),"placement":placement}));
        relations.push(json!({"before":format!("build_{i}"),"after":if i+1<units.len() {format!("build_{}",i+1)} else {"blueprint_complete".into()},"relation":"strict","basis":["测试显式建造史"]}));
    }
    for id in ["blueprint_complete", "debug_end"] {
        events.push(json!({"id":id,"kind":id,"time":tv(0)}));
    }
    relations.push(json!({"before":"blueprint_complete","after":"debug_end","relation":"occurs_before","basis":["测试阶段顺序"]}));
    for (i, c) in geometry.channels.values().enumerate() {
        let a = rank[&geometry.ports[&c.source_port].unit];
        let b = rank[&geometry.ports[&c.target_port].unit];
        let later = a.max(b);
        let id = format!("connect_{i}");
        events.push(json!({"id":id,"kind":"connection_open","time":tv(later as i64-n)}));
        connections.push(json!({"event":id,"channel":c.id,"action":"open","cause":format!("build_{later}"),
            "geometry_snapshot":raw["layout"]["id"],"construction_basis":Decision::specified(json!({"source_build":format!("build_{a}"),"target_build":format!("build_{b}"),"later_build":format!("build_{later}")}),"规则L28")}));
    }
    raw["construction"]["selected_order"] =
        json!(units.iter().map(|u| &u["id"]).collect::<Vec<_>>());
    raw["construction"]["moments"] = json!(moments);
    raw["timeline"] =
        json!({"events":events,"relations":relations,"connection_events":connections});
    set_axis(
        &mut raw,
        "connection.belt_shape",
        json!({"kind":"layout_build_history","values":units.iter().filter(|u|u["kind"]=="传送带").map(|u|json!({"unit":u["id"],"build_event":format!("build_{}",rank[u["id"].as_str().unwrap()]),"shape":"straight"})).collect::<Vec<_>>()}),
    );
    set_axis(
        &mut raw,
        "transfer.phase",
        json!({"kind":"explicit_residuals","values":[]}),
    );
    set_axis(
        &mut raw,
        "connection.tie",
        json!({"kind":"explicit_order","channels":geometry.channels.keys().collect::<Vec<_>>()}),
    );
    set_axis(
        &mut raw,
        "judgment.order",
        json!({"schema":"event-order-v1","scope":"global","template_order":geometry.channels.keys().map(|c|json!({"operation":"move","target":c})).collect::<Vec<_>>(),"repeat_embedding":"scan_round_then_template","instant_overrides":[]}),
    );
    set_axis(
        &mut raw,
        "warehouse.external_supply",
        json!({"kind":"sufficient"}),
    );
    let state = &mut raw["initial_state"]["nonwarehouse"]["value"];
    state["inventory"] = json!(cat
        .slots(&geometry.units, 1)
        .unwrap()
        .keys()
        .map(|s| json!({"slot":s,"contents":[]}))
        .collect::<Vec<_>>());
    state["progress"] = json!([]);
    state["logistics"]["poll_memory"]["value"]["sides"] = json!([]);
    let mut levels = BTreeSet::new();
    for c in geometry.channels.values() {
        for (port, peer, side) in [
            (&c.source_port, &c.target_port, "output"),
            (&c.target_port, &c.source_port, "input"),
        ] {
            let p = &geometry.ports[port];
            let graded =
                side == "input" || cat.kinds[&geometry.units[&p.unit].kind].family != "transport";
            let direct = graded
                && geometry.units[&geometry.ports[peer].unit].kind
                    == if side == "input" {
                        "分流器"
                    } else {
                        "汇流器"
                    };
            let category = if direct {
                format!("direct:{}", c.id)
            } else if graded {
                "other".into()
            } else {
                "ungraded".into()
            };
            let axis = p.axis.as_ref().map(|a| format!("|{a}")).unwrap_or_default();
            levels.insert(format!("L|{}{axis}|{side}|{category}", p.unit));
        }
    }
    state["semantic_context"]["arbitration"]["level_order"] = json!(levels);
    let raw = Input::canonicalize_seed(raw, path.parent().unwrap(), &config()).unwrap();
    Engine::new(Input::parse(raw, &path, &config(), false).unwrap()).unwrap()
}

fn advance(e: &mut Engine, ticks: usize) {
    for _ in 0..ticks {
        e.step(true).unwrap();
    }
}

#[test]
fn bridge_axis_straight_through() {
    let mut e = case(vec![
        unit("b", "桥接器", 10, 10, "r0"),
        unit("feed", "传送带", 10, 9, "r0"),
        unit("exit", "传送带", 10, 11, "r0"),
    ]);
    put(&mut e, "feed:transport:0", "源矿", 1);
    advance(&mut e, 2);
    assert_eq!(count(&e, "b:vertical:0"), 1);
    assert_eq!(count(&e, "exit:transport:0"), 0);
    advance(&mut e, 1);
    assert_eq!(count(&e, "exit:transport:0"), 1);
    assert_eq!(count(&e, "b:horizontal:0"), 0);
}

#[test]
fn bridge_two_inward_belts_both_connect_and_trap_one_item() {
    let mut e = case(vec![
        unit("b", "桥接器", 10, 10, "r0"),
        unit("south", "传送带", 10, 9, "r0"),
        unit("north", "传送带", 10, 11, "r180"),
    ]);
    assert_eq!(e.input.geometry.channels.len(), 2);
    assert!(e
        .input
        .geometry
        .channels
        .values()
        .all(|c| e.input.geometry.ports[&c.target_port].unit == "b"));
    put(&mut e, "south:transport:0", "源矿", 1);
    put(&mut e, "north:transport:0", "蓝铁矿", 1);
    let total = e.inventory_totals().unwrap();
    advance(&mut e, 8);
    assert_eq!(count(&e, "b:vertical:0"), 1);
    assert_eq!(
        count(&e, "south:transport:0") + count(&e, "north:transport:0"),
        1
    );
    assert_eq!(e.inventory_totals().unwrap(), total);
}

#[test]
fn adjacent_empty_bridges_form_both_directions_for_all_rotations() {
    for rotation in ["r0", "r90", "r180", "r270"] {
        let mut e = case(vec![
            unit("a", "桥接器", 10, 10, "r0"),
            unit("b", "桥接器", 11, 10, rotation),
        ]);
        assert_eq!(e.input.geometry.channels.len(), 2);
        assert_eq!(
            e.input
                .geometry
                .channels
                .values()
                .map(|c| (
                    &e.input.geometry.ports[&c.source_port].unit,
                    &e.input.geometry.ports[&c.target_port].unit
                ))
                .collect::<BTreeSet<_>>(),
            BTreeSet::from([(&"a".into(), &"b".into()), (&"b".into(), &"a".into())])
        );
        advance(&mut e, 2);
        assert!(e.state.inventory.iter().all(|r| r.contents.is_empty()));
    }
}

#[test]
fn adjacent_bridge_item_never_returns_after_checkpoint() {
    for reversed in [false, true] {
        let mut e = case(vec![
            unit("a", "桥接器", 10, 10, "r0"),
            unit("b", "桥接器", 11, 10, "r90"),
        ]);
        let (from, to, slot) = if reversed {
            ("b", "a", "b:vertical:0")
        } else {
            ("a", "b", "a:horizontal:0")
        };
        put(&mut e, slot, "源矿", 1);
        let total = e.inventory_totals().unwrap();
        advance(&mut e, 2);
        let occupied = e
            .state
            .inventory
            .iter()
            .find(|r| !r.contents.is_empty())
            .unwrap();
        assert!(occupied.slot.starts_with(to));
        assert_eq!(occupied.contents[0].last_unit.as_deref(), Some(from));
        let mut e = reload(e);
        let reverse = e
            .input
            .geometry
            .channels
            .iter()
            .find(|(_, c)| e.input.geometry.ports[&c.source_port].unit == to)
            .unwrap()
            .0
            .clone();
        assert_eq!(e.physical(&reverse).unwrap().1, "immediate_return");
        advance(&mut e, 8);
        assert_eq!(count(&e, slot), 0);
        assert_eq!(e.inventory_totals().unwrap(), total);
    }
}

#[test]
fn adjacent_bridges_pass_forward_and_damping_ignores_reverse_edge() {
    let mut e = case(vec![
        unit("a", "桥接器", 10, 10, "r0"),
        unit("b", "桥接器", 10, 11, "r0"),
        unit("feed", "传送带", 10, 9, "r0"),
        unit("exit", "传送带", 10, 12, "r0"),
    ]);
    put(&mut e, "feed:transport:0", "源矿", 1);
    advance(&mut e, 4);
    assert_eq!(count(&e, "exit:transport:0"), 1);
    assert_eq!(count(&e, "a:vertical:0"), 0);
    assert_eq!(count(&e, "b:vertical:0"), 0);
    // 悬空出口没有终点应为 unresolved，不能因反向 PC 误报多出边。
    let err = e.damping("PC|feed:north:0|a:south:0").unwrap_err();
    assert_eq!(err.axis, "damping.no_terminal");
}

#[test]
fn direct_splitter_on_one_bridge_axis_does_not_block_other_axis() {
    let mut e = case(vec![
        unit("b", "桥接器", 10, 10, "r0"),
        unit("split", "分流器", 10, 9, "r0"),
        unit("west", "传送带", 9, 10, "r270"),
        unit("north", "传送带", 10, 11, "r0"),
        unit("east", "传送带", 11, 10, "r270"),
    ]);
    put(&mut e, "split:transport:0", "源矿", 1);
    put(&mut e, "west:transport:0", "蓝铁矿", 1);
    e = reload(e);
    let sides: Vec<_> = e.memory.sides.iter().filter(|s| s.unit == "b").collect();
    assert_eq!(sides.len(), 4);
    for s in &sides {
        for l in &s.levels {
            for cid in &l.members {
                let c = &e.input.geometry.channels[cid];
                let p = if s.side == "input" {
                    &c.target_port
                } else {
                    &c.source_port
                };
                assert_eq!(e.input.geometry.ports[p].axis, s.axis);
            }
        }
    }
    advance(&mut e, 2);
    assert_eq!(count(&e, "b:vertical:0"), 1);
    assert_eq!(count(&e, "b:horizontal:0"), 1);
    advance(&mut e, 1);
    assert_eq!(count(&e, "north:transport:0"), 1);
    assert_eq!(count(&e, "east:transport:0"), 1);
}

#[test]
fn bridge_capacity_and_legacy_direction_are_rejected() {
    let mut e = case(vec![unit("b", "桥接器", 10, 10, "r0")]);
    assert!(e.put("b:vertical:0", "源矿", 2).is_err());
    put(&mut e, "b:vertical:0", "源矿", 1);
    put(&mut e, "b:horizontal:0", "源矿", 1);
    e.validate_inventory().unwrap();
    let mut raw = e.input.raw.clone();
    raw["layout"]["units"][1]["bridge_axes"] =
        json!({"vertical":{"status":"resolved","input_side":"south","basis":["旧方向"]}});
    assert!(Input::parse(raw, &e.input.path, &config(), false)
        .unwrap_err()
        .reason
        .contains("bridge_axes"));
}

#[test]
fn bridge_previous_unit_is_preserved_in_cycle_key_and_validated() {
    let mut e = case(vec![
        unit("a", "桥接器", 10, 10, "r0"),
        unit("b", "桥接器", 11, 10, "r0"),
        unit("c", "桥接器", 12, 10, "r0"),
    ]);
    put(&mut e, "b:horizontal:0", "源矿", 1);
    e.state.inventory[e.inv["b:horizontal:0"]].contents[0].last_unit = Some("a".into());
    e = reload(e);
    advance(&mut e, 1);
    let mut other = e.state.clone();
    other.inventory[e.inv["b:horizontal:0"]].contents[0].last_unit = Some("c".into());
    assert_ne!(
        crate::cycle::cycle_key(&e.state, &e.input).unwrap(),
        crate::cycle::cycle_key(&other, &e.input).unwrap()
    );
    e.state.inventory[e.inv["b:horizontal:0"]].contents[0].last_unit = Some("core".into());
    assert!(e.validate_inventory().unwrap_err().reason.contains("来路"));
}
