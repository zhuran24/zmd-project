//! 复核专用：公开Rust验收入口对照，不改内核源和既有测试。
use kernel::{output::{run_record, verify_record}, value::read_json, Config, Engine, Input};
use serde_json::json;
use std::path::PathBuf;

fn main() {
    let root = PathBuf::from(std::env::args().nth(1).unwrap());
    let config_path = root.join("规格/内核配置-v1.json");
    let config = Config::parse(read_json(&config_path).unwrap()).unwrap();
    let source = root.join("数据/样例/混做粉碎机两下游.json");
    let load = || Input::load(&source, &config, false).unwrap();
    let control = run_record(Engine::new(load()).unwrap(), &config, &config_path, 4, "full_state_each_instant", 3).unwrap();
    verify_record(&control, load(), &config, &config_path).unwrap();
    let mut results = Vec::new();
    for case in ["unknown_axis", "fabricated_exercised", "wrong_disposition", "missing_evidence", "wrong_profile", "wrong_producer_path"] {
        let mut bad = control.clone();
        match case {
            "unknown_axis" => bad["uncovered_axes"][0]["axis"] = json!("fabricated.axis"),
            "fabricated_exercised" => {
                let row = bad["uncovered_axes"].as_array_mut().unwrap().iter_mut().find(|r| r["axis"] == "transfer.cooldown_scope").unwrap();
                row["coverage_status"] = json!("exercised"); row["evidence"] = json!(["never_executed_event"]);
            },
            "wrong_disposition" => {
                let row = bad["uncovered_axes"].as_array_mut().unwrap().iter_mut().find(|r| r["axis"] == "warehouse.periodic_lift").unwrap();
                row["disposition"] = json!("已定");
            },
            "missing_evidence" => {
                for row in bad["uncovered_axes"].as_array_mut().unwrap() {
                    if ["warehouse.acceptance", "warehouse.acceptance_quantifier"].contains(&row["axis"].as_str().unwrap()) {row["evidence"] = json!(["无逐边界报告"]);}
                }
            },
            "wrong_profile" => bad["profile_id"] = json!("fabricated_profile"),
            _ => bad["producer"]["path"] = json!("/nonexistent/fabricated.rs"),
        }
        let error = verify_record(&bad, load(), &config, &config_path).unwrap_err();
        results.push(json!({"case":case,"accepted":false,"reason":error.to_string()}));
    }
    println!("{}", serde_json::to_string_pretty(&json!({"valid_control":true,"mutations":results})).unwrap());
}
