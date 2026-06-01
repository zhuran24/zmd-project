"""B1 toy translator — build 81K BoolVar toy master + 9-family cert translator.

Per MERGER §5.2 + §5.4 G1-G4b:
- Load real prod pose registry from ``data/preprocessed/candidate_placements.json``
  (81,795 poses across 7 facility pools).
- Build toy master with **one BoolVar per (facility_type, pose_id)** plus a simple
  per-instance "group demand" sum constraint (just to make demand counts shaped
  like prod). **No ExactlyOne, no port-linking, no anti-overlap, no objective.**
  Those are P1.3A 主体 work — this toy only measures build/solve cost.
- 9-family cert → CP-SAT constraint translator. Each cert is converted to a
  single ``model.AddBoolOr / AddLinearConstraint`` clause referencing the
  corresponding BoolVars. Pure structural — sound vs unsound is not the focus
  here (Finding 5 #2 sizing only).

Translator output: each cert ⇒ one CP-SAT constraint append + bookkeeping.

This file is spike-only. Off-limits paths untouched.
"""
from __future__ import annotations

import base64
import hashlib
import json
import random
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ortools.sat.python import cp_model


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLACEMENTS_PATH = REPO_ROOT / "data" / "preprocessed" / "candidate_placements.json"
MANDATORY_PATH = REPO_ROOT / "data" / "preprocessed" / "mandatory_exact_instances.json"


# ============================================================================
# Pose registry — load + flat index for translator lookup
# ============================================================================


@dataclass
class PoseRegistry:
    """Flat index of all poses across all 7 facility pools.

    ``poses`` is the canonical flat list (len == 81795 in prod).
    ``var_by_idx`` is the CP-SAT BoolVar created for each pose.
    ``idx_by_facility_pose`` allows reverse lookup from cert literals
    ``(facility_type, pose_id) → flat_idx``.
    """
    poses: List[Tuple[str, str]]  # (facility_type, pose_id)
    var_by_idx: List[cp_model.IntVar] = field(default_factory=list)
    idx_by_facility_pose: Dict[Tuple[str, str], int] = field(default_factory=dict)

    @property
    def n_vars(self) -> int:
        return len(self.var_by_idx)

    @property
    def n_poses(self) -> int:
        return len(self.poses)


def load_pose_registry() -> PoseRegistry:
    """Load real prod pose registry (81795 poses).

    Note: observed in spike runner on Python 3.14.x — calling
    ``json.loads(Path.read_text())`` on very large files raises
    non-deterministic ``ValueError: invalid literal for int() with base 10``
    from the json scanner. Using ``read_bytes().decode('utf-8')`` produces an
    identical str but takes a different code path that avoids the failure in
    our local environment. This is a spike-local portability workaround; no
    upstream CPython stdlib regression is asserted as proven and no master
    src impact is claimed. Observed locally on Python 3.14.5 with the 53 MB
    ``candidate_placements.json``.
    """
    placements = json.loads(PLACEMENTS_PATH.read_bytes().decode("utf-8"))
    pools = placements.get("facility_pools", {})
    poses: List[Tuple[str, str]] = []
    for ft in sorted(pools.keys()):
        for pose in pools[ft]:
            poses.append((ft, pose["pose_id"]))
    reg = PoseRegistry(poses=poses)
    reg.idx_by_facility_pose = {fp: i for i, fp in enumerate(poses)}
    return reg


# ============================================================================
# Proto size measurement — OR-Tools 9.15 pybind wrapper has no ByteSize/
# SerializeToString. We use ``CpModel.ExportToFile`` to write the binary
# proto then ``Path.stat().st_size`` to get the on-wire size. Slow at 100K
# but accurate. Used at milestone points only, not in hot loops.
# ============================================================================


def measure_proto_bytesize(model: cp_model.CpModel) -> int:
    """Return serialized proto size in bytes (via ExportToFile to /tmp)."""
    with tempfile.NamedTemporaryFile(
        prefix="spike_proto_",
        suffix=".pb",
        dir="/tmp",
        delete=True,
    ) as f:
        # ExportToFile writes binary protobuf if path ends with .pb / .bin /
        # not .txt. Else text format.
        path = f.name
    try:
        ok = model.ExportToFile(path)
        if not ok:
            return -1
        size = Path(path).stat().st_size
    finally:
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:
            pass
    return size


# ============================================================================
# Toy master build — 81K BoolVar + simple group demand sums
# ============================================================================


