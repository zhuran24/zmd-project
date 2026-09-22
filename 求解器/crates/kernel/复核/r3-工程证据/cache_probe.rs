//! 工程席独立差分：公开入口、内存基目录、表示顺序和跨时刻缓存。
use kernel::{Config, Engine, Input, value::read_json};
use serde_json::{json, Value};
use std::path::Path;

fn main() {
    let root = Path::new("/home/zhuran24/zmd-research-fresh/求解器");
    let config = Config::parse(read_json(&root.join("规格/内核配置-v1.json")).unwrap()).unwrap();
    let samples = root.join("数据/样例");
    let mut names = vec![
        "混做粉碎机两下游".to_string(), "分流器三路轮询".into(),
        "桥接器双通路".into(), "传输拒收与暂停核验".into(),
        "研磨混做核验".into(), "阻尼切支恢复核验".into(),
        "阻尼连续带核验".into(), "生产循环环带".into(), "轮询均分核验".into(),
        "密集结点核验".into(), "密集结点闭环核验".into(), "密集结点循环种子核验".into(),
    ];
    names.extend((0..6).map(|i|format!("密集制造闭环序{i}核验")));
    names.extend((0..6).map(|i|format!("轮询均分序{i}核验")));
    let mut reports = Vec::<Value>::new();
    assert!(!samples.join("memory-input.json").exists());
    for name in names {
        let path = samples.join(format!("{name}.json"));
        let raw = read_json(&path).unwrap();
        let mut direct = Engine::new(Input::parse_with_base(raw.clone(), &samples, &config, false).unwrap()).unwrap();
        let mut cached = Engine::new(Input::load(&path, &config, false).unwrap()).unwrap();
        let mut shuffled_raw = raw;
        shuffled_raw["initial_state"]["nonwarehouse"]["value"]["inventory"].as_array_mut().unwrap().reverse();
        for field in ["units","physical_channels","buffer_channels"] {
            shuffled_raw["layout"][field].as_array_mut().unwrap().reverse();
        }
        let mut shuffled = Engine::new(Input::parse_with_base(shuffled_raw, &samples, &config, false).unwrap()).unwrap();
        cached.set_cache_enabled(true);
        shuffled.set_cache_enabled(true);
        let count = if name == "混做粉碎机两下游" {4} else if name == "分流器三路轮询" {12} else {24};
        for _ in 0..count {
            let a=direct.step(true).unwrap();
            let b=cached.step(true).unwrap();
            let c=shuffled.step(true).unwrap();
            assert_eq!(a,b,"缓存差分：{name}");
            assert_eq!(a,c,"内存基目录和排列差分：{name}");
        }
        reports.push(json!({"name":name,"ticks":count,"cache_full_tick_equal":true,"memory_base_and_permutation_equal":true}));
    }
    println!("{}",json!({"status":"pass","cases":reports,"virtual_input_exists":samples.join("memory-input.json").exists()}));
}
