use endfield_sim::{Action, Channel, Counter, CounterPolicy, Event, Kind, LegalBase, Parameters};
use serde_json::json;

fn params(boxes: &[u64]) -> Parameters {
    Parameters {
        powered: vec![],
        ports: vec![],
        transfer_after: boxes.iter().map(|n| (*n, 0)).collect(),
        on_change: CounterPolicy {
            count: Counter::保留,
            quotas: Counter::清空,
        },
        on_offline: CounterPolicy {
            count: Counter::清空,
            quotas: Counter::保留,
        },
    }
}
fn build(u: u64, k: Kind) -> Event {
    Event::Build(u, k)
}
fn edge(a: u64, b: u64) -> Event {
    Event::Connect(Channel(a, b))
}

#[test]
fn checks_compliance_port_history_and_current_paths_separately() {
    use Kind::*;
    assert!(
        LegalBase::new(
            &[build(1, 协议核心), build(2, 协议核心)],
            params(&[]),
            &json!({})
        )
        .is_err()
    );
    let mut history = vec![build(1, 协议储存箱), build(2, 分流器), edge(1, 2)];
    assert!(LegalBase::new(&history, params(&[1]), &json!({})).is_err());
    history.extend([build(3, 桥接器格), edge(2, 3)]);
    assert!(LegalBase::new(&history, params(&[1]), &json!({})).is_err());
    history.extend([build(4, 协议储存箱), edge(3, 4)]);
    assert!(LegalBase::new(&history, params(&[1, 4]), &json!({})).is_ok());
    history.extend([build(5, 协议储存箱), edge(3, 5), Event::Remove(5)]);
    assert!(LegalBase::new(&history, params(&[1, 4]), &json!({})).is_err());
    assert!(LegalBase::new(&[build(1, 传送带)], params(&[]), &json!({})).is_ok());
    assert!(
        LegalBase::new(
            &[build(1, 传送带), build(2, 传送带), edge(1, 2), edge(2, 1)],
            params(&[]),
            &json!({})
        )
        .is_err()
    );
}

#[test]
fn failed_operation_and_illegal_offline_are_atomic() {
    use Kind::*;
    let history = vec![build(1, 传送带), build(2, 协议储存箱), edge(1, 2)];
    let mut base = LegalBase::new(
        &history,
        params(&[2]),
        &json!({"货":[[[1,["格",0]],[["源矿",1]]]],"已停":[[[1,["格",0]],8]]}),
    )
    .unwrap();
    let before = base.snapshot();
    assert!(base.apply(&Action::Switch(vec![2, 1], false)).is_err());
    let mut transient = history.clone();
    transient.extend([build(3, 协议储存箱), edge(1, 3), Event::Remove(3)]);
    assert!(base.apply(&Action::Offline(transient)).is_err());
    assert_eq!(base.snapshot(), before);
    assert_eq!(base.history(), history);
    let reconnected = vec![history[1].clone(), history[0].clone(), history[2].clone()];
    base.apply(&Action::Offline(reconnected.clone())).unwrap();
    assert_eq!(base.history(), reconnected);
    base.step();
    assert_eq!(base.snapshot(), json!({"货":[[[2,["格",0]],[["源矿",1]]]]}));
}

#[test]
fn current_rule_reselects_after_item_reaches_warehouse() {
    // A full merger sends to the box in the element phase. In the same phase
    // the core receives the first warehouse item and makes its outlet eligible.
    use Kind::*;
    let h = vec![
        build(1, 传送带),
        build(2, 协议核心),
        build(3, 汇流器),
        build(4, 协议储存箱),
        edge(1, 2),
        edge(2, 3),
        edge(3, 4),
    ];
    let mut params = params(&[4]);
    params.ports = vec![(Channel(2, 3), 0)];
    let mut base = LegalBase::new(
        &h,
        params,
        &json!({
            "货":[[[1,["格",0]],[["源矿",1]]],[[3,["格",0]],[["钢块",1]]]],
            "已停":[[[1,["格",0]],8],[[3,["格",0]],8]],"取货指向":[[[2,0],"源矿"]]
        }),
    )
    .unwrap();
    base.step();
    assert_eq!(
        base.snapshot(),
        json!({
            "货":[[[3,["格",0]],[["源矿",1]]],[[4,["格",0]],[["钢块",1]]]],
            "已停":[[[3,["格",0]],1]],"取货指向":[[[2,0],"源矿"]]
        })
    );
}

#[test]
fn input_port_limits_apply_to_every_prefix() {
    use Kind::*;
    for (kind, limit) in [(仓库取货口, 0), (精炼炉, 3), (种植机, 5), (封装机, 6)] {
        let mut history = vec![build(0, kind)];
        for u in 1..=limit {
            history.extend([build(u, 桥接器格), edge(u, 0)]);
        }
        assert!(LegalBase::new(&history, params(&[]), &json!({})).is_ok());
        let extra = limit + 1;
        history.extend([build(extra, 桥接器格), edge(extra, 0), Event::Remove(extra)]);
        assert!(LegalBase::new(&history, params(&[]), &json!({})).is_err());
    }
}

#[test]
fn snapshot_objects_have_strictly_increasing_utf8_keys() {
    use serde_json::Value;
    fn check(v: &Value) {
        match v {
            Value::Object(obj) => {
                assert!(obj.keys().map(|k| k.as_bytes()).is_sorted_by(|a, b| a < b));
                obj.values().for_each(check);
            }
            Value::Array(items) => items.iter().for_each(check),
            _ => {}
        }
    }
    let state = json!({
        "货": [[[2, "缓存"], [["源矿", 1]]]],
        "制造中": [[2, [{"单位":"粉碎机","原料":[["源矿",1]],"产物":["源石粉末",1],"时长":1},0]]],
        "准入口": [[1, {"名额":[3]}]],
        "储存箱": [[3, {"冷却还剩":2}]]
    });
    let h = [
        build(1, Kind::物品准入口),
        build(2, Kind::粉碎机),
        build(3, Kind::协议储存箱),
    ];
    let snapshot = LegalBase::new(&h, params(&[3]), &state).unwrap().snapshot();
    assert_eq!(snapshot.as_object().unwrap().len(), 4);
    check(&serde_json::from_str(&snapshot.to_string()).unwrap());
}

#[test]
fn solver_rejects_non_integer_and_out_of_range_snapshot_numbers() {
    for token in ["1e0", "0.1e1", "1.0", "-1", "18446744073709551616"] {
        let state = serde_json::from_str(&format!(r#"{{"仓库":[["源矿",{token}]]}}"#)).unwrap();
        assert!(LegalBase::new(&[], params(&[]), &state).is_err());
    }
}