@dataclass
class ToyMasterBuildReport:
    n_vars: int
    n_demand_constraints: int
    n_cuts_applied: int
    build_wall_s: float
    proto_bytesize: int
    notes: List[str] = field(default_factory=list)


def build_toy_master(
    registry: PoseRegistry,
    *,
    add_demand_constraints: bool = True,
) -> Tuple[cp_model.CpModel, ToyMasterBuildReport]:
    """Build the bare toy master: 81K BoolVar + 266 group demand constraints.

    ``add_demand_constraints=True`` adds one ``sum(group_vars) >= demand`` per
    instance. (Per spec: "simple demand constraint (group demand 直接 sum),
    不加 ExactlyOne / port-linking".)
    """
    t0 = time.monotonic()
    model = cp_model.CpModel()

    # Step 1: declare 81795 BoolVar — one per (facility_type, pose_id).
    registry.var_by_idx = []
    for ft, pid in registry.poses:
        v = model.NewBoolVar(f"x_{ft}__{pid}")
        registry.var_by_idx.append(v)

    n_demand = 0
    if add_demand_constraints:
        # Step 2: group vars by facility_type.
        vars_by_ft: Dict[str, List[cp_model.IntVar]] = defaultdict(list)
        for (ft, _pid), v in zip(registry.poses, registry.var_by_idx):
            vars_by_ft[ft].append(v)
        # Step 3: per-instance "demand" — for spike sizing it's just one sum
        # per instance with bound = 1 (the per-instance link is structural, not
        # ExactlyOne; we keep it loose so spike measures pure build cost).
        instances = json.loads(MANDATORY_PATH.read_text())
        by_ft_inst_count: Dict[str, int] = defaultdict(int)
        for inst in instances:
            by_ft_inst_count[inst["facility_type"]] += 1
        # For each facility_type, add a single "group total >= n_instances"
        # constraint (266 instances total ⇒ at most 7 such constraints, but
        # we add 266 per-instance sums to match shape per spec).
        for inst in instances:
            ft = inst["facility_type"]
            pool_vars = vars_by_ft.get(ft, [])
            if not pool_vars:
                continue
            # demand >= 1 (loose; just produces a real linear constraint).
            model.Add(sum(pool_vars) >= 1)
            n_demand += 1

    build_wall = time.monotonic() - t0
    proto_size = measure_proto_bytesize(model)
    rpt = ToyMasterBuildReport(
        n_vars=registry.n_vars,
        n_demand_constraints=n_demand,
        n_cuts_applied=0,
        build_wall_s=build_wall,
        proto_bytesize=proto_size,
    )
    return model, rpt


# ============================================================================
# Cert payload parsing — extract literal-style refs for translation
# ============================================================================


def _stable_hash(s: str) -> int:
    """Process-stable 32-bit hash. 内置 ``hash()`` 对 str 默认带 PYTHONHASHSEED
    随机盐, 跨进程不可复现 (GPT 第九审 finding: fallback / remap 因此每次跑不一样)。
    用 blake2b 取代, 同一输入永远同一输出。"""
    return int.from_bytes(hashlib.blake2b(s.encode("utf-8"), digest_size=4).digest(), "big")


def _decode_cert_b64(b64: str) -> Optional[dict]:
    if not b64:
        return None
    try:
        # GPT 第九审 finding: 不带 validate 的 b64decode 会静默丢弃非 base64 字符,
        # 于是 "合法 b64 里混入垃圾字符" 不 fail-closed。validate=True 让任何非
        # alphabet 字符 raise → 走 except → None → F3 family return []。
        raw = base64.b64decode(b64, validate=True)
        payload = json.loads(raw)
    except Exception:
        return None
    # GPT 八审 V21-8F1 fix: 非 dict root (None / list / string) 返回 None,
    # 不让 caller .get() raise AttributeError. Fail-closed contract: 任何
    # 不规范 payload → F3 family return [], fallback families skip.
    return payload if isinstance(payload, dict) else None


