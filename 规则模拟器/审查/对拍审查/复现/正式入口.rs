use endfield_sim::{Counter::保留, CounterPolicy, LegalBase, Parameters};
use serde_json::Value;

fn main() -> Result<(), String> {
    let script: Value = serde_json::from_str(include_str!("指数库存.json")).unwrap();
    let parameters = Parameters {
        powered: vec![],
        ports: vec![],
        transfer_after: vec![],
        on_change: CounterPolicy { count: 保留, quotas: 保留 },
        on_offline: CounterPolicy { count: 保留, quotas: 保留 },
    };
    let mut base = LegalBase::new(&[], parameters, &script["段"][0]["状态"])?;
    base.step();
    println!("{}", base.snapshot());
    Ok(())
}
