"""band22 registration driver — feed an external witness layout into the
official master-feasibility check plus the binding + routing certification
gates (P1.3 research, 2026-08-05).

WHAT THIS IS
------------
A *fixed-layout* variant of ``docs/research/p1_3_m5_convergence_20260708/
m5_cell_runner.py``. The M5 runner builds the master and lets the LBBD loop
search; this driver does not search, because the layout is already given (the
band22 witness, registered onto official pool poses by the alignment probe).
It runs three stages, in this order, each fail-closed:

    1. structural validation   this file, ``validate_layout_structure``
       (instance-set completeness, id/entry agreement, pose identity,
       geometry: in-grid, pairwise-disjoint bodies, ghost rectangle free of
       facility bodies)
    2. master feasibility      src/models/master_model.py MasterPlacementModel
       — every mandatory/optional slot literal is *fixed* to the witness pose
       and the ghost anchor is fixed to the witness anchor, then the official
       master is solved. This is what covers the master hard constraints the
       two gates never look at (power coverage, optional caps, ghost-body
       exclusion, placement rules). Anything other than FEASIBLE/OPTIMAL stops
       the run: the gates are never fed an unvalidated layout.
    3. binding + routing gates src/models/binding_subproblem.py PortBindingModel
                               src/models/routing_subproblem.py RoutingSubproblem
       driven through the *official* orchestration method
       ``LBBDController._run_exact_binding_and_routing``.

Calling the official orchestrator verbatim is deliberate: re-deriving the
binding→port_specs→routing_grid→precheck→routing wiring by hand is exactly the
kind of "harness-authored input" that has burned this project before.

VERDICT DISCIPLINE (the controller is the authority)
----------------------------------------------------
``_run_exact_binding_and_routing`` has many paths where the inner
``binding_status``/``routing_status`` look conclusive but the official return
value is still ``UNKNOWN`` (power-pole normalization failure after both gates
pass; whole-layout nogood refused because the independent re-verifier did not
confirm; …). Therefore:

* the returned controller status is the primary authority and an official
  ``UNKNOWN`` is always reported as UNKNOWN, whatever the inner statuses say;
* a positive verdict requires ``CERTIFIED`` + a non-empty returned solution +
  no harness exception + no subproblem status-contract violation;
* a negative verdict requires the official ``master_cut_added_continue`` return
  *and* ``independent_infeasibility_reverifier.confirmed is true``.

LEGALITY (research-only, fail-closed by construction)
-----------------------------------------------------
* No campaign object is constructed, ``ExactCampaign`` is never called, no
  proposal marker is written, ``supervisor_seal`` is not on this code path, and
  the publisher is never invoked — so no CANDIDATE_PROPOSED and no durable
  CERTIFIED can be produced. ``_run_exact_binding_and_routing`` may *return* the
  in-memory string "CERTIFIED"; it is recorded verbatim under
  ``controller_return_status`` and is NOT a certification (see
  ``research_only_disclaimer``).
* Every runtime byte this driver writes lands inside a fresh unique run
  directory under ``.artifacts/band22_registration_20260805`` — enforced, not
  documented: ``--out-dir`` must resolve inside that root, ``--tag`` must be a
  strict leaf name, nothing pre-existing is ever unlinked, and ``TMPDIR`` is
  re-pointed into the run directory so no library temp file can escape.
* ``CutManager`` gets a scratch dir inside the run directory, never
  ``data/checkpoints``.
* ``side_effect_audit`` snapshots ``data/checkpoints`` / ``data/solutions`` /
  ``data/blueprints`` before anything is created and again after every artifact
  has landed. A dirty audit overrides the verdict and the exit code.
* Env: any inherited ``EXACT_*`` variable is a hard error before anything is
  set. The driver owns exactly two knobs (``EXACT_CP_SAT_WORKERS``,
  ``EXACT_B1_BINDING_ALT_CAP``) and sets them itself.

BUDGET / CENSORING
------------------
``--binding-seconds`` / ``--routing-seconds`` are per-solve CP-SAT limits, not a
wall-clock cap on the run. A budget hit is bookkept as UNKNOWN censored@N, never
as a failure. The in-process ``--max-gate-wall-seconds`` SIGALRM guard is
best-effort only (it cannot interrupt a native CP-SAT call); the authoritative
envelope is the cgroup wrapper ``run_guarded.sh``.

USAGE
-----
    env -u PYTHONPATH -u PYTHONHOME .venv-uvbolt-backup/bin/python \\
      docs/research/band22_registration_20260805/registration_driver.py \\
      --tag smoke --binding-seconds 20 --routing-seconds 10

Production-shaped runs go through ``run_guarded.sh`` (see README).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_SOLUTION = (
    PROJECT_ROOT
    / ".artifacts"
    / "w0_fixrerun_20260804"
    / "band22_alignment"
    / "registration_placement_solution.json"
)
# Hard containment root. --out-dir may be this directory or a subdirectory of
# it and nothing else; see _resolve_run_dir.
OUT_ROOT = PROJECT_ROOT / ".artifacts" / "band22_registration_20260805"
DEFAULT_OUT_DIR = OUT_ROOT

# The band22 hole reported by the alignment probe
# (.artifacts/w0_fixrerun_20260804/band22_alignment/max_empty_rect_for_this_placement.json).
DEFAULT_GHOST_W = 6
DEFAULT_GHOST_H = 7
DEFAULT_GHOST_ANCHOR_X = 1
DEFAULT_GHOST_ANCHOR_Y = 51

GRID_W = 70
GRID_H = 70

TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

# The only two EXACT_* knobs this driver owns. Everything else inherited from
# the environment is a hard error (see _enforce_env_hygiene).
OWNED_ENV_KNOBS = ("EXACT_CP_SAT_WORKERS", "EXACT_B1_BINDING_ALT_CAP")

RESEARCH_ONLY_DISCLAIMER = (
    "research-only gate ingestion. No campaign, no proposal marker, no "
    "supervisor_seal, no publisher, no data/checkpoints write. "
    "controller_return_status is an in-memory return value of "
    "LBBDController._run_exact_binding_and_routing and is NOT a certification; "
    "only ExactCampaign.supervisor_seal() can mint a durable CERTIFIED and it "
    "is not on this code path."
)
CONTROLLER_SEARCH_BOUNDARY = "Witness binding/routes are provenance only; official controller independently searches binding/routing."

EXIT_OK = 0
EXIT_RUN_FAILURE = 1
EXIT_USAGE = 2


# --------------------------------------------------------------------------
# stage logging
# --------------------------------------------------------------------------
class StageLog:
    def __init__(self) -> None:
        self.started = time.perf_counter()
        self.records: List[Dict[str, Any]] = []

    def emit(self, stage: str, event: str, **extra: Any) -> None:
        elapsed = round(time.perf_counter() - self.started, 3)
        record = {
            "t": elapsed,
            "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "stage": str(stage),
            "event": str(event),
        }
        if extra:
            record.update(extra)
        self.records.append(record)
        detail = " ".join(f"{k}={v}" for k, v in extra.items())
        print(f"[+{elapsed:9.3f}s] {stage}:{event} {detail}".rstrip(), flush=True)

    def heartbeat_callback(self, payload: Mapping[str, Any]) -> None:
        stage = str(payload.get("stage", "?"))
        event = str(payload.get("event", "?"))
        extra = {
            k: v
            for k, v in payload.items()
            if k not in {"stage", "event"}
            and isinstance(v, (str, int, float, bool, type(None)))
        }
        self.emit(f"gate.{stage}", event, **extra)


# --------------------------------------------------------------------------
# memory sampler
# --------------------------------------------------------------------------
_MEM_KEYS = ("VmRSS", "VmHWM", "VmSwap", "VmPeak")


def _read_proc_status() -> Dict[str, int]:
    out: Dict[str, int] = {}
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as handle:
            for line in handle:
                key, _, rest = line.partition(":")
                if key in _MEM_KEYS:
                    parts = rest.split()
                    if parts and parts[0].isdigit():
                        out[key] = int(parts[0])  # kB
    except OSError:
        return {}
    return out


class MemorySampler:
    """Appends /proc/self/status memory lines to a JSONL sidecar.

    Observation only. It is not a limiter: the hard envelope is the cgroup in
    run_guarded.sh (the M5/C1 lesson — a soft cap never stopped an OOM).
    """

    def __init__(self, sidecar: Path, interval_seconds: float, log: StageLog) -> None:
        self.sidecar = sidecar
        self.interval = max(0.05, min(1.0, float(interval_seconds)))
        self.log = log
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.peak_kb: Dict[str, int] = {}

    def _sample_once(self, handle: Any, tag: str) -> None:
        snapshot = _read_proc_status()
        if not snapshot:
            return
        for key, value in snapshot.items():
            if value > self.peak_kb.get(key, -1):
                self.peak_kb[key] = value
        handle.write(
            json.dumps(
                {
                    "t": round(time.perf_counter() - self.log.started, 3),
                    "tag": tag,
                    **{k: snapshot[k] for k in sorted(snapshot)},
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        handle.flush()

    def _run(self) -> None:
        with open(self.sidecar, "a", encoding="utf-8") as handle:
            self._sample_once(handle, "start")
            while not self._stop.wait(self.interval):
                self._sample_once(handle, "sample")
            self._sample_once(handle, "final")

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="mem-sampler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def summary(self) -> Dict[str, Any]:
        return {
            "sidecar": str(self.sidecar),
            "interval_seconds": self.interval,
            "observation_only": True,
            "peak_kb": dict(self.peak_kb),
            "vm_hwm_mb": round(self.peak_kb.get("VmHWM", 0) / 1024.0, 1),
            "vm_swap_peak_mb": round(self.peak_kb.get("VmSwap", 0) / 1024.0, 1),
        }


# --------------------------------------------------------------------------
# side-effect audit
# --------------------------------------------------------------------------
_AUDITED_PATHS = (
    Path("data/checkpoints"),
    Path("data/solutions"),
    Path("data/blueprints"),
)


def _audit_snapshot() -> Dict[str, Any]:
    snapshot: Dict[str, Any] = {}
    for rel in _AUDITED_PATHS:
        target = PROJECT_ROOT / rel
        if not target.exists():
            snapshot[str(rel)] = {"exists": False}
            continue
        entries = {}
        if target.is_dir():
            for child in sorted(target.rglob("*")):
                try:
                    entries[str(child.relative_to(target))] = child.stat().st_mtime_ns
                except OSError:
                    entries[str(child.relative_to(target))] = None
        snapshot[str(rel)] = {
            "exists": True,
            "mtime_ns": target.stat().st_mtime_ns,
            "entries": entries,
        }
    return snapshot


def _audit_diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> Dict[str, Any]:
    changed: Dict[str, Any] = {}
    for key in sorted(set(before) | set(after)):
        if before.get(key) != after.get(key):
            b = before.get(key, {})
            a = after.get(key, {})
            b_entries = set((b or {}).get("entries", {}) or {})
            a_entries = set((a or {}).get("entries", {}) or {})
            changed[key] = {
                "added": sorted(a_entries - b_entries),
                "removed": sorted(b_entries - a_entries),
            }
    return {"clean": not changed, "changed": changed}


# --------------------------------------------------------------------------
# atomic write
# --------------------------------------------------------------------------
def atomic_write_text(path: Path, text: str) -> str:
    """Write ``text`` atomically (tmp + fsync + rename + dir fsync).

    Returns the sha256 of the bytes that landed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode("utf-8")
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, 0o644)  # mkstemp defaults to 0600; artifacts are readable
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    dir_fd = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
    return hashlib.sha256(data).hexdigest()


