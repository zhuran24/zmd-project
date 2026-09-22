//! 修订r5：D.2装载优先于矿量相关的可动级派生，有限运行仍保留容量差异。
use super::*;

#[test]
fn revision_r5_production_load_guards_ore_before_memory() {
    let cfg = config();
    let mut sample = fixture("core_inbound");
    put(&mut sample, "belt:transport:0", "源矿", 1);
    // 滞留已满，使有限运行的两种矿量确实产生不同的核心可动级。
    sample.state.inventory[sample.inv["belt:transport:0"]].contents[0].entered_at =
        Some(Time::at(-1));
    let mut raw = sample.input.raw.clone();
    raw["initial_state"]["nonwarehouse"]["value"] = json!(sample.state);
    set_axis(
        &mut raw,
        "warehouse.external_supply",
        json!({"kind":"sufficient"}),
    );
    let mut seeds = Vec::new();
    let mut memories = Vec::new();
    for quantity in [79999, 80000] {
        for row in raw["initial_state"]["nonwarehouse"]["value"]["warehouse"]["slots"]
            .as_array_mut()
            .unwrap()
        {
            if row["item"] == "源矿" {
                row["quantity"] = q(quantity);
            }
        }
        let seed = Input::canonicalize_seed(raw.clone(), sample.input.path.parent().unwrap(), &cfg)
            .unwrap();
        let input = Input::parse(seed.clone(), &sample.input.path, &cfg, false).unwrap();
        let finite = Engine::new(input.clone()).unwrap();
        memories.push(finite.memory.clone());
        let stop = Engine::new_production(input.clone()).unwrap_err();
        assert_eq!(stop.axis, "cycle.domain.D2");
        let report = Engine::check_cycle_domain(input.clone()).unwrap();
        assert_eq!(report[1]["status"], "fail");
        assert_eq!(report[3]["status"], "unresolved");
        assert!(report
            .as_array()
            .unwrap()
            .iter()
            .all(|r| r["scope"] == "static"));
        assert_eq!(
            crate::cycle::cycle_key(&finite.state, &input)
                .unwrap_err()
                .axis,
            "cycle.domain.D2"
        );
        seeds.push(seed);
    }
    assert_ne!(memories[0], memories[1]);
    // 仅改矿量，故保留79999时的游标派生；生产模式必须先报D.2，不能先报poll_memory。
    let mut crossed = seeds[0].clone();
    crossed["initial_state"]["nonwarehouse"]["value"]["warehouse"] =
        seeds[1]["initial_state"]["nonwarehouse"]["value"]["warehouse"].clone();
    let input = Input::parse(crossed, &sample.input.path, &cfg, false).unwrap();
    assert_eq!(
        Engine::new(input.clone()).unwrap_err().location,
        "poll_memory"
    );
    assert_eq!(
        Engine::new_production(input.clone()).unwrap_err().axis,
        "cycle.domain.D2"
    );
    let stop = crate::cycle::search(
        input,
        &cfg,
        &root().join("规格/内核配置-v1.json"),
        2,
        100,
        &Default::default(),
    )
    .unwrap_err();
    assert_eq!(stop.axis, "cycle.domain.D2");
}
