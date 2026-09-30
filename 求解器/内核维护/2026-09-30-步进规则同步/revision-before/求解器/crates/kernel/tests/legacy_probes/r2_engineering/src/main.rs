use kernel::{value::read_json, output::verify_record, Config, Engine, Input};
use serde_json::json;
use std::path::PathBuf;

/// 内核输入§3.1、§6与内核输出§3：独立走公开库入口，记录恢复后身份复用和坏封套验收结果。
fn main() {
    let args: Vec<_> = std::env::args().collect();
    let root = PathBuf::from(&args[1]);
    let out = PathBuf::from(&args[2]);
    let config_path = root.join("规格/内核配置-v1.json");
    let config = Config::parse(read_json(&config_path).unwrap()).unwrap();
    let source = out.join("restart-control-input.json");
    let mut raw = read_json(&source).unwrap();
    let event_id = "J|2|0|0";
    raw["initial_state"]["nonwarehouse"]["value"]["semantic_context"]["tick_context"]["value"]["movements"][0]["event"] = json!(event_id);
    let forged = out.join("movement-future-id-input.json");
    std::fs::write(&forged, serde_json::to_string_pretty(&raw).unwrap()+"\n").unwrap();
    let input = Input::load(&forged, &config, false).unwrap();
    let mut engine = Engine::new(input).unwrap();
    let seed = json!(engine.state);
    let tick = engine.step(true).unwrap().unwrap();
    let reused = tick["events"].as_array().unwrap().iter().filter(|e| e["event"] == event_id).count();
    std::fs::write(out.join("movement-future-id-tick.json"),serde_json::to_string_pretty(&tick).unwrap()+"\n").unwrap();
    let mut verified = Vec::new();
    for name in ["control", "reachability-null", "reachability-number", "reachability-object", "reachability-string"] {
        let path = out.join(format!("{name}-input.json"));
        let record = read_json(&out.join(format!("{name}-record.json"))).unwrap();
        let input = Input::load(&path, &config, false).unwrap();
        let result = verify_record(&record, input, &config, &config_path);
        verified.push(json!({"case":name,"accepted":result.is_ok(),"error":result.err().map(|e|e.to_string())}));
    }
    let result = json!({"seed_executed_event":seed["semantic_context"]["tick_context"]["value"]["movements"][0]["event"],"seed_time":seed["environment"]["time"],"next_time":tick["time"],"same_id_executed_again":reused,"record_verifier":verified});
    let text=serde_json::to_string_pretty(&result).unwrap();
    std::fs::write(out.join("library-probes.json"),text.clone()+"\n").unwrap();
    println!("{text}");
}
