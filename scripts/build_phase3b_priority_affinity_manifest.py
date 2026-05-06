from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_phase3b_s3_lite_baseline_scorecard import build_sensitive_path_audit
from scripts.run_phase3b_local_tuning_profile import ARTIFACT_ROOT
from src.runtime.cpu_topology import (
    affinity_mask_hex,
    build_cpu_topology_snapshot,
    disjoint_process_groups,
    reserve_highest_logical_ids,
)
from src.search.exact_campaign import atomic_write_json, now_iso

DEFAULT_BASELINE_SCORECARD = ARTIFACT_ROOT / "03_baseline_reproduction" / "baseline_scorecard.json"
DEFAULT_CONFIG_MATRIX_MANIFEST = ARTIFACT_ROOT / "04_config_matrix" / "matrix_manifest.json"
DEFAULT_STAGE_WORKER_MANIFEST = ARTIFACT_ROOT / "05_stage_workers" / "stage_worker_manifest.json"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "06_priority_affinity"
LOCAL_TUNING_NAMESPACE = "phase3b_local_13900ks_tuning_20260430"

VARIANT_KINDS = (
    "normal_unpinned",
    "high_unpinned",
    "reserve_2_logical_ids",
    "reserve_4_logical_ids",
    "disjoint_process_groups",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Phase3B S7 priority/affinity manifest without executing runs."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--baseline-scorecard", type=Path, default=DEFAULT_BASELINE_SCORECARD)
    parser.add_argument("--config-matrix-manifest", type=Path, default=DEFAULT_CONFIG_MATRIX_MANIFEST)
    parser.add_argument("--stage-worker-manifest", type=Path, default=DEFAULT_STAGE_WORKER_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    manifest = build_priority_affinity_manifest(
        project_root=project_root,
        baseline_scorecard_path=_resolve_path(project_root, Path(args.baseline_scorecard)),
        config_matrix_manifest_path=_resolve_path(project_root, Path(args.config_matrix_manifest)),
        stage_worker_manifest_path=_resolve_path(project_root, Path(args.stage_worker_manifest)),
    )
    print("phase3b priority/affinity manifest")
    print(f"base_profile_count={len(manifest['base_profiles'])}")
    print(f"variant_count={len(manifest['variants'])}")
    print(f"pe_mapping_confidence={manifest['topology']['pe_mapping']['confidence']}")
    print(f"execution_status={manifest['execution']['status']}")
    print(f"proof_source={manifest['safety']['proof_source']}")
    if not args.no_write:
        paths = write_priority_affinity_manifest(
            manifest,
            _resolve_path(project_root, Path(args.output_dir)),
        )
        print(f"affinity_priority_manifest_json={_display_path(project_root, Path(paths['json']))}")
        print(f"affinity_priority_manifest_md={_display_path(project_root, Path(paths['md']))}")
    return 0


def build_priority_affinity_manifest(
    *,
    project_root: Path,
    baseline_scorecard_path: Path,
    config_matrix_manifest_path: Path,
    stage_worker_manifest_path: Path,
    topology_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    baseline_scorecard = _load_json(baseline_scorecard_path)
    config_manifest = _load_optional_json(config_matrix_manifest_path)
    stage_manifest = _load_optional_json(stage_worker_manifest_path)
    topology = dict(topology_snapshot) if isinstance(topology_snapshot, Mapping) else build_cpu_topology_snapshot(project_root)
    base_profiles = _select_base_profiles(
        baseline_scorecard=baseline_scorecard,
        config_manifest=config_manifest,
        stage_manifest=stage_manifest,
    )
    variants: list[dict[str, Any]] = []
    for profile in base_profiles:
        for variant_kind in VARIANT_KINDS:
            variants.append(_variant_entry(profile, variant_kind, topology))
    return {
        "schema": "phase3b-priority-affinity-manifest/v0",
        "generated_at": now_iso(),
        "matrix_kind": "s7_priority_affinity_manifest",
        "execution": {
            "status": "not_executed_manifest_only",
            "fresh_solver_campaign_executed": False,
            "checkpoint_write_authorized": False,
            "true_priority_affinity_runs_blocked": True,
            "blocked_reason": (
                "Priority and affinity variants are prepared, but execution remains blocked "
                "until an isolated checkpoint-write authorization or checkpoint-free evaluator exists."
            ),
        },
        "source_artifacts": {
            "baseline_scorecard": _source_summary(baseline_scorecard_path),
            "config_matrix_manifest": _source_summary(config_matrix_manifest_path),
            "stage_worker_manifest": _source_summary(stage_worker_manifest_path),
        },
        "topology": topology,
        "base_profiles": base_profiles,
        "variants": variants,
        "eligibility_rules": {
            "pe_mapping_required_for_affinity_medium_confirmation": True,
            "unverified_pe_mapping_demotes_affinity_to_exploratory": True,
            "manifest_only_profiles_require_actual_nonfinal_run_before_medium_confirmation": True,
        },
        "readiness": {
            "recommended_first_variants_when_authorized": [
                "B0_prod_4x4__normal_unpinned",
                "B0_prod_4x4__high_unpinned",
                "W0_prod_4x4_stage_4_4_4_4__normal_unpinned",
                "W1_stage_4x_master6_local4_binding2_routing4__normal_unpinned",
            ],
            "affinity_variants_can_enter_medium_confirmation": _pe_mapping_confidence(topology) != "unverified",
            "priority_only_variants_can_enter_medium_confirmation": False,
        },
        "sensitive_path_audit": build_sensitive_path_audit(project_root),
        "safety": {
            "manifest_only": True,
            "proof_source": False,
            "production_profile_changed": False,
            "prod_4x4_normal_default_changed": False,
            "final_168h_started": False,
            "production_long_run_started": False,
            "checkpoint_written": False,
            "checkpoint_imported_back": False,
            "runtime_elimination_enabled": False,
            "proof_source_mutated": False,
            "release_viewer_frontdoor_promoted": False,
        },
    }


def write_priority_affinity_manifest(manifest: Mapping[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir = Path(output_dir)
    _assert_output_namespace(output_dir, LOCAL_TUNING_NAMESPACE)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "affinity_priority_manifest.json"
    md_path = output_dir / "affinity_priority_manifest.md"
    atomic_write_json(json_path, dict(manifest))
    _atomic_write_text(md_path, render_priority_affinity_manifest_markdown(manifest))
    return {"json": str(json_path), "md": str(md_path)}


def render_priority_affinity_manifest_markdown(manifest: Mapping[str, Any]) -> str:
    topology = _mapping(manifest.get("topology"))
    pe_mapping = _mapping(topology.get("pe_mapping"))
    cpu = _mapping(topology.get("cpu"))
    execution = _mapping(manifest.get("execution"))
    lines = [
        "# Phase3B S7 Priority/Affinity Manifest",
        "",
        f"- Execution status: `{execution.get('status')}`",
        f"- Proof source: `{_mapping(manifest.get('safety')).get('proof_source')}`",
        f"- Logical processors: `{cpu.get('logical_processor_count')}`",
        f"- Physical cores: `{cpu.get('physical_core_count')}`",
        f"- P/E mapping confidence: `{pe_mapping.get('confidence')}`",
        f"- Affinity medium-confirmation eligible: `{_mapping(manifest.get('readiness')).get('affinity_variants_can_enter_medium_confirmation')}`",
        "",
        "| Variant | Base Profile | Priority | Affinity | Risk | Medium Confirmation Status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for variant in manifest.get("variants", []) or []:
        if not isinstance(variant, Mapping):
            continue
        risk = _mapping(variant.get("risk"))
        affinity = _mapping(variant.get("affinity"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(variant.get("variant_id")),
                    _markdown_cell(variant.get("base_profile_id")),
                    _markdown_cell(variant.get("process_priority")),
                    _markdown_cell(affinity.get("policy")),
                    _markdown_cell(risk.get("level")),
                    _markdown_cell(variant.get("medium_confirmation_status")),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _select_base_profiles(
    *,
    baseline_scorecard: Mapping[str, Any],
    config_manifest: Mapping[str, Any] | None,
    stage_manifest: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    config_by_id = _profiles_by_id(config_manifest)
    stage_by_id = _profiles_by_id(stage_manifest)
    for profile_id in _recommended_ids(config_manifest):
        profile = config_by_id.get(profile_id)
        if profile is not None:
            selected.append(_base_profile_entry(profile, source_kind="s5_config_manifest"))
    for profile_id in _recommended_ids(stage_manifest):
        profile = stage_by_id.get(profile_id)
        if profile is not None:
            selected.append(_base_profile_entry(profile, source_kind="s6_stage_worker_manifest"))
    if not selected:
        baseline_profile = _baseline_profile(baseline_scorecard)
        selected.append(
            {
                "profile_id": str(baseline_profile.get("profile_id") or "prod_4x4"),
                "source_kind": "s3_baseline_scorecard",
                "process_count": _int_or_none(baseline_profile.get("process_count")) or 4,
                "env": {"EXACT_CP_SAT_WORKERS": str(baseline_profile.get("worker_count_per_process") or 4)},
                "risk": {"level": "low", "reasons": []},
                "execution_status": "evidence_replay_only",
            }
        )
    deduped: dict[str, dict[str, Any]] = {}
    for profile in selected:
        deduped.setdefault(str(profile.get("profile_id")), profile)
    return list(deduped.values())


def _base_profile_entry(profile: Mapping[str, Any], *, source_kind: str) -> dict[str, Any]:
    return {
        "profile_id": str(profile.get("profile_id")),
        "source_kind": source_kind,
        "process_count": _int_or_none(profile.get("process_count")) or 1,
        "env": dict(_mapping(profile.get("env"))),
        "risk": dict(_mapping(profile.get("risk"))),
        "execution_status": str(profile.get("execution_status") or "not_executed_manifest_only"),
    }


def _variant_entry(
    profile: Mapping[str, Any],
    variant_kind: str,
    topology: Mapping[str, Any],
) -> dict[str, Any]:
    process_count = _int_or_none(profile.get("process_count")) or 1
    logical_ids = _logical_ids(topology)
    priority = "high" if variant_kind == "high_unpinned" else "normal"
    affinity = _affinity_payload(
        variant_kind=variant_kind,
        logical_ids=logical_ids,
        process_count=process_count,
        pe_mapping_confidence=_pe_mapping_confidence(topology),
    )
    risk = _variant_risk(profile, variant_kind, affinity)
    medium_status = (
        "blocked_until_pe_mapping_verified"
        if affinity.get("requires_trusted_pe_mapping_for_medium_confirmation")
        else "requires_actual_nonfinal_s7_execution"
    )
    return {
        "variant_id": f"{profile.get('profile_id')}__{variant_kind}",
        "base_profile_id": str(profile.get("profile_id")),
        "source_kind": str(profile.get("source_kind")),
        "variant_kind": variant_kind,
        "process_count": process_count,
        "env": dict(_mapping(profile.get("env"))),
        "process_priority": priority,
        "affinity": affinity,
        "risk": risk,
        "execution_status": "not_executed_manifest_only",
        "proof_source": False,
        "medium_confirmation_status": medium_status,
        "candidate_command_template": [
            "python",
            "scripts/run_phase3b_local_tuning_profile.py",
            "--profile",
            str(profile.get("profile_id")),
            "--requires-future-affinity-runner-support",
        ],
    }


def _affinity_payload(
    *,
    variant_kind: str,
    logical_ids: list[int],
    process_count: int,
    pe_mapping_confidence: str,
) -> dict[str, Any]:
    if variant_kind in {"normal_unpinned", "high_unpinned"}:
        return {
            "policy": "unpinned",
            "allowed_logical_ids": logical_ids,
            "allowed_affinity_mask_hex": affinity_mask_hex(logical_ids),
            "reserved_logical_ids": [],
            "per_process_groups": [],
            "pe_mapping_confidence": pe_mapping_confidence,
            "requires_trusted_pe_mapping_for_medium_confirmation": False,
        }
    if variant_kind == "reserve_2_logical_ids":
        payload = reserve_highest_logical_ids(logical_ids, 2)
        payload.update(
            {
                "policy": "reserve_2_logical_ids",
                "per_process_groups": [],
                "pe_mapping_confidence": pe_mapping_confidence,
                "requires_trusted_pe_mapping_for_medium_confirmation": pe_mapping_confidence == "unverified",
            }
        )
        return payload
    if variant_kind == "reserve_4_logical_ids":
        payload = reserve_highest_logical_ids(logical_ids, 4)
        payload.update(
            {
                "policy": "reserve_4_logical_ids",
                "per_process_groups": [],
                "pe_mapping_confidence": pe_mapping_confidence,
                "requires_trusted_pe_mapping_for_medium_confirmation": pe_mapping_confidence == "unverified",
            }
        )
        return payload
    groups = disjoint_process_groups(logical_ids, process_count)
    return {
        "policy": "disjoint_process_groups",
        "allowed_logical_ids": logical_ids,
        "allowed_affinity_mask_hex": affinity_mask_hex(logical_ids),
        "reserved_logical_ids": [],
        "per_process_groups": groups,
        "pe_mapping_confidence": pe_mapping_confidence,
        "requires_trusted_pe_mapping_for_medium_confirmation": pe_mapping_confidence == "unverified",
    }


def _variant_risk(
    profile: Mapping[str, Any],
    variant_kind: str,
    affinity: Mapping[str, Any],
) -> dict[str, Any]:
    inherited = str(_mapping(profile.get("risk")).get("level") or "low")
    reasons = list(_mapping(profile.get("risk")).get("reasons") or [])
    level = inherited if inherited in {"low", "medium", "high"} else "low"
    if variant_kind == "high_unpinned":
        level = _max_risk(level, "medium")
        reasons.append("high_priority_exploratory")
    if affinity.get("requires_trusted_pe_mapping_for_medium_confirmation"):
        level = _max_risk(level, "medium")
        reasons.append("pe_mapping_unverified")
    if variant_kind == "disjoint_process_groups":
        level = _max_risk(level, "medium")
        reasons.append("per_process_affinity_complexity")
    return {"level": level, "reasons": sorted(set(str(reason) for reason in reasons))}


def _logical_ids(topology: Mapping[str, Any]) -> list[int]:
    cpu = _mapping(topology.get("cpu"))
    processors = cpu.get("logical_processors")
    if isinstance(processors, list):
        ids = [
            _int_or_none(_mapping(item).get("logical_id"))
            for item in processors
            if isinstance(item, Mapping)
        ]
        result = sorted({int(value) for value in ids if value is not None})
        if result:
            return result
    logical_count = _int_or_none(cpu.get("logical_processor_count")) or 0
    return list(range(logical_count))


def _pe_mapping_confidence(topology: Mapping[str, Any]) -> str:
    return str(_mapping(topology.get("pe_mapping")).get("confidence") or "unverified")


def _profiles_by_id(manifest: Mapping[str, Any] | None) -> dict[str, Mapping[str, Any]]:
    if not isinstance(manifest, Mapping):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    for profile in manifest.get("profiles", []) or []:
        if isinstance(profile, Mapping) and profile.get("profile_id"):
            result[str(profile.get("profile_id"))] = profile
    return result


def _recommended_ids(manifest: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(manifest, Mapping):
        return []
    readiness = _mapping(manifest.get("readiness"))
    ids = readiness.get("recommended_first_profiles_when_authorized")
    if isinstance(ids, list):
        return [str(value) for value in ids]
    return [
        str(_mapping(profile).get("profile_id"))
        for profile in list(manifest.get("profiles", []) or [])[:4]
        if isinstance(profile, Mapping) and _mapping(profile).get("profile_id")
    ]


def _baseline_profile(scorecard: Mapping[str, Any]) -> Mapping[str, Any]:
    requested = str(_mapping(scorecard.get("baseline")).get("profile_id") or "prod_4x4")
    for profile in scorecard.get("profiles", []) or []:
        if isinstance(profile, Mapping) and str(profile.get("profile_id")) == requested:
            return profile
    profiles = [profile for profile in scorecard.get("profiles", []) or [] if isinstance(profile, Mapping)]
    return profiles[0] if profiles else {}


def _source_summary(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {"path": str(path), "exists": False, "size_bytes": None}
    return {"path": str(path), "exists": True, "size_bytes": int(path.stat().st_size)}


def _load_json(path: Path) -> Mapping[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _load_optional_json(path: Path) -> Mapping[str, Any] | None:
    if not Path(path).exists():
        return None
    return _load_json(path)


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _assert_output_namespace(output_dir: Path, namespace: str) -> None:
    parts = set(Path(output_dir).parts)
    if ".artifacts" not in parts or namespace not in parts:
        raise ValueError(f"output_dir must be under .artifacts/{namespace}: {output_dir}")


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _max_risk(left: str, right: str) -> str:
    order = {"low": 0, "medium": 1, "high": 2}
    return left if order[left] >= order[right] else right


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


if __name__ == "__main__":
    raise SystemExit(main())
