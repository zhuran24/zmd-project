#!/usr/bin/env bash
#
# Phase 3C CachyOS setup — Endfield IndustrialPlanner solver
#
# Replaces fedora_setup.sh (Fedora unbootable on user's ASUS Z790
# hardware due to GRUB 2.06 memory-fragmentation issue, 2026-05-08).
#
# Default: dry-run, prints what would be done. Pass --apply to actually
# execute. Run from project root inside a fresh CachyOS install.
#
# Covers R2 audit a8a152668dd067210 recommendations:
# - THP (transparent huge pages, madvise mode)
# - jemalloc / tcmalloc allocator availability (P1 #24 cache-aware pack)
# - cgroups v2 verification
# - cachyos-bore kernel sanity (default on CachyOS, BORE/EEVDF scheduler)
#
# Tested target: CachyOS rolling, Linux ≥ 6.13.

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

echo "=== Phase 3C CachyOS setup ==="
if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "(dry-run mode — pass --apply to actually execute)"
fi
echo

# 1. Verify CachyOS
echo "--- OS identity ---"
if [[ -f /etc/os-release ]]; then
    grep -E "^(NAME|VERSION|ID|ID_LIKE)=" /etc/os-release
    if ! grep -qi "cachyos" /etc/os-release; then
        echo "WARNING: not CachyOS — script targets CachyOS, continuing anyway"
    fi
else
    echo "WARNING: /etc/os-release missing"
fi
echo

# 2. Kernel verify (CachyOS-bore expected)
echo "--- Kernel ---"
echo "running: $(uname -r)"
echo "(expect linux-cachyos or linux-cachyos-bore for BORE/EEVDF scheduler)"
if uname -r | grep -qE "cachyos|bore"; then
    echo "OK: cachyos-flavored kernel detected"
else
    echo "WARN: stock kernel detected. To switch to BORE:"
    echo "  sudo pacman -S linux-cachyos linux-cachyos-headers"
    echo "  sudo reboot  (select cachyos kernel in systemd-boot menu)"
fi
echo

# 3. System update
echo "--- System update ---"
run "sudo pacman -Syu --noconfirm"
echo

# 4. Python 3.13 (CachyOS rolling has it default)
echo "--- Python 3.13 ---"
if command -v python3 >/dev/null 2>&1; then
    python3 --version
    if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,13) else 1)"; then
        echo "WARN: python3 < 3.13. CachyOS rolling should have 3.13+; check pacman:"
        echo "  pacman -S python"
    fi
else
    run "sudo pacman -S --noconfirm python python-pip"
fi
echo

# 5. venv + project deps
echo "--- venv + requirements.txt ---"
if [[ ! -d .venv ]]; then
    run "python3 -m venv .venv"
fi
run "source .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt"
echo

# 6. Performance allocators (R2 a8a152668dd067210)
echo "--- Performance allocators ---"
run "sudo pacman -S --noconfirm jemalloc gperftools mimalloc"
echo "After install, paths to LD_PRELOAD:"
echo "  jemalloc: /usr/lib/libjemalloc.so.2"
echo "  tcmalloc: /usr/lib/libtcmalloc.so.4"
echo "  mimalloc: /usr/lib/libmimalloc.so.2"
echo

# 7. THP setting check (verified default in CachyOS-Settings repo)
echo "--- THP ---"
if [[ -f /sys/kernel/mm/transparent_hugepage/enabled ]]; then
    echo "  enabled: $(cat /sys/kernel/mm/transparent_hugepage/enabled)"
fi
if [[ -f /sys/kernel/mm/transparent_hugepage/defrag ]]; then
    echo "  defrag:  $(cat /sys/kernel/mm/transparent_hugepage/defrag)"
fi
echo "(CachyOS-Settings repo verified: defaults to defer+madvise on defrag,"
echo " specifically tuned for tcmalloc. khugepaged/max_ptes_none tuned for"
echo " kernel 6.12+. R2 audit's 'madvise' recommendation is already met or"
echo " exceeded by CachyOS defaults — no manual change needed.)"
echo

# 8. cgroups v2
echo "--- cgroups v2 ---"
if mount | grep -q cgroup2; then
    echo "cgroups v2 mounted (CachyOS systemd default)"
else
    echo "WARN: cgroups v2 not mounted — long-run job memory limits may be unreliable"
fi
echo

# 9. zram (CachyOS enables by default via zram-generator, verified)
echo "--- zram (verified default: zstd/lz4 + swap-priority=100) ---"
if swapon --show=NAME --noheadings 2>/dev/null | grep -q zram; then
    echo "OK: zram swap active"
    swapon --show=NAME,SIZE,USED,PRIO 2>/dev/null | grep zram || true
else
    echo "WARN: no zram swap detected. Should be auto-enabled via zram-generator."
    echo "      Check: systemctl status systemd-zram-setup@zram0.service"
fi
echo

# 9b. I/O scheduler (verified per-disk-type defaults from CachyOS-Settings)
echo "--- I/O scheduler (verified default: HDD=bfq / SATA SSD=mq-deadline / NVMe=none) ---"
for dev in /sys/block/sd* /sys/block/nvme*n*; do
    if [[ -f "$dev/queue/scheduler" ]]; then
        echo "  $(basename $dev): $(cat $dev/queue/scheduler)"
    fi
done 2>/dev/null
echo

# 10. Pin packages for 168h campaign stability
echo "--- Recommended /etc/pacman.conf hardening for campaign window ---"
echo "Add this line to /etc/pacman.conf [options] section to freeze critical packages:"
echo "  IgnorePkg = linux-cachyos linux-cachyos-headers glibc python python-ortools ortools"
echo "Then DO NOT run 'pacman -Syu' during the 168h campaign."
echo

# 11. ortools sanity
echo "--- ortools sanity ---"
run "source .venv/bin/activate && python -c 'from ortools.sat.python import cp_model; s=cp_model.CpSolver(); print(\"ortools OK, default num_search_workers:\", s.parameters.num_search_workers)'"
echo

# 12. Project pytest baseline
echo "--- Project test baseline (recommended next step) ---"
echo "  source .venv/bin/activate"
echo "  python -m pytest src/tests/ -q"
echo "Expected on a clean clone: 2033 passed, 60 skipped (Codex-era fixture-missing)."
echo

# 13. Production run example with jemalloc + 4-worker
echo "--- Run main.py with jemalloc + 4-worker (P0 #2 verified config) ---"
echo "  LD_PRELOAD=/usr/lib/libjemalloc.so.2 \\"
echo "  EXACT_CP_SAT_WORKERS=4 \\"
echo "  source .venv/bin/activate && python main.py --campaign-hours 0.083 \\"
echo "      --mode certified_exact --parallel-processes 4 --resume-campaign"
echo "(Compare RSS / wall-time with the Windows baseline run for Linux gain validation.)"
echo

echo "=== Setup checklist done ==="
if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "Re-run with --apply to actually install / configure."
fi
