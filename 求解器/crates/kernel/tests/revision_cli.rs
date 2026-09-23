//! 第1轮修订：公开CLI和独立Python落盘验收均进入cargo test。
mod support;
use std::{path::PathBuf, process::Command};

/// 内核输入§2、§3与内核输出§1–§3：生成真实文件再验收，篡改必须非零拒绝。
#[test]
fn revision_cli_and_python_record_negatives() {
    let evidence = support::evidence_dir("revision_cli");
    let script = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/revision_cli.py");
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
