//! K5独立探针：输入文件不存在时，内存值加基目录可解析并产生相同轨迹。
use kernel::{value::read_json, Config, Engine, Input};
use std::path::Path;

fn main() -> kernel::Result<()> {
    let root = Path::new("/home/zhuran24/zmd-research-fresh/求解器");
    let config = Config::parse(read_json(&root.join("规格/内核配置-v1.json"))?)?;
    let source = root.join("数据/样例/混做粉碎机两下游.json");
    let raw = read_json(&source)?;
    let base = source.parent().unwrap();
    assert!(!base.join("memory-input.json").exists());
    let mut memory = Engine::new(Input::parse_with_base(raw.clone(), base, &config, false)?)?;
    let mut file = Engine::new(Input::load(&source, &config, false)?)?;
    for _ in 0..4 {
        assert_eq!(memory.step(true)?, file.step(true)?);
    }
    // 错误基目录必须报引用错误；不能回退到工作目录或默读另一个输入。
    assert!(Input::parse_with_base(raw, root, &config, false).is_err());
    println!("{{\"status\":\"pass\",\"memory_input_exists\":false,\"ticks_equal\":4,\"wrong_base_rejected\":true}}");
    Ok(())
}
