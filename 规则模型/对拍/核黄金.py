"""只把输入交给对拍可执行程序，按 UTF-8 字节核对每行期望。"""
from pathlib import Path
from itertools import zip_longest
import json
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def verify(path, scratch):
    doc = json.loads(path.read_bytes())
    expected = []
    ticks = 0
    for s in doc["段"]:
        for row in s.pop("期望"):
            expected.append((json.dumps(row, ensure_ascii=False, separators=(",", ":"),
                                        sort_keys=True) + "\n").encode())
        ticks += sum(op[1] for op in s["操作"] if op[0] == "走")
    source = Path(scratch) / "输入.json"
    source.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
    proc = subprocess.run(["lake", "exe", "对拍", str(source)], cwd=ROOT, stdout=subprocess.PIPE,
                          check=True)
    for i, (want, got) in enumerate(zip_longest(expected, proc.stdout.splitlines(True)), 1):
        if want != got:
            raise ValueError(f"{path.name} 第 {i} 行有差异，期望 {want!r}，实际 {got!r}")
    return ticks, len(expected)


if __name__ == "__main__":
    subprocess.run(["lake", "build", "对拍"], cwd=ROOT, check=True)
    paths = sorted((ROOT / "对拍/黄金").glob("*.json"))
    replay_files = {p.stem for p in (ROOT / "Endfield/回放").glob("*.lean")}
    excluded = {"工具", "格子工具", "出货先后", "分流器出口变动"}
    difference = (replay_files - excluded) ^ {p.stem for p in paths if not p.stem.startswith("接口-")}
    if difference:
        raise SystemExit("回放与黄金文件清单不符 " + "、".join(sorted(difference)))
    size = sum(p.stat().st_size for p in paths)
    if size > 20_000_000:
        raise SystemExit(f"超出 20 MB，共 {size} 字节")
    with tempfile.TemporaryDirectory(dir=ROOT / "对拍") as scratch:
        results = []
        for path in paths:
            ticks, rows = verify(path, scratch)
            print(f"{path.stem} {ticks} 步，{rows} 行")
            results.append((ticks, rows))
    print(f"{len(paths)} 份，{sum(i for i,_ in results)} 步，{sum(n for _,n in results)} 行逐字节相同，{size} 字节")