def _cert_literal_pairs(cert_record: dict, fallback_pool: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Best-effort extraction of (facility_type, pose_id) literal pairs from cert.

    Different families embed literal references under different keys
    (oracle_assignment_witness, occupied_cells, facility_cells, etc.).
    For sizing purposes any literal-shaped list works. If parsing fails we
    fall back to a deterministic seeded pick from the global pool.
    """
    payload = _decode_cert_b64(cert_record.get("cert_payload_b64", ""))
    pairs: List[Tuple[str, str]] = []

    # GPT 八审 V21-8F1 fix: F3 port_exposure family fail-closed 检查必须移到
    # ``if payload is not None:`` 块**之外** —— 当 payload decode 失败 (bad
    # base64 / 非 dict root) 时, 旧代码会落到下游 fallback 合成 3-literal
    # synthetic, 等于 silently hide schema drift. 现在 F3 family 一律走
    # explicit fail-closed: payload=None → 直接 return [].
    if cert_record.get("family") == "port_exposure":
        if payload is None:
            return []
        facility_group = payload.get("facility_group")
        facility_pose_id = payload.get("facility_pose_id")
        blocking = payload.get("blocking_facility")
        if (
            isinstance(facility_group, str)
            and isinstance(facility_pose_id, str)
            and isinstance(blocking, (list, tuple))
            and len(blocking) >= 3
            and isinstance(blocking[0], str)
            and isinstance(blocking[2], str)
        ):
            return [
                (facility_group, facility_pose_id),
                (blocking[0], blocking[2]),
            ]
        # F3 is literal-mode with a fixed cert schema. Do not synthesize a
        # three-literal fallback here: that would hide schema drift and
        # reintroduce the v19 semantics-overclaim class. Malformed F3 certs
        # should be skipped by translate_certs_to_constraints().
        return []

    if payload is not None:
        # Strategy 1: oracle_assignment_witness = [[group_id, pose_id], ...]
        witness = payload.get("oracle_assignment_witness")
        if not pairs and isinstance(witness, list):
            for entry in witness:
                if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                    g, p = str(entry[0]), str(entry[1])
                    pairs.append((g, p))
        # Strategy 2: literal_count in record (we don't have full literal triples,
        # but the witness above usually covers it).
    if not pairs:
        # Fallback: synthesize literal pairs from fallback_pool deterministically
        # by hashing the cert payload to a stable seed. Each cert gets ~3 poses.
        seed = _stable_hash(cert_record.get("cut_id", "")) & 0xFFFFFFFF
        rng = random.Random(seed)
        k = min(3, len(fallback_pool))
        sample_idxs = rng.sample(range(len(fallback_pool)), k)
        pairs = [fallback_pool[i] for i in sample_idxs]
    return pairs


# ============================================================================
# 9-family translator — cert → CP-SAT constraint
# ============================================================================


@dataclass
class TranslationReport:
    n_certs_in: int
    n_certs_applied: int
    n_certs_skipped: int
    n_constraints_added: int
    per_family_applied: Dict[str, int] = field(default_factory=dict)
    per_family_skipped: Dict[str, int] = field(default_factory=dict)
    translation_wall_s: float = 0.0
    # GPT 第九审 finding: unknown (facility_type, pose_id) 被静默 hash-remap 到任意
    # 真 var 还照计 applied → "100K applied=100%" 误导。这里把 remap 暴露成 telemetry,
    # 让 applied 计数不再静默掩盖 "literal 没绑到真 registry"。
    n_pairs_total: int = 0
    n_pairs_remapped: int = 0
    per_family_remapped: Dict[str, int] = field(default_factory=dict)


def translate_certs_to_constraints(
    model: cp_model.CpModel,
    registry: PoseRegistry,
    cert_records: List[dict],
) -> TranslationReport:
    """For each cert: add a structural ``AddBoolOr / AddLinearConstraint`` clause.

    Family-specific shape (deliberately simplified for sizing):
    - F1 region_capacity: AddLinearConstraint(sum(lits) <= K) where K = max(0, len-1)
      (mimics "at-most-K-of-this-group" no-good).
    - F2 cutset: AddBoolOr(NOT lit_i) (forbid full assignment).
    - F4 component_reach: AddBoolOr(NOT lit_i) (same shape; defensible as
      conjunction-of-presence forbidden).
    - F5 pattern_nogood: AddBoolOr(NOT lit_i) (canonical no-good form).
    - F6 shape_packing_hall: AddLinearConstraint(sum(lits) <= K).
    - F7 power_hitting_set: AddBoolOr(NOT lit_i).
    - F8 power_grid_reach: AddBoolOr(NOT lit_i).
    - F9 density_envelope: AddLinearConstraint(sum(lits) <= K).
    - F3 port_exposure: AddBoolOr(NOT facility, NOT blocker) two-literal no-good.

    Skipped: cert with 0 resolvable literal (after fallback).
    """
    t0 = time.monotonic()
    n_applied = 0
    n_skipped = 0
    n_constraints = 0
    n_pairs_total = 0
    n_pairs_remapped = 0
    per_family_app: Dict[str, int] = defaultdict(int)
    per_family_skip: Dict[str, int] = defaultdict(int)
    per_family_remap: Dict[str, int] = defaultdict(int)

    nogood_families = {
        "cutset",
        "component_reach",
        "pattern_nogood",
        "power_hitting_set",
        "power_grid_reach",
        "port_exposure",
    }
    linear_families = {
        "region_capacity",
        "shape_packing_hall",
        "density_envelope",
    }

    fallback_pool = registry.poses  # full prod pool for deterministic fallback

    for rec in cert_records:
        fam = rec.get("family", "")
        pairs = _cert_literal_pairs(rec, fallback_pool)
        # Resolve to BoolVars in registry. Unknown poses fall back to a global
        # deterministic substitute (per-cert seeded pick) to keep cert count
        # honest in sizing.
        lits: List[cp_model.IntVar] = []
        for fp in pairs:
            n_pairs_total += 1
            idx = registry.idx_by_facility_pose.get(fp)
            if idx is None:
                # Unknown (facility_type, pose_id): 不在真 registry。保留 deterministic
                # substitute 让 100K sizing 仍能跑, 但记成 remap, 让 telemetry 暴露多少
                # literal 没绑到真 registry (GPT 第九审: 静默 remap 让 applied 计数误导)。
                n_pairs_remapped += 1
                per_family_remap[fam] += 1
                h = _stable_hash(f"{rec.get('cut_id', '')}\x00{fp[0]}\x00{fp[1]}") & 0xFFFFFFFF
                idx = h % registry.n_vars
            lits.append(registry.var_by_idx[idx])

        if not lits:
            n_skipped += 1
            per_family_skip[fam] += 1
            continue

        if fam in nogood_families:
            # Forbid full conjunction: at least one literal must be 0.
            # CP-SAT idiom: model.AddBoolOr([v.Not() for v in lits]).
            model.AddBoolOr([v.Not() for v in lits])
            n_constraints += 1
        elif fam in linear_families:
            # sum(lits) <= len-1, i.e. at most |lits|-1 of them on.
            k = max(0, len(lits) - 1)
            model.Add(sum(lits) <= k)
            n_constraints += 1
        else:
            # Unknown family — skip; report.
            n_skipped += 1
            per_family_skip[fam] += 1
            continue

        n_applied += 1
        per_family_app[fam] += 1

    return TranslationReport(
        n_certs_in=len(cert_records),
        n_certs_applied=n_applied,
        n_certs_skipped=n_skipped,
        n_constraints_added=n_constraints,
        per_family_applied=dict(per_family_app),
        per_family_skipped=dict(per_family_skip),
        translation_wall_s=time.monotonic() - t0,
        n_pairs_total=n_pairs_total,
        n_pairs_remapped=n_pairs_remapped,
        per_family_remapped=dict(per_family_remap),
    )


# ============================================================================
# Self-test (B1 commit verify): build + apply 0 cert
# ============================================================================


if __name__ == "__main__":
    reg = load_pose_registry()
    print(f"PoseRegistry loaded: {reg.n_poses} poses")
    print("Pool distribution:")
    pool_counts: Dict[str, int] = defaultdict(int)
    for ft, _ in reg.poses:
        pool_counts[ft] += 1
    for ft, n in sorted(pool_counts.items()):
        print(f"  {ft}: {n}")

    print("\nBuilding toy master (no cuts) ...")
    model, rpt = build_toy_master(reg, add_demand_constraints=True)
    print(f"  n_vars             = {rpt.n_vars}")
    print(f"  n_demand_constraints = {rpt.n_demand_constraints}")
    print(f"  build_wall         = {rpt.build_wall_s:.3f}s")
    print(f"  proto_bytesize     = {rpt.proto_bytesize}")

    # Sanity: smoke parse 5 cert from fixture if exists
    fixture = REPO_ROOT / "data" / "cuts" / "spike" / "oracle_emit_fixture_45cert.jsonl"
    if fixture.exists():
        cert_records = []
        with fixture.open() as f:
            for line in f:
                rec = json.loads(line)
                cert_records.append(rec)
                if len(cert_records) >= 5:
                    break
        print("\nTranslating 5 sample certs ...")
        tr = translate_certs_to_constraints(model, reg, cert_records)
        print(f"  n_certs_in         = {tr.n_certs_in}")
        print(f"  n_certs_applied    = {tr.n_certs_applied}")
        print(f"  n_constraints_added= {tr.n_constraints_added}")
        print(f"  per_family_applied = {tr.per_family_applied}")
        print(f"  translation_wall   = {tr.translation_wall_s:.3f}s")