def atomic_write_json(path: Path, payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    return atomic_write_text(path, text)


def _sha256_file(path: Path) -> Optional[str]:
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


# --------------------------------------------------------------------------
# env hygiene: this driver owns two knobs and inherits none
# --------------------------------------------------------------------------
def _enforce_env_hygiene() -> Dict[str, Any]:
    """Fail closed on ANY inherited EXACT_* variable, before touching os.environ.

    The certified operational allowlist is an allowlist for the *production*
    entry points, not a research-output whitelist: several allowlisted knobs
    (e.g. EXACT_BINDING_DUMP_STATE, EXACT_SUBPROBLEM_REPEAT_LOG_DIR) make the
    official code write telemetry outside this driver's audited output tree. So
    the research driver keeps its own, much narrower, contract: it owns
    OWNED_ENV_KNOBS and refuses to run with anything else inherited.
    """
    inherited = sorted(name for name in os.environ if name.startswith("EXACT_"))
    if inherited:
        print(
            "refusing to run with inherited EXACT_* environment variables "
            f"({', '.join(inherited)}). This driver owns "
            f"{', '.join(OWNED_ENV_KNOBS)} and sets them itself; unset the rest "
            "(env -u ...) and re-run.",
            file=sys.stderr,
            flush=True,
        )
        return {"ok": False, "inherited": inherited}
    return {"ok": True, "inherited": []}


def _classify_owned_env() -> Dict[str, Any]:
    """Record how the official certified allowlists classify the owned knobs."""
    classification: Dict[str, Any] = {}
    try:
        from src.search import benders_loop as _bl

        operational = set(getattr(_bl, "_CERTIFIED_OPERATIONAL_ENV_ALLOWLIST", ()) or ())
        unsafe = set(
            getattr(_bl, "_CERTIFIED_MASTER_DOMAIN_UNSAFE_ENV_OVERRIDES", ()) or ()
        )
        known = set(getattr(_bl, "_CERTIFIED_KNOWN_ENV_NAMES", ()) or ())
        for name in OWNED_ENV_KNOBS:
            classification[name] = {
                "operational_allowlisted": name in operational,
                "master_domain_unsafe": name in unsafe,
                "known": name in known,
                "value": os.environ.get(name),
            }
        classification["_set_sizes"] = {
            "operational_allowlist": len(operational),
            "master_domain_unsafe_overrides": len(unsafe),
            "known_env_names": len(known),
        }
    except Exception as exc:  # noqa: BLE001 — provenance only
        classification["_error"] = f"{type(exc).__name__}: {exc}"
    return classification


# --------------------------------------------------------------------------
# output containment
# --------------------------------------------------------------------------
def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _resolve_run_dir(out_dir: Path, tag: str) -> Tuple[Optional[Path], Optional[str]]:
    """Return a fresh, unique, contained run directory (or an error message).

    Containment is enforced rather than documented: an arbitrary --out-dir or a
    tag like ``../../data/checkpoints/x`` must not be able to place a write (or,
    worse, a delete) inside the proof-output tree.
    """
    if not TAG_RE.match(tag):
        return None, (
            f"--tag {tag!r} is not a strict leaf name "
            "(allowed: [A-Za-z0-9][A-Za-z0-9._-]{0,63})"
        )
    if os.sep in tag or (os.altsep and os.altsep in tag) or ".." in tag:
        return None, f"--tag {tag!r} must not contain path separators or '..'"

    root = OUT_ROOT.resolve() if OUT_ROOT.exists() else OUT_ROOT
    try:
        candidate = Path(os.path.realpath(str(out_dir)))
    except OSError as exc:
        return None, f"--out-dir cannot be resolved: {exc}"
    if candidate != root and not _is_within(candidate, root):
        return None, (
            f"--out-dir must be {root} or a subdirectory of it; got {candidate}"
        )
    for audited in _AUDITED_PATHS:
        if _is_within(candidate, (PROJECT_ROOT / audited).resolve()):
            return None, f"--out-dir resolves inside the audited path {audited}"

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = candidate / f"{tag}-{stamp}-{uuid.uuid4().hex[:8]}"
    try:
        run_dir.mkdir(parents=True, exist_ok=False)  # never overwrite, never unlink
    except FileExistsError:
        return None, f"run directory already exists: {run_dir}"
    except OSError as exc:
        return None, f"cannot create run directory {run_dir}: {exc}"
    resolved = Path(os.path.realpath(str(run_dir)))
    if resolved != run_dir:
        return None, f"run directory {run_dir} resolves elsewhere ({resolved})"
    return run_dir, None


# --------------------------------------------------------------------------
# witness loading + structural validation
# --------------------------------------------------------------------------
def verify_witness_snapshot_identity(provenance_sha: Any, adapter_sha: Any) -> None:
    if not isinstance(provenance_sha, str) or adapter_sha != provenance_sha:
        raise ValueError("witness bytes drifted between provenance and the immutable adapter snapshot")


def load_witness_solution(path: Path) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    from src.io.strict_json import load_strict_json

    payload = load_strict_json(path)
    if not isinstance(payload, Mapping):
        raise ValueError(f"{path} is not a JSON object")
    if "witness_schema_version" in payload:
        if payload.get("witness_schema_version") != "band22-witness/2":
            raise ValueError(f"{path}: unsupported witness_schema_version {payload.get('witness_schema_version')!r}")
        from docs.research.band22_registration_20260805.band22_v2_adapter import load_band22_v2_witness
        return load_band22_v2_witness(path, project_root=PROJECT_ROOT)
    raw_solution = payload.get("solution")
    if not isinstance(raw_solution, Mapping):
        raise ValueError(f"{path}: missing 'solution' object")
    solution: Dict[str, Dict[str, Any]] = {}
    for instance_id, entry in raw_solution.items():
        if not isinstance(entry, Mapping):
            raise ValueError(f"{path}: solution.{instance_id} is not an object")
        if str(instance_id) == "ghost_pick":
            raise ValueError(
                f"{path}: the witness must not carry ghost_pick; the driver "
                "computes it from the official index formula"
            )
        solution[str(instance_id)] = dict(entry)
    meta = {
        "path": str(path),
        "sha256": _sha256_file(path),
        "witness_schema_version": None,
        "schema_dispatch": "legacy_solution",
        "schema_note": payload.get("schema_note"),
        "pose_idx_basis": payload.get("pose_idx_basis"),
        "facility_count": payload.get("facility_count"),
        "body_cells": payload.get("body_cells"),
        "loaded_instance_count": len(solution),
    }
    return solution, meta


def validate_layout_structure(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    master: Any,
    ghost_w: int,
    ghost_h: int,
    ghost_anchor_x: int,
    ghost_anchor_y: int,
    active_terminal_cells: Optional[Sequence[Any]] = None,
    route_component_cells: Optional[Sequence[Any]] = None,
) -> Dict[str, Any]:
    """Source-owned fixed-layout structural validator (fail-closed).

    Covers what the binding/routing gates do NOT look at and what a pose-index
    re-check alone cannot see:

    * every mandatory instance of ``master.source_instances`` is present exactly
      once, and no unknown/extra instance id is present;
    * outer key == entry.instance_id, facility_type/operation_type agree with
      the instance (mandatory) or with POSE_LEVEL_OPTIONAL_OPERATIONS (optional);
    * pose_idx dereferences to a pool pose whose pose_id and anchor equal the
      witness's (a silent pool-order shift would otherwise feed the gates a
      layout nobody vetted);
    * bodies are inside the grid and pairwise disjoint;
    * the ghost rectangle contains no facility body, active terminal, or route
      component.  Merely possible pose ports are telemetry, not blockers.

    Master hard constraints beyond geometry (power coverage, optional caps,
    placement rules) are covered by ``validate_master_feasibility``.
    """
    from src.models.master_model import POSE_LEVEL_OPTIONAL_OPERATIONS

    problems: List[Dict[str, Any]] = []

    def fail(reason: str, **extra: Any) -> None:
        problems.append({"reason": reason, **extra})

    mandatory_expected: Dict[str, Dict[str, Any]] = {}
    for inst in getattr(master, "source_instances", []) or []:
        if bool(inst.get("is_mandatory")):
            mandatory_expected[str(inst.get("instance_id"))] = dict(inst)

    facility_pools = master.facility_pools
    seen_mandatory: Set[str] = set()
    optional_ids: List[str] = []
    occupied_owner: Dict[Tuple[int, int], str] = {}

    for instance_id, entry in solution.items():
        iid = str(instance_id)
        if str(entry.get("instance_id", iid)) != iid:
            fail("instance_id_key_mismatch", key=iid, entry=str(entry.get("instance_id")))
        facility_type = str(entry.get("facility_type", ""))
        pose_idx = entry.get("pose_idx")

        if iid in mandatory_expected:
            if iid in seen_mandatory:
                fail("duplicate_mandatory_instance", instance_id=iid)
            seen_mandatory.add(iid)
            expected = mandatory_expected[iid]
            if str(expected.get("facility_type")) != facility_type:
                fail(
                    "facility_type_mismatch",
                    instance_id=iid,
                    witness=facility_type,
                    expected=str(expected.get("facility_type")),
                )
            exp_op = expected.get("operation_type")
            got_op = entry.get("operation_type")
            if exp_op is not None and got_op is not None and str(exp_op) != str(got_op):
                fail(
                    "operation_type_mismatch",
                    instance_id=iid,
                    witness=str(got_op),
                    expected=str(exp_op),
                )
        elif iid.startswith("pose_optional::"):
            optional_ids.append(iid)
            parts = iid.split("::")
            if len(parts) != 3:
                fail("optional_id_shape", instance_id=iid)
                continue
            tpl = parts[1]
            if tpl not in POSE_LEVEL_OPTIONAL_OPERATIONS:
                fail("optional_template_not_pose_level", instance_id=iid, template=tpl)
                continue
            if tpl != facility_type:
                fail(
                    "optional_template_mismatch",
                    instance_id=iid,
                    witness=facility_type,
                    expected=tpl,
                )
            got_op = entry.get("operation_type")
            if got_op is not None and str(got_op) != POSE_LEVEL_OPTIONAL_OPERATIONS[tpl]:
                fail(
                    "optional_operation_mismatch",
                    instance_id=iid,
                    witness=str(got_op),
                    expected=POSE_LEVEL_OPTIONAL_OPERATIONS[tpl],
                )
        else:
            fail("unknown_instance_id", instance_id=iid)
            continue

        pool = facility_pools.get(facility_type)
        if isinstance(pose_idx, bool) or not isinstance(pose_idx, int):
            fail("pose_idx_not_int", instance_id=iid)
            continue
        if pool is None or pose_idx < 0 or pose_idx >= len(pool):
            fail(
                "pose_idx_out_of_range",
                instance_id=iid,
                facility_type=facility_type,
                pose_idx=pose_idx,
                pool_size=(len(pool) if pool is not None else None),
            )
            continue
        pose = pool[pose_idx]

        expected_pose_id = entry.get("pose_id")
        if expected_pose_id is not None and str(expected_pose_id) != str(
            pose.get("pose_id")
        ):
            fail(
                "pose_id_mismatch",
                instance_id=iid,
                witness=str(expected_pose_id),
                pool=str(pose.get("pose_id")),
            )
            continue
        if iid.startswith("pose_optional::") and iid.split("::")[-1] != str(
            pose.get("pose_id")
        ):
            fail(
                "optional_id_pose_id_mismatch",
                instance_id=iid,
                pool=str(pose.get("pose_id")),
            )
        expected_anchor = entry.get("anchor")
        actual_anchor = pose.get("anchor")
        if isinstance(expected_anchor, Mapping) and isinstance(actual_anchor, Mapping):
            if int(expected_anchor.get("x", -1)) != int(
                actual_anchor.get("x", -2)
            ) or int(expected_anchor.get("y", -1)) != int(actual_anchor.get("y", -2)):
                fail(
                    "anchor_mismatch",
                    instance_id=iid,
                    witness=dict(expected_anchor),
                    pool=dict(actual_anchor),
                )
                continue

        for cell in pose.get("occupied_cells", []) or []:
            cx, cy = int(cell[0]), int(cell[1])
            if not (0 <= cx < GRID_W and 0 <= cy < GRID_H):
                fail("body_cell_out_of_grid", instance_id=iid, cell=[cx, cy])
                continue
            owner = occupied_owner.get((cx, cy))
            if owner is not None:
                fail("body_overlap", cell=[cx, cy], a=owner, b=iid)
                continue
            occupied_owner[(cx, cy)] = iid

    missing = sorted(set(mandatory_expected) - seen_mandatory)
    for iid in missing[:20]:
        fail("missing_mandatory_instance", instance_id=iid)

    ghost_cells = {
        (x, y)
        for x in range(int(ghost_anchor_x), int(ghost_anchor_x) + int(ghost_w))
        for y in range(int(ghost_anchor_y), int(ghost_anchor_y) + int(ghost_h))
    }
    for cell in sorted(ghost_cells & set(occupied_owner)):
        fail("ghost_rect_contains_body", cell=list(cell), owner=occupied_owner[cell])

    def audited_cells(values: Optional[Sequence[Any]], kind: str) -> Set[Tuple[int, int]]:
        cells: Set[Tuple[int, int]] = set()
        for index, raw in enumerate(values or []):
            try:
                if len(raw) != 2:
                    raise ValueError
                cell = int(raw[0]), int(raw[1])
            except (KeyError, TypeError, ValueError):
                fail(f"malformed_{kind}", index=index)
                continue
            cells.add(cell)
        for cell in sorted(cells & ghost_cells):
            fail(f"ghost_rect_contains_{kind}", cell=list(cell))
        return cells

    active_cells = audited_cells(active_terminal_cells, "active_terminal")
    audited_cells(route_component_cells, "route_component")

    # PROJECT_LOCK.md:404: a physical port that binding may leave inactive does
    # not make its pose infeasible.  Keep all selected-pose candidate ports as
    # audit telemetry, but only the adapter-projected active terminals above are
    # required to stay outside the hole.
    candidate_ports_in_ghost: List[Tuple[int, int]] = []
    for instance_id, entry in solution.items():
        facility_type = str(entry.get("facility_type", ""))
        pose_idx = entry.get("pose_idx")
        pool = facility_pools.get(facility_type) or []
        if not isinstance(pose_idx, int) or pose_idx < 0 or pose_idx >= len(pool):
            continue
        pose = pool[pose_idx]
        for field in ("input_port_cells", "output_port_cells"):
            for port in pose.get(field, []) or []:
                try:
                    cell = (int(port["x"]), int(port["y"]))
                except (KeyError, TypeError, ValueError):
                    continue
                if cell in ghost_cells:
                    candidate_ports_in_ghost.append(cell)

    return {
        "ok": not problems,
        "mandatory_expected": len(mandatory_expected),
        "mandatory_present": len(seen_mandatory),
        "mandatory_missing": len(missing),
        "optional_entries": len(optional_ids),
        "body_cells": len(occupied_owner),
        "ghost_cells": len(ghost_cells),
        "candidate_physical_ports_inside_ghost": len(candidate_ports_in_ghost),
        "inactive_candidate_ports_inside_ghost": None if active_terminal_cells is None else sum(cell not in active_cells for cell in candidate_ports_in_ghost),
        "problem_count": len(problems),
        "problems": problems[:50],
    }


def build_ghost_pick(
    *,
    ghost_w: int,
    ghost_h: int,
    anchor_x: int,
    anchor_y: int,
) -> Dict[str, Any]:
    """ghost_pick pose_idx comes from the official index formula, never by hand."""
    from src.search.pr2_l0_fixed_witness_core import (
        _expected_unfiltered_ghost_anchor_index,
    )

    pose_idx = _expected_unfiltered_ghost_anchor_index(
        grid_w=GRID_W,
        grid_h=GRID_H,
        ghost_w=int(ghost_w),
        ghost_h=int(ghost_h),
        anchor_x=int(anchor_x),
        anchor_y=int(anchor_y),
    )
    if pose_idx is None:
        raise ValueError(
            "ghost rect/anchor is out of the unfiltered ghost anchor domain: "
            f"{ghost_w}x{ghost_h} @ ({anchor_x},{anchor_y})"
        )
    return {
        "instance_id": "ghost_pick",
        "facility_type": "ghost_rect",
        "pose_idx": int(pose_idx),
        "anchor": {"x": int(anchor_x), "y": int(anchor_y)},
    }


def resolve_live_ghost_domain_index(master: Any, *, anchor_x: int, anchor_y: int) -> int:
    """Resolve the live gate index; terminal fixed-witness consumers require the distinct unfiltered identity."""
    u_vars = getattr(master, "u_vars", {}) or {}
    ghost_domains = list(getattr(master, "_ghost_domains", []) or [])
    if not u_vars or not ghost_domains:
        raise ValueError("the built master has no live ghost anchor domain")
    matches: List[int] = []
    for idx in u_vars:
        if isinstance(idx, bool) or not isinstance(idx, int) or not 0 <= idx < len(ghost_domains):
            raise ValueError(f"invalid live ghost-domain index: {idx!r}")
        anchor = (ghost_domains[idx] or {}).get("anchor") or {}
        if (int(anchor.get("x", -1)), int(anchor.get("y", -1))) == (anchor_x, anchor_y):
            matches.append(idx)
    if len(matches) != 1:
        raise ValueError(
            f"ghost anchor ({anchor_x},{anchor_y}) matched {len(matches)} "
            "entries in the live ghost domain"
        )
    return matches[0]


# --------------------------------------------------------------------------
# master feasibility on the fixed layout
# --------------------------------------------------------------------------
def validate_master_feasibility(
    *,
    master: Any,
    solution: Mapping[str, Mapping[str, Any]],
    ghost_anchor_x: int,
    ghost_anchor_y: int,
    time_limit_seconds: float,
    log: StageLog,
) -> Dict[str, Any]:
    """Fix every master literal to the witness and solve the official master.

    The two gates read a layout; they never check that the layout satisfies the
    master's own hard constraints (power coverage, optional caps, placement
    rules, ghost-body exclusion). So before the gates run, the witness is pinned
    into the official master model — mandatory slots, pose-level optional slots
    (required + residual, with unused residual slots forced inactive) and the
    ghost anchor — and the master is solved.

    Slot ordering mirrors ``CoordinateExactMasterDelegate.apply_solution_hint``
    (poses sorted by ``MasterPlacementModel._pose_sort_key``, which is the order
    the slot symmetry-breaking ``order_key`` monotonicity expects).

    Returns a record whose ``confirmed`` is true only for OPTIMAL/FEASIBLE.
    """
    from ortools.sat.python import cp_model

    record: Dict[str, Any] = {
        "mode": "official_master_solve_with_fixed_literals",
        "confirmed": False,
        "status": None,
        "time_limit_seconds": float(time_limit_seconds),
    }

    delegate = getattr(master, "_coordinate_delegate", None)
    if delegate is None:
        record["status"] = "NO_COORDINATE_DELEGATE"
        record["reason"] = (
            "the exact coordinate master delegate is absent; the fixed-literal "
            "encoding is only defined for it"
        )
        return record

    tuple_by_idx = delegate._template_pose_tuple_by_idx

    # Pins are collected as (variable proto index, value, label) and applied to
    # a COPY of the official model proto as domain restrictions — see the solve
    # block below. Nothing is added to the live master model.
    pins: List[Tuple[int, int, str]] = []

    def pin(var: Any, value: int, label: str) -> None:
        pins.append((int(var.Index()), int(value), label))

    # --- group the witness by mandatory group / optional template ------------
    group_id_by_instance = master._group_id_by_instance
    grouped: Dict[str, List[int]] = {}
    optional_by_tpl: Dict[str, List[int]] = {}
    for instance_id, entry in solution.items():
        iid = str(instance_id)
        if iid == "ghost_pick":
            continue
        pose_idx = int(entry["pose_idx"])
        if iid in group_id_by_instance:
            grouped.setdefault(str(group_id_by_instance[iid]), []).append(pose_idx)
            continue
        tpl = master._infer_optional_template_from_solution_id(iid)
        if tpl is None:
            record["status"] = "UNMAPPABLE_INSTANCE"
            record["reason"] = f"cannot map witness entry {iid} to a master slot family"
            return record
        optional_by_tpl.setdefault(str(tpl), []).append(pose_idx)

    fixed_literals = 0

    # --- mandatory slots ------------------------------------------------------
    for group in master._mandatory_groups:
        group_id = str(group["group_id"])
        tpl = str(group["facility_type"])
        slots = delegate.mandatory_slots.get(group_id, [])
        pose_indices = sorted(
            grouped.get(group_id, []),
            key=lambda pose_idx: master._pose_sort_key(tpl, int(pose_idx)),
        )
        if len(pose_indices) != len(slots):
            record["status"] = "SLOT_COUNT_MISMATCH"
            record["reason"] = (
                f"group {group_id} ({tpl}) has {len(slots)} master slots but the "
                f"witness supplies {len(pose_indices)} placements"
            )
            return record
        for slot, pose_idx in zip(slots, pose_indices):
            tup = tuple_by_idx.get(tpl, {}).get(int(pose_idx))
            if tup is None:
                record["status"] = "POSE_NOT_IN_MASTER_DOMAIN"
                record["reason"] = (
                    f"pose_idx {pose_idx} of {tpl} is not in the master's pose "
                    "domain for this group"
                )
                return record
            x_val, y_val, mode_id = tup
            pin(slot.x, x_val, f"{slot.key}.x")
            pin(slot.y, y_val, f"{slot.key}.y")
            pin(slot.mode, mode_id, f"{slot.key}.mode")
            fixed_literals += 3

    # --- C1 power-pole representation ----------------------------------------
    # Under the C1 representation the delegate drops the power_pole slot specs
    # entirely and models one boolean per pool pose instead
    # (_create_c1_power_pole_pose_vars). Pin those booleans directly.
    c1_pole_bools = list(getattr(delegate, "_c1_pole_bools", []) or [])
    if c1_pole_bools:
        witness_poles = {int(idx) for idx in optional_by_tpl.pop("power_pole", [])}
        pinned_poles = set()
        for pose_idx, pole_var, _coverage in c1_pole_bools:
            selected = int(pose_idx) in witness_poles
            pin(pole_var, 1 if selected else 0, f"c1pole.{pose_idx}")
            fixed_literals += 1
            if selected:
                pinned_poles.add(int(pose_idx))
        missing_poles = sorted(witness_poles - pinned_poles)
        if missing_poles:
            record["status"] = "POSE_NOT_IN_MASTER_DOMAIN"
            record["reason"] = (
                "witness power_pole pose indices absent from the C1 pole "
                f"variable set: {missing_poles[:10]}"
            )
            return record
        record["c1_power_pole_representation"] = {
            "pool_vars": len(c1_pole_bools),
            "witness_poles": len(witness_poles),
        }

    # --- pose-level optional slots (required first, then residual) -----------
    for tpl in sorted(
        set(delegate.required_optional_slots) | set(delegate.residual_optional_slots)
        | set(optional_by_tpl)
    ):
        required_slots = list(delegate.required_optional_slots.get(tpl, []))
        residual_slots = list(delegate.residual_optional_slots.get(tpl, []))
        pose_indices = sorted(
            optional_by_tpl.get(tpl, []),
            key=lambda pose_idx: master._pose_sort_key(tpl, int(pose_idx)),
        )
        if len(pose_indices) < len(required_slots) or len(pose_indices) > len(
            required_slots
        ) + len(residual_slots):
            record["status"] = "OPTIONAL_SLOT_COUNT_MISMATCH"
            record["reason"] = (
                f"template {tpl}: witness supplies {len(pose_indices)} placements but "
                f"the master has {len(required_slots)} required + "
                f"{len(residual_slots)} residual slots"
            )
            return record
        for slot, pose_idx in zip(required_slots, pose_indices[: len(required_slots)]):
            tup = tuple_by_idx.get(tpl, {}).get(int(pose_idx))
            if tup is None:
                record["status"] = "POSE_NOT_IN_MASTER_DOMAIN"
                record["reason"] = f"pose_idx {pose_idx} of {tpl} not in master domain"
                return record
            x_val, y_val, mode_id = tup
            pin(slot.x, x_val, f"{slot.key}.x")
            pin(slot.y, y_val, f"{slot.key}.y")
            pin(slot.mode, mode_id, f"{slot.key}.mode")
            fixed_literals += 3
        rest = pose_indices[len(required_slots) :]
        for slot_idx, slot in enumerate(residual_slots):
            if slot_idx < len(rest):
                tup = tuple_by_idx.get(tpl, {}).get(int(rest[slot_idx]))
                if tup is None:
                    record["status"] = "POSE_NOT_IN_MASTER_DOMAIN"
                    record["reason"] = (
                        f"pose_idx {rest[slot_idx]} of {tpl} not in master domain"
                    )
                    return record
                x_val, y_val, mode_id = tup
                if slot.active is not None:
                    pin(slot.active, 1, f"{slot.key}.active")
                    fixed_literals += 1
                pin(slot.x, x_val, f"{slot.key}.x")
                pin(slot.y, y_val, f"{slot.key}.y")
                pin(slot.mode, mode_id, f"{slot.key}.mode")
                fixed_literals += 3
            elif slot.active is not None:
                pin(slot.active, 0, f"{slot.key}.active")
                fixed_literals += 1

    # --- ghost anchor ---------------------------------------------------------
    # u_vars is keyed by position in the (possibly anchor-filtered) ghost domain
    # list, not by the unfiltered anchor index the witness verifier uses, so the
    # anchor is resolved through master._ghost_domains.
    u_vars = getattr(master, "u_vars", {}) or {}
    ghost_domains = list(getattr(master, "_ghost_domains", []) or [])
    if not u_vars or not ghost_domains:
        record["status"] = "NO_GHOST_DOMAIN"
        record["reason"] = "the master has no ghost anchor variables"
        return record
    selected_rect_idx: Optional[int] = None
    for rect_idx in sorted(u_vars):
        anchor = (ghost_domains[int(rect_idx)] or {}).get("anchor") or {}
        if int(anchor.get("x", -1)) == int(ghost_anchor_x) and int(
            anchor.get("y", -1)
        ) == int(ghost_anchor_y):
            selected_rect_idx = int(rect_idx)
            break
    if selected_rect_idx is None:
        record["status"] = "GHOST_ANCHOR_NOT_IN_DOMAIN"
        record["reason"] = (
            f"ghost anchor ({ghost_anchor_x},{ghost_anchor_y}) is not in the "
            "master's ghost anchor domain"
        )
        return record
    record["ghost_anchor_domain_rect_idx"] = selected_rect_idx
    for rect_idx, var in u_vars.items():
        pin(var, 1 if int(rect_idx) == selected_rect_idx else 0, f"ghost.{rect_idx}")
        fixed_literals += 1

    record["fixed_literals"] = fixed_literals
    record["ghost_anchor_domain_size"] = len(u_vars)

    record["fixed_variables"] = len(pins)

    # --- pin onto a COPY of the official model, as domain restrictions --------
    # Two reasons not to touch the live master and not to call master.solve():
    #   * the live model stays exactly as the official code built it (the gates
    #     get an unmodified master object);
    #   * this is a pure *feasibility* question, so the objective and any stored
    #     hints are dropped — the master's optimization path plays no part.
    # A pin whose value lies outside the variable's official domain is itself a
    # master-domain violation and is reported as one; it must never be applied,
    # because writing the domain blindly would widen it and hide the violation.
    check_model = cp_model.CpModel()
    proto = check_model.Proto()
    source_proto = delegate.model.Proto()
    if hasattr(proto, "CopyFrom"):  # older protobuf-backed API
        proto.CopyFrom(source_proto)
    else:
        proto.copy_from(source_proto)
    for clear_name in ("clear_objective", "clear_solution_hint"):
        clear = getattr(proto, clear_name, None)
        if callable(clear):
            clear()
        else:  # older protobuf-backed API
            proto.ClearField(clear_name.removeprefix("clear_"))

    def _domain_contains(domain: Sequence[int], value: int) -> bool:
        for i in range(0, len(domain), 2):
            if domain[i] <= value <= domain[i + 1]:
                return True
        return False

    for var_index, value, label in pins:
        variable = proto.variables[var_index]
        if not _domain_contains(list(variable.domain), value):
            record["status"] = "PIN_OUTSIDE_VARIABLE_DOMAIN"
            record["reason"] = (
                f"the witness requires {label} == {value}, which is outside the "
                f"master's own domain for that variable ({list(variable.domain)}); "
                "the layout violates the master's placement domain"
            )
            return record
        variable.domain.clear()
        variable.domain.extend([value, value])

    log.emit(
        "master_validation",
        "solve_start",
        fixed_literals=fixed_literals,
        pinned_variables=len(pins),
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    solver.parameters.num_workers = 1
    t1 = time.perf_counter()
    status = solver.Solve(check_model)
    record["solve_seconds"] = round(time.perf_counter() - t1, 3)
    status_name = solver.StatusName(status)
    record["status"] = status_name
    record["confirmed"] = status_name in {"OPTIMAL", "FEASIBLE"}
    log.emit(
        "master_validation",
        "solve_done",
        status=status_name,
        seconds=record["solve_seconds"],
    )
    if not record["confirmed"]:
        record["reason"] = (
            "the official master model, with every placement literal pinned to "
            f"the witness, solved to {status_name}"
        )
        return record

    # Sanity: the solver must have returned exactly the pinned values. If it did
    # not, the pinning is not binding what it claims to bind and the FEASIBLE is
    # worthless.
    diverged = [
        label
        for var_index, value, label in pins
        if int(solver.Value(check_model.GetIntVarFromProtoIndex(var_index))) != value
    ]
    record["pin_divergences"] = diverged[:20]
    if diverged:
        record["confirmed"] = False
        record["status"] = "PINNED_SOLUTION_DIVERGED"
        record["reason"] = (
            f"{len(diverged)} pinned variables came back with a different value; "
            "the fixed-literal encoding is not binding what it claims to bind"
        )
    return record


class GateWallClockExceeded(Exception):
    """--max-gate-wall-seconds fired: the gate stage is censored, not failed."""


class RequestedStageStop(Exception): ...


# --------------------------------------------------------------------------
# verdict
# --------------------------------------------------------------------------
_CENSORED_BINDING_RAW_STATUSES = {"UNKNOWN"}
_CENSORED_ROUTING_RAW_STATUSES = {
    "UNKNOWN",
    "CONNECTIVITY_GUARD_TIMEOUT",
}


def _verdict(
    name: str,
    reason: str,
    *,
    censored: bool = False,
    stage: Optional[str] = None,
    at_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    return {
        "verdict": name,
        "censored": bool(censored),
        "censored_stage": stage,
        "censored_at_seconds": at_seconds,
        "reason": reason,
    }


def _binding_raw_solver_status(proof_summary: Mapping[str, Any]) -> Optional[str]:
    summary = proof_summary.get("binding_summary")
    if isinstance(summary, Mapping):
        raw = summary.get("solver_status")
        if raw is not None:
            return str(raw)
    return None


def _routing_raw_solver_status(proof_summary: Mapping[str, Any]) -> Optional[str]:
    summary = proof_summary.get("routing_summary")
    if isinstance(summary, Mapping):
        last = summary.get("last_solve")
        if isinstance(last, Mapping):
            raw = last.get("status")
            if raw is not None:
                return str(raw)
    return None


def classify_verdict(
    *,
    controller_status: Optional[str],
    gate_returned_solution: Optional[bool],
    proof_summary: Mapping[str, Any],
    binding_seconds: float,
    routing_seconds: float,
    harness_exception: Optional[str],
    wall_clock_censored_at: Optional[float] = None,
    master_validation: Optional[Mapping[str, Any]] = None,
    stop_after: str = "gates",
) -> Dict[str, Any]:
    """Controller-status-first classification.

    The inner ``binding_status``/``routing_status`` pair is NOT sufficient: the
    official method returns UNKNOWN on several paths that carry conclusive-
    looking inner statuses (power-pole normalization failure with both gates
    FEASIBLE; binding INFEASIBLE or routing exhausted where the whole-layout
    nogood was refused because the independent re-verifier did not confirm).
    An official UNKNOWN therefore always stays UNKNOWN here.
    """
    binding_status = proof_summary.get("binding_status")
    routing_status = proof_summary.get("routing_status")
    contract_violation = proof_summary.get("subproblem_status_contract_violation")
    status = None if controller_status is None else str(controller_status)

    if wall_clock_censored_at is not None:
        return _verdict(
            "UNKNOWN_CENSORED",
            "the driver's --max-gate-wall-seconds guard fired while the "
            "binding/routing loop was still enumerating; nothing is proved "
            "either way",
            censored=True,
            stage="driver_wall_clock",
            at_seconds=float(wall_clock_censored_at),
        )
    if harness_exception is not None:
        return _verdict("HARNESS_ERROR", harness_exception)

    if stop_after == "intake":
        return _verdict("INTAKE_ACCEPTED", "intake, mapping, ghost identity and structure passed")

    if master_validation is not None and not bool(master_validation.get("confirmed")):
        master_status = str(master_validation.get("status"))
        if master_status == "UNKNOWN":
            return _verdict(
                "UNKNOWN_CENSORED", "fixed master budget exhausted; gates were not run",
                censored=True, stage="master_validation",
                at_seconds=float(master_validation.get("time_limit_seconds", 0.0)),
            )
        if master_status == "INFEASIBLE":
            return _verdict("MASTER_INFEASIBLE", "official fixed-layout master returned INFEASIBLE")
        if master_status == "MODEL_INVALID":
            return _verdict("UNKNOWN_STATUS_CONTRACT_VIOLATION", "fixed master returned MODEL_INVALID")
        return _verdict(
            "UNKNOWN_LAYOUT_NOT_MASTER_VALIDATED",
            "the fixed layout did not pass the official master feasibility "
            f"check (status={master_validation.get('status')}); no gate verdict "
            "may be attributed to it",
        )

    if stop_after == "master":
        return _verdict("MASTER_FEASIBLE", "fully pinned official master is feasible")

    if contract_violation:
        return _verdict(
            "UNKNOWN_STATUS_CONTRACT_VIOLATION",
            "the official run recorded a subproblem status-contract violation "
            f"({contract_violation!r}); nothing is proved either way",
        )

    if status == "CERTIFIED":
        if (
            gate_returned_solution
            and binding_status == "FEASIBLE"
            and routing_status == "FEASIBLE"
        ):
            return _verdict(
                "BOTH_GATES_FEASIBLE",
                "the official orchestrator returned CERTIFIED with a non-empty "
                "solution: binding FEASIBLE and routing FEASIBLE (routing "
                "includes the whole-layout _validate_selected_route_connectivity "
                "re-check), on a layout that passed the master feasibility check. "
                "This is a gate result, not a certification",
            )
        return _verdict(
            "UNKNOWN_OTHER",
            "the orchestrator returned CERTIFIED but the record is inconsistent "
            f"(returned_solution={gate_returned_solution} binding={binding_status} "
            f"routing={routing_status}); treated as inconclusive",
        )

    if status == "master_cut_added_continue":
        reverifier = proof_summary.get("independent_infeasibility_reverifier")
        confirmed = bool(
            isinstance(reverifier, Mapping) and reverifier.get("confirmed") is True
        )
        if not confirmed:
            return _verdict(
                "UNKNOWN_OTHER",
                "the orchestrator cut the layout but the independent "
                "infeasibility re-verifier did not confirm; no negative "
                "conclusion may be drawn",
            )
        if binding_status == "INFEASIBLE":
            return _verdict(
                "BINDING_INFEASIBLE",
                "the official binding gate rejected this fixed layout and the "
                "independent infeasibility re-verifier confirmed it",
            )
        if binding_status == "EXHAUSTED" and routing_status == "ALL_INFEASIBLE":
            return _verdict(
                "ROUTING_REJECTED_ALL_BINDINGS",
                "binding alternatives were enumerated to exhaustion, routing (or "
                "its precheck) rejected every one of them, and the independent "
                "infeasibility re-verifier confirmed the whole-layout nogood",
            )
        return _verdict(
            "UNKNOWN_LOOP_WANTED_A_NEW_LAYOUT",
            "the gate loop answered by cutting the layout and handing control "
            f"back to the master (binding={binding_status} routing={routing_status}). "
            "The layout is fixed here, so this is inconclusive rather than a "
            "rejection",
        )

    # Everything below is an official UNKNOWN (or an unexpected status): the
    # only question left is how to bookkeep the censoring.
    if binding_status == "TIMEOUT":
        raw = _binding_raw_solver_status(proof_summary)
        if raw is None or raw in _CENSORED_BINDING_RAW_STATUSES:
            return _verdict(
                "UNKNOWN_CENSORED",
                "binding CP-SAT returned "
                f"{raw or 'no recorded solver status'} at its time limit; "
                "nothing is proved either way",
                censored=True,
                stage="binding",
                at_seconds=float(binding_seconds),
            )
        return _verdict(
            "UNKNOWN_STATUS_CONTRACT_VIOLATION",
            "binding reported TIMEOUT but the raw CP-SAT status was "
            f"{raw!r}; that is a model/contract error, not a budget censor",
        )
    if routing_status == "TIMEOUT":
        raw = _routing_raw_solver_status(proof_summary)
        if raw is None or raw in _CENSORED_ROUTING_RAW_STATUSES:
            return _verdict(
                "UNKNOWN_CENSORED",
                "routing CP-SAT returned "
                f"{raw or 'no recorded solver status'} at its time limit; "
                "nothing is proved either way",
                censored=True,
                stage="routing",
                at_seconds=float(routing_seconds),
            )
        return _verdict(
            "UNKNOWN_STATUS_CONTRACT_VIOLATION",
            "routing reported TIMEOUT but the raw solve status was "
            f"{raw!r}; that is a model/contract error, not a budget censor",
        )
    if binding_status == "ALT_CAP_REACHED":
        return _verdict(
            "UNKNOWN_CENSORED",
            "binding alternative enumeration hit EXACT_B1_BINDING_ALT_CAP",
            censored=True,
            stage="binding_alternative_enumeration",
        )
    return _verdict(
        "UNKNOWN_OTHER",
        f"controller_status={status} binding={binding_status} "
        f"routing={routing_status}; see proof_summary",
    )


# --------------------------------------------------------------------------
# JSON coercion (truncation is recorded, never silent)
# --------------------------------------------------------------------------
def _jsonable(
    value: Any,
    depth: int = 0,
    *,
    max_depth: int = 6,
    max_list: Optional[int] = 200,
) -> Any:
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if depth > max_depth:
        return {
            "__truncated__": "max_depth",
            "max_depth": max_depth,
            "repr_prefix": str(value)[:500],
            "repr_length": len(str(value)),
        }
    if isinstance(value, Mapping):
        return {
            str(k): _jsonable(v, depth + 1, max_depth=max_depth, max_list=max_list)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        seq = list(value)
        if max_list is not None and len(seq) > max_list:
            return {
                "__truncated__": "max_list",
                "original_length": len(seq),
                "kept": max_list,
                "items": [
                    _jsonable(v, depth + 1, max_depth=max_depth, max_list=max_list)
                    for v in seq[:max_list]
                ],
            }
        return [
            _jsonable(v, depth + 1, max_depth=max_depth, max_list=max_list) for v in seq
        ]
    return {"__repr__": str(value)[:500], "repr_length": len(str(value))}


def _provenance(argv: Sequence[str], solution_path: Path, run_uuid: str) -> Dict[str, Any]:
    def _git(*args: str) -> Optional[str]:
        try:
            out = subprocess.run(
                ["git", *args],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=20,
            )
            if out.returncode != 0:
                return None
            return out.stdout.strip()
        except Exception:  # noqa: BLE001
            return None

    try:
        from ortools import __version__ as ortools_version  # type: ignore
    except Exception:  # noqa: BLE001
        ortools_version = None
    dirty = _git("status", "--porcelain")
    return {
        "run_uuid": run_uuid,
        "argv": list(argv),
        "driver_path": str(Path(__file__).resolve()),
        "driver_sha256": _sha256_file(Path(__file__).resolve()),
        "witness_path": str(solution_path),
        "witness_sha256": _sha256_file(solution_path),
        "python": sys.version,
        "python_executable": sys.executable,
        "ortools_version": ortools_version,
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
        "git_head": _git("rev-parse", "HEAD"),
        "git_dirty": (None if dirty is None else bool(dirty)),
        "git_dirty_paths": (
            None if dirty is None else [line for line in dirty.splitlines()][:50]
        ),
        "certified_source_digest_note": (
            "ExactCampaign's certified source digest covers root *.py, src/ and "
            "scripts/ only; this driver lives under docs/research/ and is NOT in "
            "that digest — driver_sha256 above is the binding record"
        ),
    }


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a fixed externally-supplied witness layout against the "
            "official master and then run the official binding + routing gates "
            "on it (research-only)."
        )
    )
    parser.add_argument("--solution", type=Path, default=DEFAULT_SOLUTION)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=(
            "must be "
            f"{OUT_ROOT} or a subdirectory of it; a fresh unique run directory "
            "is created inside it"
        ),
    )
    parser.add_argument(
        "--tag",
        default="run",
        help="strict leaf name [A-Za-z0-9][A-Za-z0-9._-]{0,63}",
    )
    parser.add_argument("--ghost-w", type=int, default=DEFAULT_GHOST_W)
    parser.add_argument("--ghost-h", type=int, default=DEFAULT_GHOST_H)
    parser.add_argument("--ghost-anchor-x", type=int, default=DEFAULT_GHOST_ANCHOR_X)
    parser.add_argument("--ghost-anchor-y", type=int, default=DEFAULT_GHOST_ANCHOR_Y)
    parser.add_argument("--stop-after", choices=("intake", "master", "gates"), default="gates")
    parser.add_argument(
        "--binding-seconds",
        type=float,
        default=600.0,
        help="CP-SAT time limit for each binding solve (default 600)",
    )
    parser.add_argument(
        "--routing-seconds",
        type=float,
        default=600.0,
        help="CP-SAT time limit for each routing solve (default 600)",
    )
    parser.add_argument(
        "--master-validation-seconds",
        type=float,
        default=600.0,
        help="CP-SAT time limit for the fixed-layout master feasibility solve",
    )
    parser.add_argument(
        "--skip-master-validation",
        action="store_true",
        help=(
            "skip the master feasibility stage. The gates then run on an "
            "unvalidated layout, so every verdict is forced to "
            "UNKNOWN_LAYOUT_NOT_MASTER_VALIDATED — diagnostic use only"
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="EXACT_CP_SAT_WORKERS (1 = clean wall-clock attribution)",
    )
    parser.add_argument(
        "--binding-alt-cap",
        type=int,
        default=0,
        help=(
            "EXACT_B1_BINDING_ALT_CAP — cap the binding-alternative enumeration "
            "loop (0 = unset/unbounded). Hitting the cap is bookkept as UNKNOWN "
            "censored, never as infeasible"
        ),
    )
    parser.add_argument(
        "--max-gate-wall-seconds",
        type=float,
        default=0.0,
        help=(
            "best-effort in-process SIGALRM guard around the gate stage (0 = "
            "off). It cannot interrupt a native CP-SAT call; the authoritative "
            "envelope is run_guarded.sh. Firing it yields UNKNOWN "
            "censored@driver_wall_clock, not a failure"
        ),
    )
    parser.add_argument(
        "--memory-sample-interval",
        type=float,
        default=0.5,
        help="seconds between /proc/self/status samples (clamped to <= 1.0)",
    )
    parser.add_argument(
        "--ghost-anchor-filter",
        dest="ghost_anchor_filter",
        action="store_true",
        default=True,
        help=(
            "build the master ghost domain for the single witness anchor only "
            "(default). The layout under test fixes the ghost anchor anyway, so "
            "narrowing the domain to it cannot change this layout's "
            "satisfiability; it only saves build RAM/time. Recorded as "
            "ghost.anchor_filter_applied. NOT a certified-search configuration"
        ),
    )
    parser.add_argument(
        "--no-ghost-anchor-filter",
        dest="ghost_anchor_filter",
        action="store_false",
        help="build the full ghost anchor domain (slower, more RAM)",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)

    # --- env hygiene BEFORE any mutation -------------------------------------
    env_audit = _enforce_env_hygiene()
    if not env_audit["ok"]:
        return EXIT_USAGE
    if args.workers <= 0:
        print("--workers must be a positive integer", file=sys.stderr, flush=True)
        return EXIT_USAGE
    if args.memory_sample_interval <= 0:
        print("--memory-sample-interval must be positive", file=sys.stderr, flush=True)
        return EXIT_USAGE
    if args.skip_master_validation and args.stop_after != "gates":
        print("--skip-master-validation requires --stop-after gates", file=sys.stderr, flush=True)
        return EXIT_USAGE

    # --- audit BEFORE anything is created ------------------------------------
    audit_before = _audit_snapshot()

    run_dir, error = _resolve_run_dir(args.out_dir, str(args.tag))
    if run_dir is None:
        print(str(error), file=sys.stderr, flush=True)
        return EXIT_USAGE

    run_uuid = str(uuid.uuid4())
    result_path = run_dir / f"{args.tag}_result.json"
    stages_path = run_dir / f"{args.tag}_stages.json"
    memory_path = run_dir / f"{args.tag}_memory.jsonl"
    proof_full_path = run_dir / f"{args.tag}_proof_summary_full.json"
    done_path = run_dir / f"{args.tag}.DONE"
    scratch = run_dir / "scratch"
    scratch_tmp = run_dir / "scratch_tmp"
    scratch.mkdir()
    scratch_tmp.mkdir()

    # Nothing this process (or a library under it) may put a temp file outside
    # the run directory — tempfile honours TMPDIR, and CutManager touches its
    # checkpoint dir on construction.
    os.environ["TMPDIR"] = str(scratch_tmp)
    os.environ["TEMP"] = str(scratch_tmp)
    os.environ["TMP"] = str(scratch_tmp)
    tempfile.tempdir = str(scratch_tmp)

    os.environ["PYTHONUNBUFFERED"] = "1"
    os.environ["EXACT_CP_SAT_WORKERS"] = str(int(args.workers))
    if args.binding_alt_cap > 0:
        os.environ["EXACT_B1_BINDING_ALT_CAP"] = str(int(args.binding_alt_cap))

    log = StageLog()
    sampler = MemorySampler(memory_path, args.memory_sample_interval, log)
    sampler.start()
    log.emit("run", "start", run_dir=str(run_dir), run_uuid=run_uuid)

    result: Dict[str, Any] = {
        "driver": "docs/research/band22_registration_20260805/registration_driver.py",
        "purpose": (
            "validate the band22 witness layout against the official master and "
            "run the official binding + routing gates on it"
        ),
        "research_only": True,
        "research_only_disclaimer": RESEARCH_ONLY_DISCLAIMER,
        "requested_stop_after": args.stop_after,
        "run_uuid": run_uuid,
        "run_dir": str(run_dir),
        "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tag": args.tag,
        "provenance": _provenance(argv, args.solution, run_uuid),
        "env_audit": {
            "inherited_exact_env": env_audit["inherited"],
            "owned_knobs": list(OWNED_ENV_KNOBS),
        },
        "budgets": {
            "binding_seconds": float(args.binding_seconds),
            "routing_seconds": float(args.routing_seconds),
            "master_validation_seconds": float(args.master_validation_seconds),
            "workers": int(args.workers),
            "binding_alt_cap": int(args.binding_alt_cap),
            "max_gate_wall_seconds": float(args.max_gate_wall_seconds),
            "max_gate_wall_seconds_note": (
                "best-effort SIGALRM only; the hard envelope is run_guarded.sh"
            ),
        },
        "ghost": {
            "w": int(args.ghost_w),
            "h": int(args.ghost_h),
            "anchor_x": int(args.ghost_anchor_x),
            "anchor_y": int(args.ghost_anchor_y),
            "anchor_filter_applied": bool(args.ghost_anchor_filter),
        },
    }

    harness_exception: Optional[str] = None
    controller_status: Optional[str] = None
    proof_summary: Dict[str, Any] = {}
    proof_summary_full: Any = None
    wall_clock_censored_at: Optional[float] = None
    master_validation: Optional[Dict[str, Any]] = None
    gate_returned_solution: Optional[bool] = None
    completed_stage = "none"
    exit_code = EXIT_OK

    try:
        log.emit("witness", "load", path=str(args.solution))
        solution, witness_meta = load_witness_solution(args.solution)
        result["witness"] = witness_meta
        log.emit("witness", "loaded", instances=len(solution))

        v2_input = witness_meta.get("witness_schema_version") == "band22-witness/2"
        if v2_input:
            verify_witness_snapshot_identity(result["provenance"].get("witness_sha256"), witness_meta.get("sha256"))
        v2_ghost = witness_meta.get("ghost") if v2_input else None
        if v2_input and not isinstance(v2_ghost, Mapping):
            raise ValueError("v2 adapter did not return its derived ghost geometry")
        ghost_fields = (("w", "ghost_w"), ("h", "ghost_h"), ("anchor_x", "ghost_anchor_x"), ("anchor_y", "ghost_anchor_y"))
        explicit_flags = {value.split("=", 1)[0] for value in argv}
        ghost_flags = {f"--{arg_name.replace('_', '-')}" for _, arg_name in ghost_fields}
        if v2_input and explicit_flags & ghost_flags:
            raise ValueError("v2 ghost geometry is witness-derived; CLI ghost overrides are forbidden")
        if v2_input:
            for key, arg_name in ghost_fields:
                setattr(args, arg_name, int(v2_ghost[key]))
        result["ghost"].update({key: int(getattr(args, arg_name)) for key, arg_name in ghost_fields})

        canonical_ghost_pick = build_ghost_pick(
            ghost_w=args.ghost_w,
            ghost_h=args.ghost_h,
            anchor_x=args.ghost_anchor_x,
            anchor_y=args.ghost_anchor_y,
        )
        canonical_ghost_idx = int(canonical_ghost_pick["pose_idx"])
        if v2_input and int(v2_ghost["canonical_unfiltered_ghost_idx"]) != canonical_ghost_idx:
            raise ValueError("v2 adapter canonical ghost identity disagrees with official formula")
        result["ghost"]["canonical_unfiltered_ghost_idx"] = canonical_ghost_idx
        result["ghost"]["canonical_unfiltered_ghost_idx_source"] = (
            "src/search/pr2_l0_fixed_witness_core.py "
            "_expected_unfiltered_ghost_anchor_index"
        )
        log.emit("ghost_pick", "canonical_computed", pose_idx=canonical_ghost_idx)

        from src.models.master_model import MasterPlacementModel
        from src.search.benders_loop import ExactSearchSession

        result["env_audit"]["owned_knob_classification"] = _classify_owned_env()

        log.emit("session", "build_start")
        t0 = time.perf_counter()
        session = ExactSearchSession.create(PROJECT_ROOT, solve_mode="certified_exact")
        session_seconds = round(time.perf_counter() - t0, 3)
        result["session_build_seconds"] = session_seconds
        result["artifact_hashes"] = _jsonable(session.artifact_hashes)
        log.emit("session", "build_done", seconds=session_seconds)
        if v2_input:
            from docs.research.band22_registration_20260805.band22_v2_adapter import verify_against_session_pins

            verify_against_session_pins(witness_meta.get("actual_source_hashes") or {}, session.artifact_hashes)
            result["v2_source_hash_session_pin_match"] = True
            result["v2_binding_projection"] = witness_meta.get("binding_projection")

        anchor_filter = (
            [(int(args.ghost_anchor_x), int(args.ghost_anchor_y))]
            if args.ghost_anchor_filter
            else None
        )
        log.emit("master", "build_start", ghost=f"{args.ghost_w}x{args.ghost_h}")
        t1 = time.perf_counter()
        master = MasterPlacementModel.from_exact_core(
            session.core,
            ghost_rect=(int(args.ghost_w), int(args.ghost_h)),
            ghost_anchor_filter=anchor_filter,
        )
        master.build()
        master_seconds = round(time.perf_counter() - t1, 3)
        result["master_build_seconds"] = master_seconds
        log.emit("master", "build_done", seconds=master_seconds)

        gate_ghost_idx = resolve_live_ghost_domain_index(
            master, anchor_x=int(args.ghost_anchor_x), anchor_y=int(args.ghost_anchor_y)
        )
        result["ghost"]["gate_ghost_domain_idx"] = gate_ghost_idx
        gate_ghost_pick = dict(canonical_ghost_pick)
        gate_ghost_pick["pose_idx"] = gate_ghost_idx
        log.emit("ghost_pick", "live_resolved", pose_idx=gate_ghost_idx)

        structure = validate_layout_structure(
            solution=solution,
            master=master,
            ghost_w=int(args.ghost_w),
            ghost_h=int(args.ghost_h),
            ghost_anchor_x=int(args.ghost_anchor_x),
            ghost_anchor_y=int(args.ghost_anchor_y),
            active_terminal_cells=witness_meta.get("active_terminal_cells"),
            route_component_cells=witness_meta.get("route_component_cells"),
        )
        result["layout_structure_check"] = structure
        log.emit(
            "layout_structure",
            "checked",
            ok=structure["ok"],
            problems=structure["problem_count"],
            body_cells=structure["body_cells"],
        )
        if not structure["ok"]:
            raise RuntimeError(
                "the witness layout failed the structural validator "
                f"({structure['problem_count']} problems); refusing to feed the "
                "official gates a layout that is not a well-formed master solution"
            )
        completed_stage = "intake"

        if args.stop_after == "intake":
            raise RequestedStageStop
        if args.skip_master_validation:
            master_validation = {
                "mode": "skipped",
                "confirmed": False,
                "status": "SKIPPED_BY_FLAG",
                "reason": "--skip-master-validation was passed",
            }
            log.emit("master_validation", "skipped")
        else:
            master_validation = validate_master_feasibility(
                master=master,
                solution=solution,
                ghost_anchor_x=int(args.ghost_anchor_x),
                ghost_anchor_y=int(args.ghost_anchor_y),
                time_limit_seconds=float(args.master_validation_seconds),
                log=log,
            )
        result["master_feasibility_check"] = master_validation
        completed_stage = "master"
        if args.stop_after == "master" or (
            not bool(master_validation.get("confirmed"))
            and not args.skip_master_validation
        ):
            raise RequestedStageStop

        from src.models.cut_manager import CutManager
        from src.search.benders_loop import LBBDController

        gate_solution: Dict[str, Any] = dict(solution)
        gate_solution["ghost_pick"] = gate_ghost_pick

        result["scratch_checkpoint_dir"] = str(scratch)
        controller = LBBDController(
            master=master,
            cut_manager=CutManager(checkpoint_dir=scratch, solve_mode="certified_exact"),
            project_root=PROJECT_ROOT,
            solve_mode="certified_exact",
            master_seconds=1.0,  # unused: the master search is never run here
            binding_seconds=float(args.binding_seconds),
            routing_seconds=float(args.routing_seconds),
            max_iterations=1,
            artifact_hashes=session.artifact_hashes,
            heartbeat_callback=log.heartbeat_callback,
            session=session,
        )

        log.emit("gates", "start")
        t2 = time.perf_counter()
        wall_guard_armed = float(args.max_gate_wall_seconds) > 0.0
        if wall_guard_armed:

            def _wall_guard(signum: int, frame: Any) -> None:  # noqa: ARG001
                raise GateWallClockExceeded(
                    f"gate stage exceeded {args.max_gate_wall_seconds}s"
                )

            signal.signal(signal.SIGALRM, _wall_guard)
            signal.setitimer(signal.ITIMER_REAL, float(args.max_gate_wall_seconds))
        try:
            controller_status, gate_output = controller._run_exact_binding_and_routing(
                iteration=0,
                solution=gate_solution,
                diagnostic_flow_status="SKIPPED_FIXED_LAYOUT_DRIVER",
            )
            controller_status = str(controller_status)
            gate_returned_solution = gate_output is not None
        except GateWallClockExceeded as exc:
            wall_clock_censored_at = float(args.max_gate_wall_seconds)
            controller_status = "DRIVER_WALL_CLOCK_CENSORED"
            gate_returned_solution = False
            log.emit("gates", "wall_clock_censored", detail=str(exc))
        except Exception as exc:  # noqa: BLE001 — recorded, and it IS a failure
            harness_exception = f"{type(exc).__name__}: {exc}"
            controller_status = "HARNESS_EXCEPTION"
            gate_returned_solution = False
            exit_code = EXIT_RUN_FAILURE
            log.emit("gates", "exception", detail=harness_exception)
        finally:
            if wall_guard_armed:
                signal.setitimer(signal.ITIMER_REAL, 0.0)
        result["gate_returned_solution"] = gate_returned_solution
        gate_seconds = round(time.perf_counter() - t2, 3)
        result["gate_wall_seconds"] = gate_seconds
        log.emit("gates", "done", seconds=gate_seconds, status=controller_status)
        completed_stage = "gates"

        raw_proof_summary = getattr(controller, "last_proof_summary", None) or {}
        proof_summary = _jsonable(raw_proof_summary)
        proof_summary_full = _jsonable(raw_proof_summary, max_depth=64, max_list=None)
    except RequestedStageStop:
        pass
    except Exception as exc:  # noqa: BLE001 — driver-level failure
        harness_exception = f"{type(exc).__name__}: {exc}"
        controller_status = controller_status or "DRIVER_EXCEPTION"
        exit_code = EXIT_RUN_FAILURE
        log.emit("driver", "exception", detail=harness_exception)

    sampler.stop()

    verdict = classify_verdict(
        controller_status=controller_status,
        gate_returned_solution=gate_returned_solution,
        proof_summary=proof_summary,
        binding_seconds=float(args.binding_seconds),
        routing_seconds=float(args.routing_seconds),
        harness_exception=harness_exception,
        wall_clock_censored_at=wall_clock_censored_at,
        master_validation=master_validation,
        stop_after=str(args.stop_after),
    )
    if verdict["verdict"] == "HARNESS_ERROR":
        exit_code = EXIT_RUN_FAILURE

    audit_after = _audit_snapshot()
    audit = _audit_diff(audit_before, audit_after)
    log.emit("side_effect_audit", "compared", clean=audit["clean"])
    if not audit["clean"]:
        # An audit violation overrides the verdict, not just the exit code.
        verdict = {
            "verdict": "INVALIDATED_SIDE_EFFECT_AUDIT",
            "censored": False,
            "censored_stage": None,
            "censored_at_seconds": None,
            "reason": (
                "the run touched data/checkpoints, data/solutions or "
                "data/blueprints; no verdict from this run may be used"
            ),
            "verdict_before_audit": verdict,
        }
        exit_code = EXIT_RUN_FAILURE

    result["controller_return_status"] = controller_status
    result["completed_stage"] = completed_stage
    result["harness_exception"] = harness_exception
    result["proof_summary"] = proof_summary
    result["proof_summary_truncation_note"] = (
        "proof_summary here is depth/length coerced; truncation is explicit "
        "(objects with __truncated__). The untruncated dump is "
        f"{proof_full_path.name}"
    )
    result["gate_results"] = {
        "binding_status": proof_summary.get("binding_status"),
        "routing_status": proof_summary.get("routing_status"),
        "binding_raw_solver_status": _binding_raw_solver_status(proof_summary),
        "routing_raw_solve_status": _routing_raw_solver_status(proof_summary),
        "enumerated_bindings": proof_summary.get("enumerated_bindings"),
        "routing_attempts": proof_summary.get("routing_attempts"),
        "binding_alternative_cap": proof_summary.get("binding_alternative_cap"),
        "master_follow_up": proof_summary.get("master_follow_up"),
        "routing_precheck": proof_summary.get("routing_precheck"),
        "blocked_port": proof_summary.get("blocked_port"),
        "independent_infeasibility_reverifier": proof_summary.get(
            "independent_infeasibility_reverifier"
        ),
        "subproblem_status_contract_violation": proof_summary.get(
            "subproblem_status_contract_violation"
        ),
    }
    result["verdict"] = verdict
    result["memory"] = sampler.summary()
    result["side_effect_audit"] = audit
    result["stage_log"] = log.records
    result["finished_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result["total_wall_seconds"] = round(time.perf_counter() - log.started, 3)
    result["exit_code"] = exit_code

    if proof_summary_full is not None:
        try:
            atomic_write_json(proof_full_path, proof_summary_full)
        except Exception as exc:  # noqa: BLE001
            result["proof_summary_full_error"] = f"{type(exc).__name__}: {exc}"
    atomic_write_json(stages_path, {"stages": log.records})
    result_sha = atomic_write_json(result_path, result)

    # Terminal receipt, written last, atomically, after the verdict, the audit
    # and the exit code are all decided.
    receipt = {
        "receipt": "band22_registration_driver",
        "receipt_version": "band22-registration-driver/2",
        "run_uuid": run_uuid,
        "tag": args.tag,
        "witness_schema_version": (result.get("witness") or {}).get("witness_schema_version"),
        "requested_stop_after": args.stop_after,
        "completed_stage": completed_stage,
        "finished_utc": result["finished_utc"],
        "exit_code": exit_code,
        "verdict": verdict["verdict"],
        "censored": verdict["censored"],
        "censored_stage": verdict["censored_stage"],
        "censored_at_seconds": verdict.get("censored_at_seconds"),
        "verdict_reason": verdict.get("reason"),
        "gate_ghost_domain_idx": result["ghost"].get("gate_ghost_domain_idx"),
        "canonical_unfiltered_ghost_idx": result["ghost"].get("canonical_unfiltered_ghost_idx"),
        "v2_binding_projection": result.get("v2_binding_projection"),
        "controller_search_boundary": CONTROLLER_SEARCH_BOUNDARY,
        "controller_return_status": controller_status,
        "binding_status": proof_summary.get("binding_status"),
        "routing_status": proof_summary.get("routing_status"),
        "master_feasibility_confirmed": bool(
            (master_validation or {}).get("confirmed")
        ),
        "side_effect_audit_clean": audit["clean"],
        "harness_exception": harness_exception,
        "result_path": str(result_path),
        "result_sha256": result_sha,
        "vm_hwm_mb": result["memory"].get("vm_hwm_mb"),
        "vm_swap_peak_mb": result["memory"].get("vm_swap_peak_mb"),
        "total_wall_seconds": result["total_wall_seconds"],
    }
    atomic_write_json(done_path, receipt)

    # Convenience pointer for supervisors; the run directory itself is the
    # authority and is never overwritten.
    try:
        atomic_write_text(
            Path(os.path.realpath(str(args.out_dir))) / f"{args.tag}.LATEST",
            str(run_dir) + "\n",
        )
    except Exception:  # noqa: BLE001 — pointer is a convenience, not evidence
        pass

    print("", flush=True)
    print(json.dumps(receipt, ensure_ascii=False), flush=True)
    if not audit["clean"]:
        print(
            "WARNING: side-effect audit is NOT clean; see side_effect_audit in "
            f"{result_path}",
            file=sys.stderr,
            flush=True,
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
