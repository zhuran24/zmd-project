use kernel::{value::read_json, Config, Engine, Input};
use serde_json::json;
use std::path::Path;

// 受限转移§1、§3.1：仅经公开加载、步进和阻尼入口观察，不修改内核。
fn main() {
    let args: Vec<String> = std::env::args().collect();
    let config = Config::parse(read_json(Path::new(&args[2])).unwrap()).unwrap();
    if args[3] == "verify" {
        let record = read_json(Path::new(&args[4])).unwrap();
        let result = Input::load(Path::new(&args[1]), &config, false)
            .and_then(|input| kernel::output::verify_record(&record, input, &config, Path::new(&args[2])));
        println!("{}", json!({"verify":result.map_err(|e|e.to_string())}));
        return;
    }
    let result = Input::load(Path::new(&args[1]), &config, false).and_then(Engine::new);
    let mut engine = match result {
        Ok(e) => e,
        Err(e) => { println!("{}", json!({"load_error":e.to_string()})); return; }
    };
    let mut observations = Vec::new();
    let query = args.get(4);
    if let Some(q) = query {
        observations.push(json!({"when":"loaded", "damping":engine.damping(q).map_err(|e|e.to_string())}));
    }
    for _ in 0..args[3].parse::<usize>().unwrap() {
        match engine.step(true) {
            Ok(tick) => {
                let mut row = json!({"tick":tick});
                if let Some(q) = query {
                    row["damping"] = json!(engine.damping(q).map_err(|e|e.to_string()));
                }
                // 内核输入§6与受限转移§1：完整闭包后态应能按原参数恢复。
                let mut restored = engine.input.raw.clone();
                restored["initial_state"]["nonwarehouse"]["value"] = json!(engine.state);
                row["reload"] = json!(Input::parse(restored, &engine.input.path, &config, false)
                    .and_then(Engine::new).map(|_| "ok").map_err(|e|e.to_string()));
                observations.push(row);
            }
            Err(e) => { observations.push(json!({"stop":e.to_string()})); break; }
        }
    }
    println!("{}", json!({"observations":observations}));
}
