//! 内核输出§3复核：调用公开重算验收入口，不修改内核。
use kernel::{output::verify_record, value::read_json, Config, Input};
use serde_json::json;
use std::path::PathBuf;

fn main() {
    let root = PathBuf::from(std::env::args().nth(1).expect("缺求解器路径"));
    let out = root.join("crates/kernel/复核/r1-测试与证据");
    let config_path = root.join("规格/内核配置-v1.json");
    let config = Config::parse(read_json(&config_path).unwrap()).unwrap();
    let mut rows = Vec::new();
    for name in ["混做粉碎机两下游", "分流器三路轮询"] {
        let input_path = root.join(format!("数据/样例/{name}.json"));
        for record_path in [
            root.join(format!("数据/样例/{name}-运行记录-kernel.json")),
            root.join(format!("数据/样例/{name}-运行记录-checkpoint_delta-kernel.json")),
            out.join(format!("{name}-删除三份正式源指纹.json")),
            out.join(format!("{name}-伪造验证范围与批数.json")),
        ] {
            let record = read_json(&record_path).unwrap();
            let input = Input::load(&input_path, &config, false).unwrap();
            let result = verify_record(&record, input, &config, &config_path);
            rows.push(json!({"record":record_path,"accepted":result.is_ok(),"error":result.err().map(|e|e.to_string())}));
        }
    }
    // 复核负例也经过公开输入装载及完整记录重算。
    let record_path = out.join("空补矿史耗尽-record.json");
    let input = Input::load(&out.join("空补矿史耗尽-input.json"), &config, false).unwrap();
    let result = verify_record(&read_json(&record_path).unwrap(), input, &config, &config_path);
    rows.push(json!({"record":record_path,"accepted":result.is_ok(),"error":result.err().map(|e|e.to_string())}));
    println!("{}", serde_json::to_string_pretty(&rows).unwrap());
}
