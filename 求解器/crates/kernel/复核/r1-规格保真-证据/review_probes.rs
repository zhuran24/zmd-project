//! 规格保真独立探针；只读原源代码，测试记录保存在复核目录。
use crate::{value::*, Config, Engine, Input};
use serde_json::{json, Value};
use std::path::PathBuf;

fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..").canonicalize().unwrap()
}

fn config() -> Config {
    Config::parse(read_json(&root().join("规格/内核配置-v1.json")).unwrap()).unwrap()
}

fn sample(name: &str) -> Engine {
    let path = root().join(format!("数据/样例/{name}.json"));
    Engine::new(Input::load(&path, &config(), false).unwrap()).unwrap()
}

fn set_axis(raw: &mut Value, axis: &str, value: Value) {
    for group in ["fixed", "offline_mutable", "fixedness_unproven"] {
        if raw["parameters"][group].get(axis).is_some() {
            raw["parameters"][group][axis]["value"] = value.clone();
        }
    }
    for row in raw["initial_state"]["nonwarehouse"]["value"]["semantic_context"]["parameter_values"].as_array_mut().unwrap() {
        if row["axis"] == axis { row["value"]["value"] = value.clone(); }
    }
}

// 受限转移§3.4、输入§5.3：在原始函数上隔离图变更后的分支选择，不冒充可达性见证。
#[test]
fn review_fixed_branch_after_edge_removal() {
    let mut engine = sample("分流器三路轮询");
    let origin = "PC|south_box:north:2|splitter:south:0";
    let chosen = "PC|splitter:north:0|north_box:south:0";
    engine.input.branches.insert((origin.into(), "splitter".into()), chosen.into());
    assert_eq!(engine.damping(origin).unwrap(), 1);
    engine.active.remove(chosen);
    let two_remaining = engine.damping(origin);
    assert!(two_remaining.is_err());
    let others: Vec<_> = engine.active.iter().filter(|id| id.starts_with("PC|splitter:")).cloned().collect();
    assert_eq!(others.len(), 2);
    engine.active.remove(&others[0]);
    let one_remaining = engine.damping(origin);
    println!("fixed_branch chosen={chosen} two_remaining={two_remaining:?} one_remaining={one_remaining:?}");
    assert_eq!(one_remaining.unwrap(), 1);
}

// 输入§5.3：非路径分叉表项不能只因端点真实存在便被接收。
#[test]
fn review_unrelated_fork_choice_accepted() {
    let engine = sample("分流器三路轮询");
    let mut raw = engine.input.raw.clone();
    let axis = json!({"schema":"damping-branch-v1","fixedness":"fixed_for_run","choices":[{"channel":"PC|probe_left:west:0|probe_gate_a:south:0","fork_unit":"splitter","outgoing_channel":"PC|splitter:north:0|north_box:south:0"}],"evaluations":[],"on_missing":"unresolved"});
    set_axis(&mut raw, "damping.branch", axis);
    raw["catalog"]["path"] = json!(root().join("数据/正式静态目录.json"));
    raw["parameters"]["axis_registry"]["path"] = json!(root().join("规格/选择点参数轴.md"));
    let path = root().join("crates/kernel/复核/r1-规格保真-证据/unrelated-fork-input.json");
    std::fs::write(&path, serde_json::to_string_pretty(&raw).unwrap()).unwrap();
    let result = Input::load(&path, &config(), false).and_then(Engine::new);
    println!("unrelated_fork accepted={}", result.is_ok());
    assert!(result.is_ok());
}

// 受限模型声明§2：运行函数没有请求阻尼的单级情况，与多级退化前件分开。
#[test]
fn review_single_level_no_terminal_continues() {
    let mut engine = sample("混做粉碎机两下游");
    engine.active.remove("PC|belt_a2:north:0|grinder_a:south:5");
    let direct = engine.damping("PC|crusher:north:0|belt_a0:south:0");
    let refresh = engine.refresh();
    println!("single_level direct_query={direct:?} refresh={refresh:?}");
    assert_eq!(direct.unwrap_err().axis, "damping.no_terminal");
    assert!(refresh.is_ok());
}

// 输入§5.3、转移§2.2：两门同次身份维护后，已选分支断开且仍有另一条活路。
#[test]
fn review_dynamic_fixed_branch() {
    let dir = root().join("crates/kernel/复核/r1-规格保真-证据");
    let path = dir.join("fixed-branch-dynamic.json");
    let mut engine = Engine::new(Input::load(&path, &config(), false).unwrap()).unwrap();
    engine.put("source:storage:0", "源矿", 20).unwrap();
    engine.refresh().unwrap();
    engine.state.logistics.poll_memory.value = json!(engine.memory);
    let mut raw = engine.input.raw.clone();
    raw["initial_state"]["nonwarehouse"]["value"] = json!(engine.state);
    let input_path = dir.join("fixed-branch-dynamic-input.json");
    std::fs::write(&input_path, serde_json::to_string_pretty(&raw).unwrap()).unwrap();
    let mut engine = Engine::new(Input::load(&input_path, &config(), false).unwrap()).unwrap();
    let origin = "PC|source:north:0|splitter:south:0";
    let before = engine.damping(origin).unwrap();
    let tick = engine.step(true).unwrap().unwrap();
    let after = engine.damping(origin);
    println!("dynamic_fixed_branch before={before} after={after:?} blocked={:?}", engine.state.logistics.blocked_channels);
    std::fs::write(dir.join("fixed-branch-dynamic-tick.json"), serde_json::to_string_pretty(&tick).unwrap()).unwrap();
    assert!(!engine.active.contains("PC|splitter:north:0|gate_n:south:0"));
    assert!(!engine.active.contains("PC|splitter:west:0|gate_w:south:0"));
    assert_eq!(after.unwrap(), 3);
}

// 输出§2–§3：同一错误不能仅凭同程序重算相等获得事件身份验收。
#[test]
fn review_alias_record_self_verifies() {
    let dir = root().join("crates/kernel/复核/r1-规格保真-证据");
    let record = read_json(&dir.join("pending-historical-alias-record.json")).unwrap();
    let input = Input::load(&dir.join("pending-historical-alias-input.json"), &config(), false).unwrap();
    let result = crate::output::verify_record(&record, input, &config(), &root().join("规格/内核配置-v1.json"));
    println!("historical_alias_self_verify={result:?}");
    assert!(result.is_ok());
}
