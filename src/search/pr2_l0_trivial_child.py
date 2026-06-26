"""PR2-a trivial child verifier body.

This is only a round-trip placeholder for the controlled loader.  PR2-b owns
the real replay, gate, and B2-B4 verification body.
"""

SNAPSHOT_MARKER = "pr2_l0_verified_snapshot_child_v1"


def verify(request: dict[str, object]) -> dict[str, object]:
    payload = request.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a mapping")
    nonce = str(request.get("nonce", ""))
    action = str(payload.get("action", "ack"))

    if action == "wrong_nonce":
        return {"verdict": "SEALED", "nonce": "tampered", "reason": "wrong_nonce"}
    if action == "sleep":
        import time

        time.sleep(float(payload.get("seconds", 1.0)))
        return {"verdict": "SEALED", "nonce": nonce, "reason": "slept"}
    if action == "probe_import":
        module = payload.get("module")
        if not isinstance(module, str) or not module:
            raise ValueError("probe module must be a non-empty string")
        __import__(module)
        return {"verdict": "SEALED", "nonce": nonce, "reason": "probe_imported"}
    if action == "reject":
        return {"verdict": "REJECTED", "nonce": nonce, "reason": "trivial_rejected"}
    if SNAPSHOT_MARKER != "pr2_l0_verified_snapshot_child_v1":
        return {"verdict": "REJECTED", "nonce": nonce, "reason": "shadow_marker"}
    return {"verdict": "SEALED", "nonce": nonce, "reason": "trivial_ack"}
