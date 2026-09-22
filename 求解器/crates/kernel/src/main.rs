//! 第四轮§4.6、§4.8：有限轨迹命令行；输出可关且仍执行同一引擎。
use kernel::{
    output::{run_record, stopped_record},
    value::read_json,
    Config, Engine, Input, Result, Stop,
};
use std::{path::PathBuf, time::Instant};
/// 第四轮§4.6：严格参数解析，未知开关拒绝，不静默忽略。
fn run() -> Result<bool> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if args.is_empty() {
        return Err(Stop::invalid("cli","用法：kernel run <input.json> --config <配置.json> --ticks N --out <记录.json> [--format full_state_each_instant|checkpoint_delta] [--checkpoint-interval K]；输出关闭用 --no-output"));
    }
    let command = &args[0];
    if command == "verify-batch" {
        let directory = args
            .get(1)
            .ok_or_else(|| Stop::invalid("verify-batch", "缺目录"))?;
        let mut child = std::process::Command::new("python");
        child
            .arg("-B")
            .arg(concat!(env!("CARGO_MANIFEST_DIR"), "/tests/verify_all.py"))
            .arg("--dry")
            .arg(directory)
            .args(&args[2..]);
        child.env(
            "KERNEL_BIN",
            std::env::current_exe().map_err(|e| Stop::invalid("binary", e.to_string()))?,
        );
        return Ok(child
            .status()
            .map_err(|e| Stop::invalid("verify-batch", e.to_string()))?
            .success());
    }

    if ![
        "run",
        "check",
        "request",
        "seed",
        "cycle",
        "verify-cycle",
        "verify-record",
        "checkpoint",
    ]
    .contains(&command.as_str())
        || args.len() < 2
    {
        return Err(Stop::invalid(
            "cli",
            "子命令须为 run/check/request，并给输入或轴名",
        ));
    }
    let mut config_path = None;
    let mut out = None;
    let mut ticks = None;
    let mut format = "full_state_each_instant".to_string();
    let mut interval = 10usize;
    let mut no_output = false;
    let mut no_record = false;
    let mut cycle_domain = false;
    let mut search_interval = 32usize;
    let mut cache = true;
    let mut max_sweeps = 100_000usize;
    let mut index = 2;
    while index < args.len() {
        let key = &args[index];
        if key == "--no-record" {
            no_record = true;
            index += 1;
            continue;
        }
        if key == "--cycle-domain" {
            cycle_domain = true;
            index += 1;
            continue;
        }
        if key == "--no-cache" {
            cache = false;
            index += 1;
            continue;
        }
        if key == "--no-output" {
            no_output = true;
            index += 1;
            continue;
        }
        let value = args
            .get(index + 1)
            .ok_or_else(|| Stop::invalid("cli", "开关缺值"))?;
        match key.as_str() {
            "--search-checkpoint-interval" => {
                search_interval = value
                    .parse()
                    .map_err(|_| Stop::invalid("search_interval", "须为正整数"))?;
                if search_interval == 0 {
                    return Err(Stop::invalid("search_interval", "须为正整数"));
                }
            }
            "--config" => config_path = Some(PathBuf::from(value)),
            "--out" => out = Some(PathBuf::from(value)),
            "--ticks" | "--max-ticks" => {
                ticks = Some(
                    value
                        .parse::<usize>()
                        .map_err(|_| Stop::invalid("cli.ticks", "须为非负整数"))?,
                )
            }
            "--max-sweeps" => {
                max_sweeps = value
                    .parse()
                    .map_err(|_| Stop::invalid("max_sweeps", "须为正整数"))?;
                if max_sweeps == 0 {
                    return Err(Stop::invalid("max_sweeps", "须为正整数"));
                }
            }
            "--format" => format = value.clone(),
            "--checkpoint-interval" => {
                interval = value
                    .parse()
                    .map_err(|_| Stop::invalid("cli.interval", "须为正整数"))?
            }
            _ => return Err(Stop::invalid("cli", format!("未知选项 {key}"))),
        }
        index += 2;
    }
    let cfg = config_path.ok_or_else(|| Stop::invalid("cli", "缺 --config"))?;
    let execute = || -> Result<serde_json::Value> {
        let config = Config::parse(read_json(&cfg)?)?;
        if command == "request" {
            let axis = kernel::value::decode(serde_json::json!(args[1]), "request.axis")?;
            config.request(axis, "cli.request")?;
            return Ok(serde_json::json!({"status":"input_checked"}));
        }
        let path = PathBuf::from(&args[1])
            .canonicalize()
            .map_err(|e| Stop::invalid("input", e.to_string()))?;
        if command == "verify-record" {
            let record = read_json(&path)?;
            let base = path.parent().unwrap();
            let source = kernel::output::record_input_path(&record, base)?;
            kernel::output::verify_record_at(
                &record,
                Input::load(&source, &config, false)?,
                &config,
                &cfg,
                base,
            )?;
            return Ok(serde_json::json!({"status":"input_checked","verified_record":path}));
        }
        if command == "verify-cycle" {
            return kernel::cycle::verify_cycle_at(
                &read_json(&path)?,
                &config,
                &cfg,
                path.parent().unwrap(),
            );
        }
        if command == "checkpoint" {
            let artifact = read_json(&path)?;
            let (source, state) = if artifact["schema"] == "kernel-cycle-v3" {
                kernel::cycle::verify_cycle_at(&artifact, &config, &cfg, path.parent().unwrap())?;
                let source = artifact["replay_input_ref"]["path"]
                    .as_str()
                    .filter(|p| !p.is_empty())
                    .ok_or_else(|| {
                        Stop::invalid(
                            "checkpoint.recovery",
                            "诊断已复现，但装载失败外壳没有可恢复输入或完整状态",
                        )
                    })?;
                let state = if artifact["cycle"].is_null() {
                    &artifact["last_state"]
                } else {
                    &artifact["cycle"]["end_state"]
                };
                if !state.is_object() {
                    return Err(Stop::invalid("checkpoint.recovery", "缺可恢复完整状态"));
                }
                (path.parent().unwrap().join(source), state.clone())
            } else {
                let base = path.parent().unwrap();
                let source = kernel::output::record_input_path(&artifact, base)?;
                kernel::output::verify_record_at(
                    &artifact,
                    Input::load(&source, &config, false)?,
                    &config,
                    &cfg,
                    base,
                )?;
                let trace = kernel::output::decode_trace(&artifact["trace"])?;
                (
                    source,
                    trace["ticks"]
                        .as_array()
                        .and_then(|a| a.last())
                        .map(|r| r["state"].clone())
                        .unwrap_or(trace["start_state"].clone()),
                )
            };
            let input = Input::load(&source, &config, false)?;
            let resumed = kernel::cycle::checkpoint_input(&input, state, &config)?;
            return Input::canonicalize_seed(resumed.raw, source.parent().unwrap(), &config);
        }
        if command == "seed" {
            return Input::canonicalize_seed(read_json(&path)?, path.parent().unwrap(), &config);
        }
        let input = Input::load(&path, &config, command == "check" && !cycle_domain)?;
        if command == "check" {
            if cycle_domain {
                let report = Engine::check_cycle_domain(input)?;
                let passed = report
                    .as_array()
                    .unwrap()
                    .iter()
                    .all(|r| r["status"] == "pass");
                return Ok(
                    serde_json::json!({"status":if passed{"input_checked"}else{"unsupported"},"domain_report":report,"trajectory_executed":false}),
                );
            }
            return Ok(
                serde_json::json!({"status":"input_checked","units":input.geometry.units.len(),"physical_channels":input.geometry.channels.len(),"buffer_channels":input.geometry.buffers.len(),"catalog_sha256":input.catalog.sha256}),
            );
        }
        let n = ticks.ok_or_else(|| Stop::invalid("cli", "缺 --ticks"))?;
        if command == "cycle" {
            let record_path = if no_record {
                None
            } else {
                let dest = out.as_ref().ok_or_else(|| {
                    Stop::invalid("cli.cycle", "有记录模式须给 --out；无记录用 --no-record")
                })?;
                Some(dest.with_file_name(format!(
                    "{}.record.json",
                    dest.file_stem().unwrap().to_string_lossy()
                )))
            };
            let options = kernel::cycle::SearchOptions {
                checkpoint_interval: search_interval,
                record_path,
            };
            return kernel::cycle::run_cycle_with_options(
                input, &config, &cfg, n, max_sweeps, &options,
            );
        }
        if n == 0 && !no_output {
            return Err(Stop::invalid("ticks", "记录至少需要一个时刻"));
        }
        let mut engine = Engine::new(input)?;
        engine.max_sweeps = max_sweeps;
        engine.set_cache_enabled(cache);
        if no_output {
            let start = Instant::now();
            let mut completed = 0usize;
            let mut stop = None;
            for _ in 0..n {
                match engine.step(false) {
                    Ok(_) => completed += 1,
                    Err(e) => {
                        stop = Some(e);
                        break;
                    }
                }
            }
            if let Some(e) = stop {
                return Ok(
                    serde_json::json!({"status":e.status,"ticks":n,"completed_ticks":completed,"elapsed_ns":start.elapsed().as_nanos().to_string(),"output":"disabled","statistics":{"completed":0,"inconclusive":usize::from(e.status=="inconclusive"),"stopped":usize::from(e.status!="inconclusive")},"stop":e}),
                );
            }
            Ok(
                serde_json::json!({"status":"completed","ticks":n,"elapsed_ns":start.elapsed().as_nanos().to_string(),"output":"disabled","statistics":{"completed":1,"inconclusive":0,"stopped":0},"completed_batches":engine.completed_batches,"actual_inbound":engine.delivery,"final_inventory":engine.inventory_totals()?}),
            )
        } else {
            run_record(engine, &config, &cfg, n, &format, interval)
        }
    };
    let (record, success) = match execute() {
        Ok(r) => {
            let ok = r["status"] == "completed"
                || r["status"] == "input_checked"
                || r["schema"] == "kernel-input-v3"
                || (command == "cycle"
                    && ["cycle_found", "diagnostic_cycle", "counterexample", "inconclusive"]
                        .contains(&r["status"].as_str().unwrap_or("")));
            (r, ok)
        }
        Err(e) => {
            let raw = read_json(std::path::Path::new(&args[1])).ok();
            let meeting = raw
                .as_ref()
                .and_then(|v| {
                    v["parameters"]["fixed"]["connection.port_meeting"]["value"]
                        .as_str()
                })
                .filter(|s| *s == "shared_edge_opposite")
                .unwrap_or("");
            let mut record = if command == "cycle" {
                kernel::cycle::load_stopped_cycle(&e, ticks.unwrap_or(1), max_sweeps, meeting)
            } else {
                stopped_record(&e)
            };
            if command == "check" && cycle_domain {
                record = serde_json::json!({"status":e.status,"domain_report":kernel::cycle::load_stopped_cycle(&e,1,max_sweeps,meeting)["domain_report"],"trajectory_executed":false});
            } else if command != "cycle" && !meeting.is_empty() {
                record["port_meeting"] = serde_json::json!(meeting);
            }
            if command == "cycle" {
                record["record_mode"] =
                    serde_json::json!(if no_record { "none" } else { "referenced" });
                kernel::cycle::attach_load_context(
                    &mut record,
                    std::path::Path::new(&args[1]),
                    &cfg,
                )?;
            }
            (record, false)
        }
    };
    let text = serde_json::to_string_pretty(&record)
        .map_err(|e| Stop::invalid("output", e.to_string()))?
        + "\n";
    if let Some(path) = out {
        std::fs::write(&path, text)
            .map_err(|e| Stop::invalid(path.display().to_string(), e.to_string()))?;
        println!(
            "{}",
            serde_json::json!({"status":record["status"],"out":path})
        );
    } else if command == "run" && !no_output {
        return Err(Stop::invalid(
            "cli",
            "记录输出须指定 --out；性能运行用 --no-output",
        ));
    } else {
        print!("{text}");
    }
    Ok(success)
}
/// 第四轮§4.6：失败以非零退出，不吞错误或把停止报成功。
fn main() {
    match run() {
        Ok(true) => {}
        Ok(false) => std::process::exit(2),
        Err(e) => {
            eprintln!("{e}");
            std::process::exit(2)
        }
    }
}
