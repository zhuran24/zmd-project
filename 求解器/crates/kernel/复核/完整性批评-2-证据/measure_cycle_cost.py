#!/usr/bin/env python3
"""完整性批评-内核-2：对比 run --no-output 与 cycle 两种模式的每刻代价。

K7 的 benchmark 只测 run --no-output；执行器实际用的是 cycle（逐刻算生产键、
留全状态查重、再整体重放生成 run_record 并内嵌进证书）。本脚本两种模式都测，
并记证书体积与子进程峰值 RSS，输出写调用方指定的路径，不改仓库内任何既有文件。
"""
import json, resource, subprocess, sys, time
from pathlib import Path

ROOT = Path("/home/zhuran24/zmd-research-fresh/求解器")
BIN = str(ROOT / "target/release/kernel")
CFG = str(ROOT / "规格/内核配置-v1.json")
FIX = ROOT / "crates/kernel/tests/fixtures"


def timed(cmd):
    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    t = time.perf_counter_ns()
    r = subprocess.run(cmd, capture_output=True, text=True)
    ns = time.perf_counter_ns() - t
    after = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return ns / 1e6, r, max(after, before) / 1024.0


def main(outdir):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in ("benchmark_brick_60", "benchmark_brick", "benchmark_candidate_b"):
        src = str(FIX / (name + ".json"))
        ms, r, _ = timed([BIN, "run", src, "--config", CFG, "--ticks", "12", "--no-output"])
        engine = json.loads(r.stdout) if r.stdout.lstrip().startswith("{") else {}
        rows.append({"case": name, "mode": "run --no-output", "ticks": 12,
                     "engine_ms_per_tick": int(engine.get("elapsed_ns", 0)) / 1e6 / 12,
                     "wall_ms": ms, "completed_batches": engine.get("completed_batches"),
                     "returncode": r.returncode})
    for name, ns in (("benchmark_brick_60", (12, 24, 48)), ("benchmark_candidate_b", (5, 10))):
        src = str(FIX / (name + ".json"))
        for n in ns:
            dest = out / f"{name}-cycle-{n}.json"
            ms, r, rss = timed([BIN, "cycle", src, "--config", CFG, "--max-ticks", str(n), "--out", str(dest)])
            size = dest.stat().st_size if dest.exists() else 0
            dest.unlink(missing_ok=True)
            rows.append({"case": name, "mode": "cycle", "ticks": n, "wall_ms": ms,
                         "wall_ms_per_tick": ms / n, "out_bytes": size,
                         "out_mb_per_tick": size / 1048576 / n,
                         "children_peak_rss_mb": rss, "rss_mb_per_tick": rss / n,
                         "status": (json.loads(r.stdout).get("status") if r.stdout.lstrip().startswith("{") else None),
                         "returncode": r.returncode})
    result = {"schema": "critic2-cycle-cost-v1", "binary": BIN, "rows": rows,
              "note": "engine_ms_per_tick 与 evidence/benchmark.json 同口径（只计推进）；cycle 行是整进程 wall，含生产键、查重、重放与证书序列化。"}
    (out / "循环代价实测.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
