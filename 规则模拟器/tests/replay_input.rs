use endfield_sim::oracle::OracleRunner;
use serde_json::{Value, json};

fn segment() -> Value {
    json!({"历史":[["建成",1,"研磨机"]],"供电":[],"端口":[],"状态":{},"操作":[],
        "未定":{"传输排在几组之后":[],"离线后的计数":["保留","保留"],
        "改设定后的计数":["保留","保留"],"输入判定都没货时":"每步判两次"}})
}

fn run(segment: Value) -> Result<(), String> {
    OracleRunner::run(
        &json!({"版本":1,"段":[segment]}).to_string(),
        &mut Vec::new(),
    )
}

#[test]
fn replay_requires_plain_unsigned_numbers_and_string_names() {
    for token in ["1e0", "0.1e1", "1.0", "-0", "-1", "18446744073709551616"] {
        let input = format!(r#"{{"版本":{token},"段":[]}}"#);
        assert!(OracleRunner::run(&input, &mut Vec::new()).is_err());
    }
    for op in [
        json!(["入库", {"钢块": null}, 1]),
        json!(["离线", [["建成", 1, {"研磨机":null}]]]),
    ] {
        let mut s = segment();
        s["操作"] = json!([op]);
        assert!(run(s).is_err());
    }
}

#[test]
fn lone_surrogate_escapes_are_rejected() {
    // 备注写在段里；原文直接拼进去，转义不经 serde 重写。
    let with_note = |note: &str| {
        let seg = segment().to_string();
        let seg = format!(r#"{{"备注":"{note}",{}"#, &seg[1..]);
        OracleRunner::run(&format!(r#"{{"版本":1,"段":[{seg}]}}"#), &mut Vec::new())
    };
    assert!(with_note("plain").is_ok());
    assert!(with_note(r"\ud800\udc00").is_ok());
    for note in [r"\ud800", r"\udc00", r"\ud800\ufeff"] {
        assert!(with_note(note).is_err());
    }
}

#[test]
fn native_integer_limits_are_checked() {
    let mut s = segment();
    s["历史"] = json!([["建成", u64::MAX, "物品准入口"]]);
    s["状态"] = json!({"准入口":[[u64::MAX, {"名额":[u32::MAX], "累计已收":usize::MAX}]]});
    s["操作"] = json!([["走", 1]]);
    assert!(run(s.clone()).is_ok());
    s["状态"]["准入口"][0][1]["名额"] = json!([u64::from(u32::MAX) + 1]);
    assert!(run(s).is_err());
}
