//! Test-only output allocation shared by all public CLI harnesses.
use std::{path::PathBuf, process::Command};

pub fn evidence_dir(name: &str) -> PathBuf {
    let output = Command::new("python")
        .arg("-B")
        .arg(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/tests/evidence_paths.py"
        ))
        .arg(name)
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .output()
        .expect("start test output allocator");
    assert!(
        output.status.success(),
        "output allocation failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    eprint!("{}", String::from_utf8_lossy(&output.stderr));
    PathBuf::from(
        String::from_utf8(output.stdout)
            .expect("allocator path is UTF-8")
            .trim(),
    )
}
