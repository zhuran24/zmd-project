"""Run the whole tier-② differential-fuzz suite as one regression gate.

Every slice already exposes `--self-test` (discrimination proof) and
`--batch N --seed S` (run the SUT vs the independent oracle). This runner invokes
all of them in sequence as separate processes (matching how they are run by
hand), aggregates exit codes, and returns non-zero if any slice's self-test
fails or any batch finds a mismatch / anomaly.

Intended use: the differential fuzz's standing job is to regression-guard the
certified path. Whenever the upstream line lands a `src/` change, re-run this
(it needs no GitHub / external calls, just CP-SAT locally):

    python cc_context/verification/diff_fuzz/run_all.py            # default seed 0
    python cc_context/verification/diff_fuzz/run_all.py 7          # seed 7
    python cc_context/verification/diff_fuzz/run_all.py 7 --quick  # smaller batches

Each slice keeps its own independent verifier; this only orchestrates them.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PY = sys.executable

# (filename, full-run batch size, quick batch size)
SLICES = [
    ("routing_connectivity_diff.py", 150, 60),
    ("master_geometry_diff.py", 120, 50),
    ("binding_model_diff.py", 150, 60),
    ("routing_aware_binding_diff.py", 120, 50),
]


def _run(path: Path, args: list) -> int:
    proc = subprocess.run([PY, str(path), *args], cwd=str(REPO))
    return int(proc.returncode)


def main() -> int:
    seed = 0
    quick = "--quick" in sys.argv
    for a in sys.argv[1:]:
        if a.isdigit():
            seed = int(a)

    results = []
    rc = 0
    for fname, full_batch, quick_batch in SLICES:
        path = HERE / fname
        if not path.exists():
            print(f"[MISSING] {fname}")
            rc |= 1
            results.append((fname, "MISSING"))
            continue
        batch = quick_batch if quick else full_batch
        st_rc = _run(path, ["--self-test"])
        bt_rc = _run(path, ["--batch", str(batch), "--seed", str(seed)])
        slice_rc = st_rc | bt_rc
        rc |= slice_rc
        results.append((fname, "OK" if slice_rc == 0 else f"FAIL(self={st_rc},batch={bt_rc})"))

    print("=" * 64)
    print(f"diff-fuzz suite (seed={seed}, {'quick' if quick else 'full'}):")
    for fname, status in results:
        print(f"  [{'OK' if status == 'OK' else 'FAIL'}] {fname}: {status}")
    print("ALL CLEAN" if rc == 0 else "SUITE HAS FAILURES — investigate before trusting certified soundness")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
