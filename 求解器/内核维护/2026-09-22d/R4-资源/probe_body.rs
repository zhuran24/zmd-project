// Included after unchanged production modules by build_probe.py.
fn stats(e: &Engine, completed: usize, elapsed_ns: u128) -> serde_json::Value {
    let inventory_rows: usize = e.state.inventory.iter().map(|r| r.contents.len()).sum();
    let capacities: usize = e.allocated.iter().chain(e.executed.iter()).map(|s| s.capacity()).sum();
    serde_json::json!({
        "completed_ticks": completed, "elapsed_ns": elapsed_ns.to_string(),
        "allocated": e.allocated.len(), "executed": e.executed.len(),
        "allocated_j": e.allocated.iter().filter(|s| s.starts_with("J|")).count(),
        "executed_j": e.executed.iter().filter(|s| s.starts_with("J|")).count(),
        "id_string_capacity_bytes_both_sets": capacities,
        "id_string_object_bytes_both_sets": (e.allocated.len()+e.executed.len()) * std::mem::size_of::<String>(),
        "records": e.records.len(), "records_capacity": e.records.capacity(),
        "movements": e.movements.len(), "passages": e.passages.len(),
        "pending": e.pending.len(), "inventory_content_rows": inventory_rows,
        "templates": e.input.templates.len(),
        "last_rounds": e.state.semantic_context.judgment_context.value["round"],
        "physical_cache": e.physical_cache.borrow().len(),
        "proc_status": std::fs::read_to_string("/proc/self/status").unwrap(),
    })
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let config = Config::parse(value::read_json(std::path::Path::new(&args[2])).unwrap()).unwrap();
    let input = Input::load(std::path::Path::new(&args[1]), &config, false).unwrap();
    let mut engine = Engine::new(input).unwrap();
    engine.set_cache_enabled(true);
    engine.max_sweeps = 100_000;
    println!("{}", stats(&engine, 0, 0));
    let start = std::time::Instant::now();
    for completed in 1..=100_000 {
        if let Err(stop) = engine.step(false) {
            println!("{}", serde_json::json!({"completed_ticks":completed-1,"stop":stop}));
            return;
        }
        if [1, 1000, 10000, 100000].contains(&completed) {
            println!("{}", stats(&engine, completed, start.elapsed().as_nanos()));
        }
    }
}
