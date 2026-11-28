"""执行各格子回放的全部 #guard，在临时调用方观察格子操作，按文件去重。"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Endfield/回放"
DEST = ROOT / "对拍/场地黄金"
IMPORT = re.compile(r"import Endfield\.«回放»\.«([^»]+)»")


def dependencies(name):
    return IMPORT.findall((SOURCE / (name + ".lean")).read_text())


def grid_replay(name):
    return any(dep == "格子工具" or grid_replay(dep) for dep in dependencies(name))


def harness(name):
    modules = {}
    imports = {"import «对拍».«场地取样»"}

    def include(mod):
        if mod in modules:
            return
        code = []
        skip = False
        for line in (SOURCE / (mod + ".lean")).read_text().splitlines():
            if line.startswith("import "):
                match = IMPORT.fullmatch(line)
                if match:
                    include(match[1])
                else:
                    imports.add(line)
                continue
            if line.startswith("#guard ") and mod != name:
                skip = True
                continue
            if skip and line and not line[0].isspace():
                skip = False
            if not skip:
                code.append(line)
        source = "\n".join(code).replace("«回放»", "«场地取样回放»")
        source = source.replace("Endfield.«格子».«作用»", "Oracle.GridTrace.observe")
        if mod in {"供电范围", "供电范围右上角"}:
            source = source.replace("«场地».«有电»", "Oracle.GridTrace.power")
        modules[mod] = source

    include(name)
    return "\n".join(sorted(imports)) + "\nset_option maxRecDepth 32768\n" + "\n".join(modules.values())


def packed(x):
    return json.dumps(x, ensure_ascii=False, separators=(",", ":"))


def export(name, check):
    with tempfile.TemporaryDirectory() as tmp:
        temp = Path(tmp)
        source = temp / "Replay.lean"
        source.write_text(harness(name))
        rows = {}
        with subprocess.Popen(["lake", "env", "lean", "-j1", str(source)], cwd=ROOT,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as p:
            errors = []
            for line in p.stdout:
                if not line.startswith("@field "):
                    if line.strip():
                        errors.append(line.rstrip())
                    continue
                example, ref = json.loads(line[7:])
                key = packed(example)
                if key not in rows or rows[key] is None:
                    rows[key] = ref
                elif ref is not None and rows[key] != ref:
                    raise ValueError(f"{name} 同一摆件表的回放历史不一致")
            if p.wait() or errors:
                raise RuntimeError(name + "\n" + "\n".join(errors[:40]))
        if not rows:
            raise ValueError(name + " 没有读到摆件表")
        path = temp / "输入.json"
        path.write_text('{"版本":1,"场地":[\n' + ",\n".join(rows) + "\n]}\n")
        output = subprocess.check_output([ROOT / ".lake/build/bin/对拍", path], cwd=ROOT)
        # 每份去重后的原始回放历史交给 Lean 自检，连同步进入口一并检查。
        refs = temp / "回放历史.jsonl"
        with refs.open("w") as f:
            for case, ref in rows.items():
                if ref is not None:
                    f.write("[" + case + "," + packed(ref) + "]\n")
        subprocess.run(["lake", "env", "lean", "--run", "对拍/核场地.lean", str(refs)],
                       cwd=ROOT, check=True, stdout=subprocess.PIPE)
        for suffix, data in [(".json", path.read_bytes()), (".jsonl", output)]:
            dest = DEST / (name + suffix)
            if check:
                if dest.read_bytes() != data:
                    raise ValueError(f"{dest.name} 与当前回放导出不符")
            else:
                dest.write_bytes(data)
        clean = sum(isinstance(r, list) for r in rows.values())
        print(f"{name} {len(rows)} 例，{clean} 个回放历史，{len(rows)-len(refs.read_text().splitlines())} 个静态场地", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="*", help="回放名，默认全部格子回放")
    parser.add_argument("-j", type=int, default=4)
    parser.add_argument("--check", action="store_true", help="只核现场回放与已存黄金")
    opts = parser.parse_args()
    subprocess.run(["lake", "build", "对拍库", "对拍"], cwd=ROOT, check=True)
    DEST.mkdir(exist_ok=True)
    names = opts.names or sorted(p.stem for p in SOURCE.glob("*.lean") if grid_replay(p.stem))
    with ThreadPoolExecutor(max_workers=opts.j) as pool:
        list(pool.map(lambda name: export(name, opts.check), names))
