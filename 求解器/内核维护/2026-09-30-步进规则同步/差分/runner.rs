//! 仅调用公开库接口；输入、状态和轨迹均在内存，不写历史样例或运行记录。
use kernel::{Config, Engine, Input};
use serde_json::{json, Value};
use std::{io::{self, BufRead, Write}, path::Path};

fn run(job: &Value) -> kernel::Result<Value> {
    let cfg = Config::parse(kernel::value::read_json(Path::new(job["config"].as_str().unwrap()))?)?;
    let input = Input::parse_with_base(job["input"].clone(), Path::new(job["base"].as_str().unwrap()), &cfg)?;
    let mut engine = Engine::new(input)?;
    let graph = json!({
        "layers":engine.graph().components.iter().enumerate().map(|(i,c)| (c.id.clone(),engine.graph().layers[i])).collect::<std::collections::BTreeMap<_,_>>(),
        "order":engine.graph().order.iter().map(|s|engine.graph().label(s)).collect::<Vec<_>>(),
        "rank":engine.graph().rank,
    });
    let mut rows = Vec::new();
    let mut polls = Vec::new();
    let mut gates = Vec::new();
    let mut events = Vec::new();
    for _ in 0..job["steps"].as_u64().unwrap() {
        let report = engine.step()?;
        rows.push(engine.observe(&report));
        polls.push(serde_json::to_value(&engine.state.logistics.poll_state).unwrap());
        gates.push(serde_json::to_value(&engine.state.logistics.gate_counters).unwrap());
        events.push(serde_json::to_value(&report.events).unwrap());
    }
    Ok(json!({"name":job["name"],"graph":graph,"rows":rows,"polls":polls,"gates":gates,"events":events,"end_state":engine.state}))
}
fn main() {
    let stdin = io::stdin();
    let mut out = io::BufWriter::new(io::stdout().lock());
    for line in stdin.lock().lines() {
        let job: Value = serde_json::from_str(&line.unwrap()).unwrap();
        let result = match run(&job) {
            Ok(value) => value,
            Err(error) => json!({"name":job["name"],"error":error}),
        };
        serde_json::to_writer(&mut out, &result).unwrap();
        writeln!(&mut out).unwrap();
        out.flush().unwrap();
    }
}
