use kernel::{cycle, value::read_json, Config, Engine, Input};
use serde_json::{json, Value};
use std::path::Path;

fn inventory_result(result: kernel::Result<()>) -> Value {
    match result {
        Ok(()) => json!({"result":"Ok"}),
        Err(stop) => json!({"result":"Err", "stop":stop}),
    }
}
fn key_result(result: kernel::Result<Value>) -> Value {
    match result {
        Ok(key) => json!({"result":"Ok", "key":key}),
        Err(stop) => json!({"result":"Err", "stop":stop}),
    }
}
fn inspect(engine: &Engine) -> Value {
    json!({
        "validate_inventory":inventory_result(engine.validate_inventory()),
        "engine_cycle_key":key_result(engine.cycle_key()),
        "standalone_cycle_key":key_result(cycle::cycle_key(&engine.state, &engine.input))
    })
}
fn main() {
    let arg = std::env::args().nth(1).expect("solver root argument");
    let root = Path::new(&arg);
    let config = Config::parse(read_json(&root.join("规格/内核配置-v1.json")).unwrap()).unwrap();
    let input = Input::load(&root.join("数据/样例/生产循环环带.json"), &config, false).unwrap();
    let mut engine = Engine::new_production(input).unwrap();
    let initial_time = engine.state.environment.time.integer("probe.time").unwrap();
    engine.step(false).expect("first step succeeds");
    let before_state = json!(engine.state);
    let before = inspect(&engine);
    for name in ["validate_inventory", "engine_cycle_key", "standalone_cycle_key"] {
        assert_eq!(before[name]["result"], "Ok");
    }
    assert_eq!(before["engine_cycle_key"]["key"], before["standalone_cycle_key"]["key"]);
    let row_index = engine.state.inventory.iter().position(|r| r.slot == "b:transport:0").unwrap();
    let old = engine.state.inventory[row_index].contents[0].quantity.value.clone();
    assert_ne!(old, "0");
    // The only mutation: keep category, item, entered_at and all other fields unchanged.
    engine.state.inventory[row_index].contents[0].quantity.value = "0".into();
    let after_state = json!(engine.state);
    let after = inspect(&engine);
    assert_eq!(json!(engine.state), after_state);
    assert_eq!(after["validate_inventory"]["stop"]["status"], "invalid_input");
    assert_eq!(after["engine_cycle_key"]["result"], "Ok");
    assert_eq!(after["standalone_cycle_key"]["stop"]["status"], "invalid_input");
    assert!(after["engine_cycle_key"]["key"]["state"]["inventory"].as_array().unwrap().iter()
        .any(|r| r["slot"] == "b:transport:0" && r["contents"][0]["quantity"]["value"] == "0"));
    engine.state.inventory[row_index].contents[0].quantity.value = old.clone();
    let restored = inspect(&engine);
    assert_eq!(before, restored);
    assert_eq!(json!(engine.state), before_state);
    println!("{}", serde_json::to_string_pretty(&json!({
        "verdict":"重现了", "input":"数据/样例/生产循环环带.json",
        "constructor":"Engine::new_production", "step":"engine.step(false)",
        "initial_time":initial_time,
        "after_step_time":engine.state.environment.time.integer("probe.time").unwrap(),
        "mutation":{"path":format!("state.inventory[{row_index}].contents[0].quantity.value"),
            "slot":"b:transport:0", "before":old, "after":"0"},
        "before":before, "after":after, "restored":restored,
        "before_state":before_state, "after_state":after_state,
        "checks":{"only_quantity_value_changed":true,"valid_keys_equal":true,
            "engine_key_contains_zero":true,"apis_did_not_mutate_state":true,
            "restoration_returns_original_results":true}
    })).unwrap());
}
