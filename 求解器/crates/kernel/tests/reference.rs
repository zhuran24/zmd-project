//! 第四轮§4.7：固定黄金与独立 Python 运行记录逐字段严格比较。
use kernel::{value::*, Config, Engine, Input};
use serde_json::Value;
use std::path::PathBuf;
/// 第四轮§4.7：依工作区定位只读样例。
fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .unwrap()
}
/// 内核输出§3：差异报告到具体路径，类型和数组顺序都参与比较。
fn compare(a: &Value, b: &Value, path: &str) {
    match (a, b) {
        (Value::Object(x), Value::Object(y)) => {
            assert_eq!(
                x.keys().collect::<Vec<_>>(),
                y.keys().collect::<Vec<_>>(),
                "{path} keys"
            );
            for (k, v) in x {
                compare(v, &y[k], &format!("{path}.{k}"));
            }
        }
        (Value::Array(x), Value::Array(y)) => {
            assert_eq!(x.len(), y.len(), "{path} length");
            for (i, (x, y)) in x.iter().zip(y).enumerate() {
                compare(x, y, &format!("{path}[{i}]"))
            }
        }
        _ => assert_eq!(a, b, "{path}"),
    }
}
/// 第四轮§4.7：粉碎机4刻完整轨迹、全部黄金字段相等。
#[test]
fn crusher_reference() {
    differential("混做粉碎机两下游", true)
}
/// 第四轮§4.7：分流器12刻完整轨迹相等，含双门同批到期。
#[test]
fn splitter_reference() {
    differential("分流器三路轮询", false)
}
/// 第四轮§4.7：比较每个时刻的每个字段，不删事件或元数据。
fn differential(name: &str, golden: bool) {
    let r = root();
    let config = Config::parse(read_json(&r.join("规格/内核配置-v1.json")).unwrap()).unwrap();
    let path = r.join(format!("数据/样例/{name}.json"));
    let input = Input::load(&path, &config, false).unwrap();
    let mut engine = Engine::new(input).unwrap();
    let record = read_json(&r.join(format!("数据/样例/{name}-运行记录-v3.json"))).unwrap();
    let expected = record["trace"]["ticks"].as_array().unwrap();
    let mut actual = Vec::new();
    for tick in expected {
        let got = engine.step(true).unwrap().unwrap();
        compare(&got, tick, "tick");
        actual.push(got);
    }
    if golden {
        let g = read_json(&r.join("数据/样例/混做粉碎机两下游-黄金轨迹.json")).unwrap();
        compare(
            &Value::Array(actual.iter().map(|t| t["summary"].clone()).collect()),
            &g["ticks"],
            "golden.ticks",
        );
    }
}
/// 第四轮§4.7：现场调用已显式迁移v3台账的独立 Python 参考执行器，先与已落盘记录相等，再与 Rust 相等。
#[test]
fn live_python_differential() {
    let r = root();
    let script="import json,sys;sys.path.insert(0,sys.argv[1]);import check_golden_trace as g;import check_examples as c;print(json.dumps({n:g.run(c.load_json(g.BASE/(n+'.json'))) for n in ['混做粉碎机两下游','分流器三路轮询']},ensure_ascii=False))";
    let output = std::process::Command::new("python")
        .arg("-B")
        .arg("-c")
        .arg(script)
        .arg(r.join("数据/样例"))
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let python: Value = serde_json::from_slice(&output.stdout).unwrap();
    let config = Config::parse(read_json(&r.join("规格/内核配置-v1.json")).unwrap()).unwrap();
    for name in ["混做粉碎机两下游", "分流器三路轮询"] {
        let reference = read_json(&r.join(format!("数据/样例/{name}-运行记录-v3.json"))).unwrap();
        compare(
            &python[name],
            &reference["trace"]["ticks"],
            "python_vs_record",
        );
        let mut e = Engine::new(
            Input::load(&r.join(format!("数据/样例/{name}.json")), &config, false).unwrap(),
        )
        .unwrap();
        for tick in python[name].as_array().unwrap() {
            compare(&e.step(true).unwrap().unwrap(), tick, "rust_vs_python");
        }
    }
}
