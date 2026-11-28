"""Shared commands and lossless stdout comparisons. Run with Python 3.10+."""
import json
from itertools import zip_longest
from pathlib import Path
from subprocess import run

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT.parent / "规则模型"
GOLD = MODEL / "对拍" / "黄金"
RUST = ROOT / "target" / "release" / "endfield-sim"


def build():
    run(["cargo", "build", "--locked", "--release"], cwd=ROOT, check=True)


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def outputs(path):
    def invoke(cmd, cwd):
        p = run([*cmd, str(path)], cwd=cwd, capture_output=True)
        if p.returncode:
            raise RuntimeError(f"{path} {cmd[0]} 退出 {p.returncode}\n{p.stderr.decode()}")
        return p.stdout

    return invoke([RUST], ROOT), invoke(["lake", "exe", "对拍"], MODEL)


def equal(label, a, b):
    if a == b:
        return
    for i, (x, y) in enumerate(zip_longest(a.splitlines(True), b.splitlines(True)), 1):
        if x != y:
            raise AssertionError(f"{label} 第 {i} 行不同\n{x!r}\n{y!r}")
