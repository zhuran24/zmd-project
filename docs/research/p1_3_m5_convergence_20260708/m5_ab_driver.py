"""M5 convergence A/B driver (P1.3, 2026-07-08).

Runs the cell matrix {ghost rects} x {attach on, off}, each cell in its OWN
subprocess (M1 verdict: models linger in-process — per-cell isolation keeps
RAM flat and wall-clock attribution clean), then writes a summary JSON.

Usage:
  python m5_ab_driver.py --ghosts 40x40 30x30 --master-seconds 300 \
      --binding-seconds 300 --routing-seconds 300 --max-iterations 15 \
      --out-dir results_smoke
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ghosts", nargs="+", required=True, help="e.g. 40x40 30x30")
    parser.add_argument("--master-seconds", type=float, default=300.0)
    parser.add_argument("--binding-seconds", type=float, default=300.0)
    parser.add_argument("--routing-seconds", type=float, default=300.0)
    parser.add_argument("--max-iterations", type=int, default=15)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    out_dir = args.out_dir if args.out_dir.is_absolute() else HERE / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    cells = []
    for ghost in args.ghosts:
        w, h = (int(v) for v in ghost.lower().split("x"))
        for attach in ("off", "on"):
            cells.append((w, h, attach))

    summary = []
    for w, h, attach in cells:
        tag = f"g{w}x{h}_{attach}"
        out_json = out_dir / f"cell_{tag}.json"
        cmd = [
            sys.executable,
            str(HERE / "m5_cell_runner.py"),
            "--ghost-w", str(w),
            "--ghost-h", str(h),
            "--attach", attach,
            "--master-seconds", str(args.master_seconds),
            "--binding-seconds", str(args.binding_seconds),
            "--routing-seconds", str(args.routing_seconds),
            "--max-iterations", str(args.max_iterations),
            "--out", str(out_json),
        ]
        print(f"[m5] cell {tag} starting", flush=True)
        t0 = time.perf_counter()
        proc = subprocess.run(
            cmd, cwd=str(HERE.parents[2]), capture_output=True, text=True
        )
        wall = round(time.perf_counter() - t0, 1)
        record = {"cell": tag, "exit": proc.returncode, "subprocess_wall": wall}
        if out_json.exists():
            record["result"] = json.loads(out_json.read_text(encoding="utf-8"))
        else:
            record["stdout_tail"] = proc.stdout[-2000:]
            record["stderr_tail"] = proc.stderr[-2000:]
        summary.append(record)
        print(f"[m5] cell {tag} done exit={proc.returncode} wall={wall}s", flush=True)

    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[m5] all {len(cells)} cells done -> {out_dir / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
