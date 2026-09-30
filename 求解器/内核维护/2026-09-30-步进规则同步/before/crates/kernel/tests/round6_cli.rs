//! 第六轮公开CLI：引用、两模式、独立重跑、检查点及装载边界。
mod support;
use std::process::Command;
#[test]
fn round6_public_cli_regressions() {
    let evidence = support::evidence_dir("round6_cli");
    let result = Command::new("python")
        .arg("-B")
        .env("KERNEL_TEST_INSTANCE_DIR", &evidence)
        .arg(concat!(env!("CARGO_MANIFEST_DIR"), "/tests/round6_cli.py"))
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
