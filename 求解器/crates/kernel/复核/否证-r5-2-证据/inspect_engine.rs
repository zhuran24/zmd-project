//! 否证席只读探针：直接观察公开构造器返回值，随后才调用生产域检查。
use kernel::{value::read_json, Config, Engine, Input};
use serde_json::json;
use std::path::Path;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let config = Config::parse(read_json(Path::new(&args[1])).unwrap()).unwrap();
    let input = Input::load(Path::new(&args[2]), &config, false).unwrap();
    let engine = Engine::new(input).unwrap();
    let current = &engine.memory.sides.iter()
        .find(|side| side.unit == "core" && side.side == "input").unwrap().current_level;
    println!("{}", json!({
        "constructor_returned": true,
        "production_abstraction_before_domain": engine.production_abstraction,
        "core_input_current_level_before_domain": current,
        "time_before_domain": engine.state.environment.time,
        "domain_report_after_constructor": engine.domain_report("static")
    }));
}
