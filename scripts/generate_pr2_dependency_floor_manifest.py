"""Generate the PR2 L0 third-party dependency floor manifest for this host.

This manifest is generated from a reviewed dependency environment.  File entries
are relative to the active sysconfig purelib root so identical wheel bytes can be
reviewed without pinning one machine's absolute install prefix.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
import textwrap
from typing import Iterable

AUTHORITY = "pr2_l0_dependency_floor_manifest_v1"
DEFAULT_OUTPUT = Path("data/proof_obligations/pr2_dependency_floor_manifest.json")
FLOOR_ROOT_SENTINEL = "PYTHON_SYSCONFIG_PURELIB"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROBE_IMPORTS = (
    "absl",
    "absl.flags",
    "google.protobuf",
    "jsonschema",
    "src.search.pr2_l0_true_verifier_child",
    "src.search.terminal_fixed_witness_verifier",
    "src.search.terminal_fixed_witness_capsule",
    "src.models.binding_subproblem",
    "src.models.routing_subproblem",
    "src.models.master_model",
    "src.models.exact_coordinate_master",
    "src.models.flow_subproblem",
    "ortools.sat.python.cp_model",
    "ortools.linear_solver.pywraplp",
    "ortools.graph.python.min_cost_flow",
)
BASE_DISTRIBUTIONS = ("ortools", "protobuf", "absl-py")
IMPORT_FILE_SUFFIXES = (
    ".py",
    ".pyi",
    ".pyd",
    ".dll",
    ".so",
    ".dylib",
)


def _site_roots() -> list[Path]:
    roots: list[Path] = []
    for key in ("purelib", "platlib"):
        raw = sysconfig.get_paths().get(key)
        if not raw:
            continue
        path = Path(raw).resolve()
        if path.exists() and path not in roots:
            roots.append(path)
    if not roots:
        raise RuntimeError("no site-package floor root found")
    return roots


def _probe_source(project_root: Path, site_roots: Iterable[Path]) -> str:
    imports_json = json.dumps(list(PROBE_IMPORTS))
    site_json = json.dumps([str(path) for path in site_roots])
    return textwrap.dedent(
        f"""
        import importlib, json, pathlib, sys

        project = pathlib.Path({str(project_root)!r}).resolve()
        site_roots = [pathlib.Path(raw).resolve() for raw in json.loads({site_json!r})]
        sys.path.insert(0, str(project))
        for root in reversed(site_roots):
            sys.path.insert(1, str(root))

        errors = {{}}
        for name in json.loads({imports_json!r}):
            try:
                importlib.import_module(name)
            except Exception as exc:
                errors[name] = type(exc).__name__ + ":" + str(exc)

        try:
            from ortools.sat.python import cp_model
            model = cp_model.CpModel()
            x = model.NewIntVar(0, 1, "x")
            model.Maximize(x)
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 0.1
            solver.Solve(model)
        except Exception as exc:
            errors["cp_sat_smoke"] = type(exc).__name__ + ":" + str(exc)

        try:
            from ortools.linear_solver import pywraplp
            solver = pywraplp.Solver.CreateSolver("SCIP") or pywraplp.Solver.CreateSolver("GLOP")
            if solver is not None:
                y = solver.NumVar(0, 1, "y")
                solver.Maximize(y)
                solver.Solve()
        except Exception as exc:
            errors["linear_solver_smoke"] = type(exc).__name__ + ":" + str(exc)

        loaded = {{}}
        for name, module in sorted(sys.modules.items()):
            raw_file = getattr(module, "__file__", None)
            if not raw_file:
                continue
            try:
                file_path = pathlib.Path(raw_file).resolve()
            except Exception:
                continue
            for root in site_roots:
                try:
                    rel = file_path.relative_to(root).as_posix()
                except ValueError:
                    continue
                loaded[name] = rel
                break
        print(json.dumps({{"errors": errors, "loaded": loaded}}, sort_keys=True))
        """
    )


def _run_import_probe(project_root: Path, site_roots: Iterable[Path]) -> dict[str, object]:
    completed = subprocess.run(
        [
            str(Path(os.path.abspath(sys.executable))),
            "-I",
            "-S",
            "-B",
            "-c",
            _probe_source(project_root, site_roots),
        ],
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
        cwd=str(project_root),
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "dependency floor import probe failed:"
            f" rc={completed.returncode} stderr={completed.stderr[-1000:]}"
        )
    payload = json.loads(completed.stdout)
    errors = payload.get("errors")
    if errors:
        raise RuntimeError(f"dependency floor import probe errors: {errors}")
    return payload


def _loaded_top_level(loaded: dict[str, str]) -> set[str]:
    return {
        name.split(".", 1)[0]
        for name in loaded
        if name and name.split(".", 1)[0].isidentifier()
    }


def _rel_top_level(rel: str) -> str | None:
    first = rel.split("/", 1)[0]
    path = Path(first)
    if path.suffix in IMPORT_FILE_SUFFIXES and path.stem.isidentifier():
        return path.stem
    if first.isidentifier():
        return first
    return None


def _top_level_roots(site_root: Path, loaded: dict[str, str]) -> tuple[set[Path], set[str]]:
    roots: set[Path] = set()
    path_tops: set[str] = set()
    for rel in loaded.values():
        first = rel.split("/", 1)[0]
        top = _rel_top_level(rel)
        if top is not None:
            path_tops.add(top)
        candidate = (site_root / first).resolve()
        if candidate.is_file():
            roots.add(candidate)
        elif candidate.is_dir() and (first.isidentifier() or first.endswith(".libs")):
            roots.add(candidate)
            libs = candidate.with_name(f"{candidate.name}.libs")
            if libs.is_dir():
                roots.add(libs.resolve())
    return roots, path_tops


def _distribution_roots(names: Iterable[str]) -> list[Path]:
    roots: list[Path] = []
    for name in sorted(set(names)):
        dist = importlib.metadata.distribution(name)
        roots.append(Path(str(dist._path)).resolve())  # noqa: SLF001
    return roots


def _distribution_names(top_level_names: Iterable[str]) -> set[str]:
    packages_to_distributions = importlib.metadata.packages_distributions()
    names = set(BASE_DISTRIBUTIONS)
    for top_level in top_level_names:
        names.update(packages_to_distributions.get(top_level, ()))
    return names


def _iter_files(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        if root.is_file():
            if "__pycache__" not in root.parts:
                yield root.resolve()
            continue
        for path in root.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                yield path.resolve()


def build_manifest() -> dict[str, object]:
    site_roots = _site_roots()
    if len(site_roots) != 1:
        raise RuntimeError(f"expected one dependency floor root, got: {site_roots}")
    floor_root = site_roots[0]
    probe = _run_import_probe(PROJECT_ROOT, site_roots)
    loaded_raw = probe.get("loaded")
    if not isinstance(loaded_raw, dict) or not loaded_raw:
        raise RuntimeError("dependency floor import probe loaded no third-party modules")
    loaded = {str(key): str(value) for key, value in loaded_raw.items()}
    package_roots, path_top_level = _top_level_roots(floor_root, loaded)
    allowed_top_level = sorted(_loaded_top_level(loaded) | path_top_level)
    dist_roots = _distribution_roots(_distribution_names(allowed_top_level))
    roots = [*sorted(package_roots), *dist_roots]
    files: dict[str, dict[str, object]] = {}
    for path in sorted(set(_iter_files(roots))):
        rel = path.relative_to(floor_root).as_posix()
        raw = path.read_bytes()
        files[rel] = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size": len(raw),
        }
    return {
        "schema_version": 1,
        "authority": AUTHORITY,
        "floor_root": FLOOR_ROOT_SENTINEL,
        "allowed_top_level": allowed_top_level,
        "files": files,
        "named_tcb": {
            "python_interpreter": "NAMED-TCB",
            "stdlib": "NAMED-TCB",
            "third_party_closure": {name: "NAMED-TCB" for name in allowed_top_level},
            "third_party_distribution_metadata": {
                path.name: "NAMED-TCB" for path in sorted(dist_roots)
            },
            "third_party_native_semantics": "NAMED-TCB",
            "os_loader_c_runtime_kernel_cpu": "NAMED-TCB",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = build_manifest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False))
        handle.write("\n")
    print(args.output)
    print(hashlib.sha256(args.output.read_bytes()).hexdigest().upper())
    print("allowed_top_level=" + ",".join(manifest["allowed_top_level"]))  # type: ignore[index]
    print(f"files={len(manifest['files'])}")  # type: ignore[index]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
