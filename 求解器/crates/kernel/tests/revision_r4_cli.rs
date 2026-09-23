//! 第4轮：使用本次Cargo构建的公开CLI核验真实文件及独立schema。
mod support;
use std::process::Command;

#[test]
fn revision_r4_public_cli_regressions() {
    let evidence = support::evidence_dir("revision_r4_cli");
    let result = Command::new("python")
        .arg("-B")
        .env("KERNEL_TEST_INSTANCE_DIR", &evidence)
        .arg(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/tests/revision_r4_cli.py"
        ))
        .env("KERNEL_BIN", env!("CARGO_BIN_EXE_kernel"))
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "{}\n{}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );
}
