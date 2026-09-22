//! 第五轮K5/K8：真实CLI的资源统计及装载停止仍遵守循环外壳。
use serde_json::{json, Value};
use std::{path::PathBuf, process::Command};
#[test]
fn round5_cli_resource_statistics_and_cycle_load_stop() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .unwrap();
    let config = root.join("规格/内核配置-v1.json");
    let out = root.join("crates/kernel/evidence/round5");
    let exported = out.join("relocated-seed.json");
    let process = Command::new(env!("CARGO_BIN_EXE_kernel"))
        .arg("seed")
        .arg(root.join("数据/样例/混做粉碎机两下游.json"))
        .arg("--config")
        .arg(&config)
        .arg("--out")
        .arg(&exported)
        .output()
        .unwrap();
    assert!(
        process.status.success(),
        "{}",
        String::from_utf8_lossy(&process.stderr)
    );
    let process = Command::new(env!("CARGO_BIN_EXE_kernel"))
        .arg("run")
        .arg(&exported)
        .arg("--config")
        .arg(&config)
        .args(["--ticks", "4", "--no-output"])
        .output()
        .unwrap();
    assert!(
        process.status.success(),
        "{}",
        String::from_utf8_lossy(&process.stdout)
    );
    assert_eq!(
        serde_json::from_slice::<Value>(&process.stdout).unwrap()["status"],
        "completed"
    );
    let process = Command::new(env!("CARGO_BIN_EXE_kernel"))
        .arg("run")
        .arg(root.join("数据/样例/生产循环环带.json"))
        .arg("--config")
        .arg(&config)
        .args(["--ticks", "2", "--max-sweeps", "1", "--no-output"])
        .output()
        .unwrap();
    assert_eq!(process.status.code(), Some(2));
    let report: Value = serde_json::from_slice(&process.stdout).unwrap();
    assert_eq!(report["status"], "inconclusive");
    assert_eq!(report["statistics"]["inconclusive"], 1);
    assert_eq!(report["completed_ticks"], 0);
    std::fs::write(
        out.join("resource-statistics.json"),
        serde_json::to_vec_pretty(&report).unwrap(),
    )
    .unwrap();
    let input = out.join("invalid-cycle-input.json");
    let record = out.join("invalid-cycle-result.json");
    std::fs::write(&input, json!({"schema":"kernel-input-v3"}).to_string()).unwrap();
    let process = Command::new(env!("CARGO_BIN_EXE_kernel"))
        .arg("cycle")
        .arg(&input)
        .arg("--config")
        .arg(&config)
        .args(["--max-ticks", "2", "--out"])
        .arg(&record)
        .output()
        .unwrap();
    assert_eq!(process.status.code(), Some(2));
    let result: Value = serde_json::from_slice(&std::fs::read(&record).unwrap()).unwrap();
    assert_eq!(result["schema"], "kernel-cycle-v2");
    assert_eq!(result["status"], "invalid_input");
    assert!(result["cycle"].is_null());
}
