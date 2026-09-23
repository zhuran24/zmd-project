//! 第3轮：公开入口回归必须由本次Cargo构建的CLI执行。
mod support;
use std::process::Command;

#[test]
fn revision_r3_public_cli_regressions() {
    let evidence = support::evidence_dir("revision_r3_cli");
    let output = Command::new("python")
        .arg("-B")
        .env("KERNEL_TEST_INSTANCE_DIR", &evidence)
        .arg(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/tests/revision_r3_cli.py"
        ))
        .env("KERNEL_BIN", env!("CARGO_BIN_EXE_kernel"))
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
}
