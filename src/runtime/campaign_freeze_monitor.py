"""Phase 3C P2 #19 — 168h campaign 期间 pacman freeze 监控

提供:
- `is_pacman_freeze_enabled()` 检查 /etc/pacman.conf 里有无 Phase 3C
  freeze marker (campaign-stability lock)
- `start_freeze_monitor(...)` 起一个 daemon 线程，campaign 期间周期
  re-check freeze marker；丢了就 append warning 到 telemetry log + stderr
  (warning-only 不 abort — 已经跑 N 小时不能浪费)

Project Linux only — `/etc/pacman.conf` 在非 Arch/CachyOS 不存在，监控
会立刻 detect 并 warning 一次后停止 (相当于 effective skip)。
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Optional

PACMAN_CONF = Path("/etc/pacman.conf")
FREEZE_MARKER = "# === Phase 3C campaign freeze BEGIN ==="

# 默认采样间隔 60 min — 168h 期间检查 168 次，单次 read /etc/pacman.conf
# 几 KB IO 几乎无开销。短于这个值在 168h 期间产 noise，长于则 lock-loss
# 检测延迟过大。
DEFAULT_MONITOR_INTERVAL_SECONDS = 60 * 60


def is_pacman_freeze_enabled() -> bool:
    """Pure-function check: True iff /etc/pacman.conf contains the freeze marker.

    Returns False on missing file or read error (defensive — caller decides
    severity).
    """
    if not PACMAN_CONF.exists():
        return False
    try:
        return FREEZE_MARKER in PACMAN_CONF.read_text(encoding="utf-8")
    except OSError:
        return False


def _monitor_loop(
    *,
    log_path: Optional[Path],
    interval_seconds: int,
    stop_event: threading.Event,
) -> None:
    """Inner loop run on the daemon thread."""
    iteration = 0
    last_state = is_pacman_freeze_enabled()
    if not last_state:
        # Should not happen if startup gate passed, but defensive: if monitor
        # is started in a state where freeze was never on, log once and exit.
        _emit_warning(
            log_path,
            "[campaign_freeze_monitor] startup state: freeze marker NOT present "
            "— monitor will not run further (caller should have caught this in "
            "the readiness gate; check why monitor was started anyway).",
        )
        return

    while not stop_event.is_set():
        # Wait first so the very first check happens after one interval
        # (don't double-check what the readiness gate already verified).
        if stop_event.wait(timeout=interval_seconds):
            return  # stop signaled
        iteration += 1
        current = is_pacman_freeze_enabled()
        if current != last_state and not current:
            # Freeze was enabled at startup, now it's gone — alert.
            _emit_warning(
                log_path,
                f"[campaign_freeze_monitor] iter={iteration}: freeze marker "
                f"DISAPPEARED from /etc/pacman.conf during campaign! "
                f"Possible mid-run pacman -Syu or manual edit. Restore with "
                f"`bash scripts/pacman_campaign_freeze.sh --enable` ASAP. "
                f"This monitor will keep running and re-alert on each cycle "
                f"until restored.",
            )
        elif current != last_state and current:
            _emit_warning(
                log_path,
                f"[campaign_freeze_monitor] iter={iteration}: freeze marker "
                f"restored.",
            )
        last_state = current


def _emit_warning(log_path: Optional[Path], message: str) -> None:
    """Write the warning to stderr and (if configured) append to the log file."""
    sys.stderr.write(message + "\n")
    sys.stderr.flush()
    if log_path is not None:
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(message + "\n")
        except OSError as exc:
            sys.stderr.write(
                f"[campaign_freeze_monitor] WARN: failed to append log "
                f"{log_path}: {exc}\n"
            )


def start_freeze_monitor(
    *,
    log_path: Optional[Path] = None,
    interval_seconds: int = DEFAULT_MONITOR_INTERVAL_SECONDS,
) -> threading.Event:
    """Start a daemon thread monitoring the pacman freeze marker.

    Daemon = the thread won't block process shutdown; when main.py exits
    (campaign finished or interrupted), the thread auto-dies.

    Returns the stop_event so the caller can signal early shutdown if
    needed (rare — typically you just let the process exit).
    """
    stop_event = threading.Event()
    thread = threading.Thread(
        target=_monitor_loop,
        kwargs={
            "log_path": log_path,
            "interval_seconds": int(interval_seconds),
            "stop_event": stop_event,
        },
        name="campaign_freeze_monitor",
        daemon=True,
    )
    thread.start()
    return stop_event
