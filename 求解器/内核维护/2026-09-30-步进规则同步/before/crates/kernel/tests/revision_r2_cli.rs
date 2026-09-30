//! 第2轮修订：实际CLI与独立Python验收的元数据和输入负例纳入cargo test。
mod support;
use std::{path::PathBuf, process::Command};

/// 内核输出§3、内核输入§1–§6：真文件、真进程及有效对照同时核验。
#[test]
fn revision_r2_cli_and_python_record_negatives() {
    let evidence = support::evidence_dir("revision_r2_cli");
    let script = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/revision_r2_cli.py");
    let output = Command::new("python")
        .arg("-B")
        .env("KERNEL_TEST_INSTANCE_DIR", &evidence)
        .arg(script)
        .arg(env!("CARGO_BIN_EXE_kernel"))
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
}
