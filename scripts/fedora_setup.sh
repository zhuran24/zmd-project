#!/usr/bin/env bash
#
# Phase 3C Fedora setup — Endfield IndustrialPlanner solver
#
# Default: dry-run, prints what *would* be done. Pass --apply to actually
# execute the steps. Run from project root.
#
# Covers R2 audit a8a152668dd067210 recommendations:
# - THP (transparent huge pages, madvise mode)
# - tcmalloc / jemalloc allocator swap (Phase 3C P1 #24 cache-aware pack)
# - cgroups v2 verification
# - io_uring availability (kernel ≥ 6.10 default)
#
# Tested target: Fedora Workstation 41/42.

set -euo pipefail

DRY_RUN=1
if [[ "${1:-}" == "--apply" ]]; then
    DRY_RUN=0
fi

run() {
    if [[ "${DRY_RUN}" -eq 1 ]]; then
        echo "DRY-RUN: $*"
    else
        echo "RUN: $*"
        eval "$*"
    fi
}

echo "=== Phase 3C Fedora setup ==="
if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "(dry-run mode — pass --apply to actually execute)"
fi
echo

# 1. Verify Fedora
if [[ -f /etc/fedora-release ]]; then
    cat /etc/fedora-release
else
    echo "WARNING: /etc/fedora-release missing — script targets Fedora, continuing anyway"
fi
echo

# 2. Python 3.13
echo "--- Python 3.13 ---"
if command -v python3.13 >/dev/null 2>&1; then
    python3.13 --version
else
    run "sudo dnf install -y python3.13 python3.13-devel"
fi
echo

# 3. venv + project deps
echo "--- venv + requirements.txt ---"
if [[ ! -d .venv ]]; then
    run "python3.13 -m venv .venv"
fi
run "source .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt"
echo

# 4. Performance allocators (R2 a8a152668dd067210)
echo "--- Performance allocators ---"
run "sudo dnf install -y gperftools-libs gperftools-devel jemalloc jemalloc-devel"
echo "After install, paths to LD_PRELOAD:"
echo "  tcmalloc: /usr/lib64/libtcmalloc.so.4"
echo "  jemalloc: /usr/lib64/libjemalloc.so.2"
echo "(mimalloc not in Fedora repos; build from source if needed)"
echo

# 5. THP setting check
echo "--- THP ---"
if [[ -f /sys/kernel/mm/transparent_hugepage/enabled ]]; then
    echo "current: $(cat /sys/kernel/mm/transparent_hugepage/enabled)"
    echo "(R2 audit recommends 'madvise' for fine control on long-run jobs)"
    echo "to set: sudo sh -c 'echo madvise > /sys/kernel/mm/transparent_hugepage/enabled'"
else
    echo "THP sysfs path missing — kernel may not support"
fi
echo

# 6. cgroups v2
echo "--- cgroups v2 ---"
if mount | grep -q cgroup2; then
    echo "cgroups v2 mounted (Fedora 41+ default)"
else
    echo "WARNING: cgroups v2 not mounted — long-run job memory limits may be unreliable"
fi
echo

# 7. ortools sanity
echo "--- ortools sanity ---"
run "source .venv/bin/activate && python -c 'from ortools.sat.python import cp_model; s=cp_model.CpSolver(); print(\"ortools OK, default num_search_workers:\", s.parameters.num_search_workers)'"
echo

# 8. Project pytest baseline
echo "--- Project test baseline (recommended next step) ---"
echo "  source .venv/bin/activate"
echo "  python -m pytest src/tests/ -q"
echo "Expected on a clean clone: 2027 passed, 60 skipped (Codex-era fixture-missing)."
echo

# 9. Production run example with tcmalloc
echo "--- Run main.py with tcmalloc + 4-worker (P0 #2 verified config) ---"
echo "  LD_PRELOAD=/usr/lib64/libtcmalloc.so.4 \\"
echo "  EXACT_CP_SAT_WORKERS=4 \\"
echo "  source .venv/bin/activate && python main.py --campaign-hours 0.083 \\"
echo "      --mode certified_exact --parallel-processes 4 --resume-campaign"
echo "(Compare RSS / wall-time with the Windows baseline run for Linux gain validation.)"
echo

echo "=== Setup checklist done ==="
if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "Re-run with --apply to actually install / configure."
fi
