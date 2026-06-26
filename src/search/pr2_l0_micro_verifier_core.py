"""PR2-a stdlib-only L0 skeleton: snapshot bytes, spawn child, return SEALED/REJECTED."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Mapping, Sequence

SEALED = "SEALED"
REJECTED = "REJECTED"
AUTHORITY = "pr2_l0_micro_verifier_v1"
SCHEMA_VERSION = 1
DEFAULT_VERIFIER_MODULE = "src.search.pr2_l0_trivial_child"
DEFAULT_VERIFIER_FUNCTION = "verify"
CHILD_STAGE_TRACE = (
    "floor_verified",
    "loader_installed",
    "verifier_imported",
    "verifier_ran",
)


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate JSON key: {key}")
        payload[key] = value
    return payload


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _parse_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite JSON number: {value}")
    return parsed


def loads_l0_strict_json(text: str) -> Any:
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=_reject_json_constant,
        parse_float=_parse_json_float,
    )


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


@dataclass(frozen=True)
class L0MicroVerdict:
    status: str
    nonce: str
    reason: str
    floor_digest: str | None = None
    response: Mapping[str, Any] = field(default_factory=dict)


def run_l0_micro_verifier_round_trip(
    payload: Mapping[str, Any] | None = None,
    *,
    timeout_seconds: float = 10.0,
    verifier_module: str = DEFAULT_VERIFIER_MODULE,
    verifier_function: str = DEFAULT_VERIFIER_FUNCTION,
    extra_snapshot_modules: Sequence[str] = (),
    omit_snapshot_modules: Sequence[str] = (),
    poison_sys_path: Path | str | None = None,
) -> L0MicroVerdict:
    nonce = secrets.token_hex(32)
    source_root = Path(__file__).resolve().parents[2]
    modules = _snapshot_module_paths(
        source_root=source_root,
        verifier_module=verifier_module,
        extra_snapshot_modules=extra_snapshot_modules,
        omit_snapshot_modules=frozenset(omit_snapshot_modules),
    )
    pycache_prefix = tempfile.mkdtemp(prefix="zmd_pr2_l0_pycache_")
    try:
        with tempfile.TemporaryDirectory(prefix="zmd_pr2_l0_snapshot_") as temp_dir:
            snapshot_root = Path(temp_dir) / "snapshot"
            manifest = _materialize_snapshot(snapshot_root, modules)
            floor_digest = _floor_digest(manifest)
            request = {
                "schema_version": SCHEMA_VERSION,
                "authority": AUTHORITY,
                "nonce": nonce,
                "snapshot_root": str(snapshot_root),
                "manifest": manifest,
                "floor_digest": floor_digest,
                "verifier_module": verifier_module,
                "verifier_function": verifier_function,
                "payload": dict(payload or {}),
                "poison_sys_path": ([] if poison_sys_path is None else [str(poison_sys_path)]),
            }
            try:
                completed = subprocess.run(
                    [
                        str(Path(os.path.abspath(sys.executable))),
                        "-I",
                        "-B",
                        "-X",
                        f"pycache_prefix={pycache_prefix}",
                        "-c",
                        CHILD_BOOTSTRAP_SOURCE,
                    ],
                    input=_json_bytes(request).decode("utf-8"),
                    text=True,
                    capture_output=True,
                    env=_child_env(),
                    cwd=str(snapshot_root),
                    timeout=float(timeout_seconds),
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return _reject(nonce, "child_timeout", floor_digest=floor_digest)
            return _verdict_from_completed_process(
                completed=completed,
                nonce=nonce,
                floor_digest=floor_digest,
            )
    except Exception as exc:  # noqa: BLE001
        return _reject(nonce, f"parent_exception:{type(exc).__name__}")
    finally:
        shutil.rmtree(pycache_prefix, ignore_errors=True)


def _snapshot_module_paths(
    *,
    source_root: Path,
    verifier_module: str,
    extra_snapshot_modules: Sequence[str],
    omit_snapshot_modules: frozenset[str],
) -> dict[str, Path]:
    names = [__name__, verifier_module, *extra_snapshot_modules]
    paths: dict[str, Path] = {}
    for module in names:
        if module in omit_snapshot_modules:
            continue
        rel_path = _module_relpath(module)
        path = (source_root / rel_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"snapshot module missing: {module}")
        paths[module] = path
    return paths


def _module_relpath(module: str) -> Path:
    parts = module.split(".")
    if not parts or any(not part.isidentifier() for part in parts):
        raise ValueError(f"invalid module name: {module}")
    return Path(*parts).with_suffix(".py")


def _materialize_snapshot(snapshot_root: Path, modules: Mapping[str, Path]) -> dict[str, dict[str, str]]:
    manifest: dict[str, dict[str, str]] = {}
    for module, source_path in sorted(modules.items()):
        rel_path = _module_relpath(module)
        source_bytes = Path(source_path).read_bytes()
        target_path = snapshot_root / rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(source_bytes)
        manifest[module] = {
            "path": rel_path.as_posix(),
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
        }
    return manifest


def _floor_digest(manifest: Mapping[str, Mapping[str, str]]) -> str:
    return hashlib.sha256(_json_bytes(manifest)).hexdigest()


def _child_env() -> dict[str, str]:
    return {"PATH": os.defpath, "PYTHONHASHSEED": "0", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}


def _verdict_from_completed_process(
    *,
    completed: subprocess.CompletedProcess[str],
    nonce: str,
    floor_digest: str,
) -> L0MicroVerdict:
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[-200:]
        return _reject(nonce, f"child_exit:{completed.returncode}:{detail}", floor_digest=floor_digest)
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        return _reject(nonce, "child_no_response", floor_digest=floor_digest)
    try:
        response = loads_l0_strict_json(lines[-1])
    except Exception as exc:  # noqa: BLE001
        return _reject(nonce, f"child_response_json:{type(exc).__name__}", floor_digest=floor_digest)
    violation = _response_violation(response, nonce=nonce, floor_digest=floor_digest)
    if violation is not None:
        return _reject(nonce, violation, floor_digest=floor_digest, response=response if isinstance(response, Mapping) else {})
    verdict = str(response["verdict"])
    reason = str(response["reason"])
    if verdict == SEALED:
        return L0MicroVerdict(
            status=SEALED,
            nonce=nonce,
            reason=reason,
            floor_digest=floor_digest,
            response=dict(response),
        )
    return _reject(nonce, reason, floor_digest=floor_digest, response=dict(response))


def _response_violation(response: Any, *, nonce: str, floor_digest: str) -> str | None:
    keys = {
        "schema_version",
        "authority",
        "nonce",
        "floor_digest",
        "verdict",
        "reason",
        "stage_trace",
        "verifier_module",
    }
    if not isinstance(response, Mapping) or set(response.keys()) != keys:
        return "response_shape_invalid"
    if response["schema_version"] != SCHEMA_VERSION:
        return "response_schema_invalid"
    if response["authority"] != AUTHORITY:
        return "response_authority_invalid"
    if response["nonce"] != nonce:
        return "response_nonce_mismatch"
    if response["floor_digest"] != floor_digest:
        return "response_floor_digest_mismatch"
    if response["verdict"] not in {SEALED, REJECTED}:
        return "response_verdict_invalid"
    if not isinstance(response["reason"], str):
        return "response_reason_invalid"
    if not isinstance(response["verifier_module"], str):
        return "response_verifier_invalid"
    trace = response["stage_trace"]
    if not isinstance(trace, list) or any(not isinstance(item, str) for item in trace):
        return "response_stage_trace_invalid"
    if response["verdict"] == SEALED and tuple(trace) != CHILD_STAGE_TRACE:
        return "response_stage_trace_incomplete"
    return None


def _reject(
    nonce: str,
    reason: str,
    *,
    floor_digest: str | None = None,
    response: Mapping[str, Any] | None = None,
) -> L0MicroVerdict:
    return L0MicroVerdict(
        status=REJECTED,
        nonce=nonce,
        reason=str(reason),
        floor_digest=floor_digest,
        response=dict(response or {}),
    )


CHILD_BOOTSTRAP_SOURCE = r'''
import hashlib, importlib, importlib.machinery, importlib.util, json, math, os, sys, time
SEALED = "SEALED"
REJECTED = "REJECTED"
AUTHORITY = "pr2_l0_micro_verifier_v1"
SCHEMA_VERSION = 1

def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key:" + str(key))
        out[key] = value
    return out

def _bad_constant(value):
    raise ValueError("invalid JSON constant:" + str(value))

def _float(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite JSON number:" + str(value))
    return parsed

def _loads(text):
    return json.loads(text, object_pairs_hook=_pairs, parse_constant=_bad_constant, parse_float=_float)

def _dumps(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)

def _safe_path(root, rel):
    if os.path.isabs(rel) or rel in {"", ".."} or rel.startswith("../") or "/../" in rel:
        raise ValueError("snapshot path escapes root")
    path = os.path.realpath(os.path.join(root, *rel.split("/")))
    if os.path.commonpath([root, path]) != root:
        raise ValueError("snapshot path escapes root")
    return path

def _floor_digest(manifest):
    return hashlib.sha256(_dumps(manifest).encode("utf-8")).hexdigest()

class _SnapshotLoader:
    def __init__(self, path, digest):
        self.path = path
        self.digest = digest
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        source = open(self.path, "rb").read()
        if hashlib.sha256(source).hexdigest() != self.digest:
            raise ImportError("snapshot digest mismatch")
        exec(compile(source, self.path, "exec"), module.__dict__)

class _NamespaceLoader:
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        module.__path__ = []

class _SnapshotFinder:
    def __init__(self, root, manifest):
        self.root = root
        self.manifest = manifest
        self.packages = {".".join(name.split(".")[:i]) for name in manifest for i in range(1, len(name.split(".")))}
    def find_spec(self, fullname, path=None, target=None):
        entry = self.manifest.get(fullname)
        if entry is not None:
            origin = _safe_path(self.root, entry["path"])
            return importlib.util.spec_from_loader(fullname, _SnapshotLoader(origin, entry["sha256"]), origin=origin)
        if fullname in self.packages:
            spec = importlib.machinery.ModuleSpec(fullname, _NamespaceLoader(), is_package=True)
            spec.submodule_search_locations = []
            return spec
        return None

def _install_loader(root, manifest):
    sys.path[:] = []
    sys.meta_path[:] = [_SnapshotFinder(root, manifest), importlib.machinery.BuiltinImporter, importlib.machinery.FrozenImporter]

def _response(verdict, reason, nonce, floor, trace, verifier):
    print(_dumps({"schema_version": SCHEMA_VERSION, "authority": AUTHORITY, "nonce": nonce, "floor_digest": floor, "verdict": verdict, "reason": str(reason), "stage_trace": list(trace), "verifier_module": str(verifier)}))

def main():
    trace = []
    nonce = floor = verifier_module = ""
    try:
        request = _loads(sys.stdin.read())
        required = {"schema_version", "authority", "nonce", "snapshot_root", "manifest", "floor_digest", "verifier_module", "verifier_function", "payload", "poison_sys_path"}
        if set(request.keys()) != required:
            raise ValueError("request shape invalid")
        if request["schema_version"] != SCHEMA_VERSION or request["authority"] != AUTHORITY:
            raise ValueError("request authority invalid")
        nonce = str(request["nonce"])
        verifier_module = str(request["verifier_module"])
        root = os.path.realpath(str(request["snapshot_root"]))
        manifest = request["manifest"]
        if not isinstance(manifest, dict):
            raise ValueError("manifest invalid")
        for name, entry in manifest.items():
            if not isinstance(name, str) or not isinstance(entry, dict):
                raise ValueError("manifest entry invalid")
            if hashlib.sha256(open(_safe_path(root, str(entry["path"])), "rb").read()).hexdigest() != str(entry["sha256"]):
                raise ValueError("manifest digest mismatch")
        floor = _floor_digest(manifest)
        if floor != str(request["floor_digest"]):
            raise ValueError("floor digest mismatch")
        trace.append("floor_verified")
        for raw_path in request.get("poison_sys_path", []):
            sys.path.insert(0, str(raw_path))
        _install_loader(root, manifest)
        trace.append("loader_installed")
        verifier = importlib.import_module(verifier_module)
        trace.append("verifier_imported")
        result = getattr(verifier, str(request["verifier_function"]))({"nonce": nonce, "payload": request["payload"]})
        trace.append("verifier_ran")
        if not isinstance(result, dict) or result.get("verdict") not in {SEALED, REJECTED}:
            raise ValueError("verifier result invalid")
        _response(result["verdict"], result.get("reason", ""), result.get("nonce", nonce), floor, trace, verifier_module)
    except BaseException as exc:
        _response(REJECTED, type(exc).__name__ + ":" + str(exc), nonce, floor, trace, verifier_module)
    return 0

raise SystemExit(main())
'''
