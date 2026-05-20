"""Update the /loop heartbeat file — called by Claude at each loop iteration."""
from __future__ import annotations

import json
import time
from pathlib import Path

HEARTBEAT_PATH = Path(__file__).resolve().parents[1] / ".artifacts" / "loop_heartbeat.json"


def update_heartbeat(stage: str = "", note: str = "") -> None:
    HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stage": stage,
        "note": note,
    }
    tmp = HEARTBEAT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(HEARTBEAT_PATH)


if __name__ == "__main__":
    import sys
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    note = sys.argv[2] if len(sys.argv) > 2 else ""
    update_heartbeat(stage, note)
    print(f"Heartbeat updated: {HEARTBEAT_PATH}")
