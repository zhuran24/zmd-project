import json
from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory
from pathlib import Path

from common import ROOT, GOLD, RUST, build, compact, outputs, equal
from subprocess import run


def verify(path):
    doc = json.loads(path.read_bytes())
    expected = bytearray()
    steps = 0
    for s in doc["段"]:
        for row in s.pop("期望"):
            expected.extend((compact(row) + "\n").encode())
        steps += sum(op[1] for op in s["操作"] if op[0] == "走")
    with TemporaryDirectory(dir=ROOT / "target") as scratch:
        bare = Path(scratch) / path.name
        bare.write_text(compact(doc))
        rust, lean = outputs(bare)
        equal(path.name + " Rust/黄金", rust, expected)
        equal(path.name + " Rust/Lean", rust, lean)
    checked = run([RUST, path], capture_output=True, check=True)
    equal(path.name + " 带期望", checked.stdout, expected)
    return len(doc["段"]), steps, rust.count(b"\n")


if __name__ == "__main__":
    build()
    files = sorted(GOLD.glob("*.json"))
    assert len(files) == 43
    with ThreadPoolExecutor(max_workers=4) as pool:
        segments, steps, rows = map(sum, zip(*pool.map(verify, files)))
    print(f"{len(files)} 份，{segments} 段，{steps} 步，{rows} 行，三方逐字节全等")
