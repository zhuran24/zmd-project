//! 修订r5：公共入口回归包含不同cwd、两种记录编码及诊断恢复拒收。
use std::process::Command;

#[test]
fn revision_r5_public_cli_regressions() {
    let result = Command::new("python")
        .arg("-B")
        .arg(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/tests/revision_r5_cli.py"
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
