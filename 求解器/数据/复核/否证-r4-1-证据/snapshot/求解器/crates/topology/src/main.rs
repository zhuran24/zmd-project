use std::{env, fs, process};
fn main() {
    let args: Vec<_> = env::args().collect();
    if args.len() != 2 {
        eprintln!("用法：topology <contract.json>；报告写至标准输出");
        process::exit(2);
    }
    let result = fs::read_to_string(&args[1])
        .map_err(|e| e.to_string())
        .and_then(|s| topology::load(&s));
    match result {
        Ok(c) => {
            let report = topology::validate(&c);
            print!("{}", report.markdown());
            if report.failures() > 0 {
                process::exit(1);
            }
        }
        Err(e) => {
            eprintln!("契约加载失败：{e}");
            process::exit(2);
        }
    }
}
