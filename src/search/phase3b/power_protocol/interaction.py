from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.search.exact_campaign import now_iso

POWER_PROTOCOL_INTERACTION_SOURCE = (
    "phase3b_power_protocol_interaction_diagnostic_v1"
)
POWER_COVERAGE_ANCHOR_DELTA_SOURCE = "phase3b_power_coverage_anchor_delta_v1"
RESIDUAL_OPTIONAL_ENCODING_SOURCE = "phase3b_residual_optional_encoding_inventory_v1"
ZERO_BRANCH_UNKNOWN_TRIAGE_SOURCE = "phase3b_zero_branch_unknown_triage_v1"
FORCED_ANCHOR_MODEL_SLICE_SOURCE = "phase3b_forced_anchor_model_slice_diagnostic_v1"
FAMILY_BOUND_AUDIT_SOURCE = "phase3b_family_bound_audit_v1"
FAMILY_BOUND_SEMANTIC_AUDIT_SOURCE = "phase3b_family_bound_semantic_audit_v1"
FAMILY_BOUND_SOLVER_PROFILE_SOURCE = "phase3b_family_bound_solver_profile_v1"
FAMILY_BOUND_PARAMETER_PROBE_SOURCE = "phase3b_family_bound_parameter_probe_v1"
FAMILY_BOUND_FORMULATION_PROBE_SOURCE = "phase3b_family_bound_formulation_probe_v1"
FAMILY_LOOKUP_SEARCH_PROBE_SOURCE = "phase3b_family_lookup_search_probe_v1"
FAMILY_LOOKUP_ASSUMPTION_PROBE_SOURCE = "phase3b_family_lookup_assumption_probe_v1"
FAMILY_LOOKUP_SEMANTIC_REPRO_SOURCE = "phase3b_family_lookup_semantic_repro_v1"
FORCED_ANCHOR_PROTO_REDUCTION_SOURCE = "phase3b_forced_anchor_proto_reduction_v1"
POWER_COVERAGE_WITNESS_AUDIT_SOURCE = "phase3b_power_coverage_witness_audit_v1"
POWER_COVERAGE_WITNESS_DOMAIN_SOURCE = "phase3b_power_coverage_witness_domain_v1"
FAMILY_LOOKUP_ASSIGNMENT_AUDIT_SOURCE = "phase3b_family_lookup_assignment_audit_v1"
POWER_CAPACITY_GVI_AUDIT_SOURCE = "phase3b_power_capacity_gvi_audit_v1"

DEFAULT_POWER_COVERAGE_ANCHOR_DELTA_PATH = Path(
    ".artifacts/phase3b_power_coverage_anchor_delta/power_coverage_anchor_delta.json"
)
DEFAULT_RESIDUAL_OPTIONAL_ENCODING_PATH = Path(
    ".artifacts/phase3b_residual_optional_encoding_67x13_cap112_v3/"
    "residual_optional_encoding.json"
)
DEFAULT_ZERO_BRANCH_UNKNOWN_TRIAGE_PATH = Path(
    ".artifacts/phase3b_zero_branch_unknown_triage/zero_branch_unknown_triage.json"
)
DEFAULT_MODEL_SLICE_DIR = Path(".artifacts/phase3b_forced_anchor_model_slice_67x13_cap112_v3")
DEFAULT_MODEL_SLICE_DIRS = (
    DEFAULT_MODEL_SLICE_DIR,
    Path(".artifacts/phase3b_forced_anchor_model_slice_67x13_family009_protocol"),
    Path(".artifacts/phase3b_forced_anchor_model_slice_67x13_dynamic_coupling"),
    Path(".artifacts/phase3b_forced_anchor_model_slice_67x13_dynamic_family_gvi"),
    Path(".artifacts/phase3b_forced_anchor_model_slice_67x13_dynamic_family_sublayers"),
    Path(".artifacts/phase3b_forced_anchor_model_slice_67x13_dynamic_family_lookup_distance"),
    Path(".artifacts/phase3b_forced_anchor_model_slice_67x13_family_channeling"),
    Path(".artifacts/phase3b_forced_anchor_model_slice_67x13_dynamic_family_table_linear"),
    Path(".artifacts/phase3b_forced_anchor_model_slice_67x13_dynamic_family_linear_categories"),
    Path(".artifacts/phase3b_forced_anchor_model_slice_67x13_family_shell_pair_tables"),
    Path(".artifacts/phase3b_forced_anchor_model_slice_67x13_family_lookup_rebuild"),
    Path(".artifacts/phase3b_forced_anchor_model_slice_67x13_family_lookup_rebuild_components"),
)
DEFAULT_FAMILY_BOUND_AUDIT_PATH = Path(
    ".artifacts/phase3b_family_bound_audit_67x13_family009/"
    "family_bound_audit_67x13_anchor119_family009.json"
)
DEFAULT_FAMILY_BOUND_SEMANTIC_AUDIT_PATH = Path(
    ".artifacts/phase3b_family_bound_semantic_audit/family_bound_semantic_audit.json"
)
DEFAULT_FAMILY_BOUND_SOLVER_PROFILE_PATH = Path(
    ".artifacts/phase3b_family_bound_solver_profile/family_bound_solver_profile.json"
)
DEFAULT_FAMILY_BOUND_PARAMETER_PROBE_PATH = Path(
    ".artifacts/phase3b_family_bound_parameter_probe_67x13_anchor119/"
    "family_bound_parameter_probe.json"
)
DEFAULT_FAMILY_BOUND_FORMULATION_PROBE_PATH = Path(
    ".artifacts/phase3b_family_bound_formulation_probe/family_bound_formulation_probe.json"
)
DEFAULT_FAMILY_LOOKUP_SEARCH_PROBE_PATH = Path(
    ".artifacts/phase3b_family_lookup_search_probe/family_lookup_search_probe.json"
)
DEFAULT_FAMILY_LOOKUP_ASSUMPTION_PROBE_PATH = Path(
    ".artifacts/phase3b_family_lookup_assumption_probe/family_lookup_assumption_probe.json"
)
DEFAULT_FAMILY_LOOKUP_SEMANTIC_REPRO_PATH = Path(
    ".artifacts/phase3b_family_lookup_semantic_repro/family_lookup_semantic_repro.json"
)
DEFAULT_FORCED_ANCHOR_PROTO_REDUCTION_PATH = Path(
    ".artifacts/phase3b_forced_anchor_proto_reduction_table_threshold/forced_anchor_proto_reduction.json"
)
DEFAULT_POWER_COVERAGE_WITNESS_AUDIT_PATH = Path(
    ".artifacts/phase3b_power_coverage_witness_audit/power_coverage_witness_audit.json"
)
DEFAULT_POWER_COVERAGE_WITNESS_DOMAIN_PATH = Path(
    ".artifacts/phase3b_power_coverage_witness_domain/witness_domain.json"
)
DEFAULT_FAMILY_LOOKUP_ASSIGNMENT_AUDIT_PATH = Path(
    ".artifacts/phase3b_family_lookup_assignment_audit/family_lookup_assignment_audit.json"
)
DEFAULT_POWER_CAPACITY_GVI_AUDIT_PATH = Path(
    ".artifacts/phase3b_power_capacity_gvi_audit/power_capacity_gvi_audit.json"
)


def build_phase3b_power_protocol_interaction_diagnostic(
    project_root: Path,
    *,
    power_coverage_anchor_delta_path: Optional[Path] = None,
    residual_optional_encoding_path: Optional[Path] = None,
    zero_branch_unknown_triage_path: Optional[Path] = None,
    model_slice_dir: Optional[Path] = None,
    model_slice_dirs: Optional[Sequence[Path]] = None,
    family_bound_audit_path: Optional[Path] = None,
    family_bound_semantic_audit_path: Optional[Path] = None,
    family_bound_solver_profile_path: Optional[Path] = None,
    family_bound_parameter_probe_path: Optional[Path] = None,
    family_bound_formulation_probe_path: Optional[Path] = None,
    family_lookup_search_probe_path: Optional[Path] = None,
    family_lookup_assumption_probe_path: Optional[Path] = None,
    family_lookup_semantic_repro_path: Optional[Path] = None,
    forced_anchor_proto_reduction_path: Optional[Path] = None,
    power_coverage_witness_audit_path: Optional[Path] = None,
    power_coverage_witness_domain_path: Optional[Path] = None,
    family_lookup_assignment_audit_path: Optional[Path] = None,
    power_capacity_gvi_audit_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    power_delta_path = _resolve_path(
        project_root,
        power_coverage_anchor_delta_path
        if power_coverage_anchor_delta_path is not None
        else DEFAULT_POWER_COVERAGE_ANCHOR_DELTA_PATH,
    )
    residual_path = _resolve_path(
        project_root,
        residual_optional_encoding_path
        if residual_optional_encoding_path is not None
        else DEFAULT_RESIDUAL_OPTIONAL_ENCODING_PATH,
    )
    zero_branch_path = _resolve_path(
        project_root,
        zero_branch_unknown_triage_path
        if zero_branch_unknown_triage_path is not None
        else DEFAULT_ZERO_BRANCH_UNKNOWN_TRIAGE_PATH,
    )
    if model_slice_dirs is not None:
        slice_dirs = [_resolve_path(project_root, Path(path)) for path in model_slice_dirs]
    elif model_slice_dir is not None:
        slice_dirs = [_resolve_path(project_root, model_slice_dir)]
    else:
        slice_dirs = [_resolve_path(project_root, path) for path in DEFAULT_MODEL_SLICE_DIRS]
    family_audit_path = _resolve_path(
        project_root,
        family_bound_audit_path
        if family_bound_audit_path is not None
        else DEFAULT_FAMILY_BOUND_AUDIT_PATH,
    )
    semantic_audit_path = _resolve_path(
        project_root,
        family_bound_semantic_audit_path
        if family_bound_semantic_audit_path is not None
        else DEFAULT_FAMILY_BOUND_SEMANTIC_AUDIT_PATH,
    )
    solver_profile_path = _resolve_path(
        project_root,
        family_bound_solver_profile_path
        if family_bound_solver_profile_path is not None
        else DEFAULT_FAMILY_BOUND_SOLVER_PROFILE_PATH,
    )
    parameter_probe_path = _resolve_path(
        project_root,
        family_bound_parameter_probe_path
        if family_bound_parameter_probe_path is not None
        else DEFAULT_FAMILY_BOUND_PARAMETER_PROBE_PATH,
    )
    formulation_probe_path = _resolve_path(
        project_root,
        family_bound_formulation_probe_path
        if family_bound_formulation_probe_path is not None
        else DEFAULT_FAMILY_BOUND_FORMULATION_PROBE_PATH,
    )
    lookup_search_probe_path = _resolve_path(
        project_root,
        family_lookup_search_probe_path
        if family_lookup_search_probe_path is not None
        else DEFAULT_FAMILY_LOOKUP_SEARCH_PROBE_PATH,
    )
    lookup_assumption_probe_path = _resolve_path(
        project_root,
        family_lookup_assumption_probe_path
        if family_lookup_assumption_probe_path is not None
        else DEFAULT_FAMILY_LOOKUP_ASSUMPTION_PROBE_PATH,
    )
    lookup_semantic_repro_path = _resolve_path(
        project_root,
        family_lookup_semantic_repro_path
        if family_lookup_semantic_repro_path is not None
        else DEFAULT_FAMILY_LOOKUP_SEMANTIC_REPRO_PATH,
    )
    proto_reduction_path = _resolve_path(
        project_root,
        forced_anchor_proto_reduction_path
        if forced_anchor_proto_reduction_path is not None
        else DEFAULT_FORCED_ANCHOR_PROTO_REDUCTION_PATH,
    )
    witness_audit_path = _resolve_path(
        project_root,
        power_coverage_witness_audit_path
        if power_coverage_witness_audit_path is not None
        else DEFAULT_POWER_COVERAGE_WITNESS_AUDIT_PATH,
    )
    witness_domain_path = _resolve_path(
        project_root,
        power_coverage_witness_domain_path
        if power_coverage_witness_domain_path is not None
        else DEFAULT_POWER_COVERAGE_WITNESS_DOMAIN_PATH,
    )
    lookup_audit_path = _resolve_path(
        project_root,
        family_lookup_assignment_audit_path
        if family_lookup_assignment_audit_path is not None
        else DEFAULT_FAMILY_LOOKUP_ASSIGNMENT_AUDIT_PATH,
    )
    capacity_gvi_path = _resolve_path(
        project_root,
        power_capacity_gvi_audit_path
        if power_capacity_gvi_audit_path is not None
        else DEFAULT_POWER_CAPACITY_GVI_AUDIT_PATH,
    )

    power_delta, power_delta_error = _load_json_mapping(power_delta_path)
    residual, residual_error = _load_json_mapping(residual_path)
    zero_branch, zero_branch_error = _load_json_mapping(zero_branch_path)
    family_audit, family_audit_error = _load_json_mapping(family_audit_path)
    semantic_audit, semantic_audit_error = _load_json_mapping(semantic_audit_path)
    solver_profile, solver_profile_error = _load_json_mapping(solver_profile_path)
    parameter_probe, parameter_probe_error = _load_json_mapping(parameter_probe_path)
    formulation_probe, formulation_probe_error = _load_json_mapping(
        formulation_probe_path
    )
    lookup_search_probe, lookup_search_probe_error = _load_json_mapping(
        lookup_search_probe_path
    )
    lookup_assumption_probe, lookup_assumption_probe_error = _load_json_mapping(
        lookup_assumption_probe_path
    )
    lookup_semantic_repro, lookup_semantic_repro_error = _load_json_mapping(
        lookup_semantic_repro_path
    )
    proto_reduction, proto_reduction_error = _load_json_mapping(proto_reduction_path)
    witness_audit, witness_audit_error = _load_json_mapping(witness_audit_path)
    witness_domain, witness_domain_error = _load_json_mapping(witness_domain_path)
    lookup_audit, lookup_audit_error = _load_json_mapping(lookup_audit_path)
    capacity_gvi, capacity_gvi_error = _load_json_mapping(capacity_gvi_path)
    slice_reports = _load_model_slice_reports(slice_dirs)

    power_delta_evidence = _power_delta_evidence(power_delta, power_delta_error)
    residual_evidence = _residual_evidence(residual, residual_error)
    zero_branch_evidence = _zero_branch_evidence(zero_branch, zero_branch_error)
    model_slice_evidence = _model_slice_evidence(slice_reports)
    family_audit_evidence = _family_audit_evidence(family_audit, family_audit_error)
    semantic_audit_evidence = _semantic_audit_evidence(
        semantic_audit,
        semantic_audit_error,
    )
    solver_profile_evidence = _solver_profile_evidence(
        solver_profile,
        solver_profile_error,
    )
    parameter_probe_evidence = _parameter_probe_evidence(
        parameter_probe,
        parameter_probe_error,
    )
    formulation_probe_evidence = _formulation_probe_evidence(
        formulation_probe,
        formulation_probe_error,
    )
    lookup_search_probe_evidence = _family_lookup_search_probe_evidence(
        lookup_search_probe,
        lookup_search_probe_error,
    )
    lookup_assumption_probe_evidence = _family_lookup_assumption_probe_evidence(
        lookup_assumption_probe,
        lookup_assumption_probe_error,
    )
    lookup_semantic_repro_evidence = _family_lookup_semantic_repro_evidence(
        lookup_semantic_repro,
        lookup_semantic_repro_error,
    )
    proto_reduction_evidence = _forced_anchor_proto_reduction_evidence(
        proto_reduction,
        proto_reduction_error,
    )
    witness_audit_evidence = _witness_audit_evidence(
        witness_audit,
        witness_audit_error,
    )
    witness_domain_evidence = _witness_domain_evidence(
        witness_domain,
        witness_domain_error,
    )
    lookup_audit_evidence = _family_lookup_audit_evidence(
        lookup_audit,
        lookup_audit_error,
    )
    capacity_gvi_evidence = _capacity_gvi_evidence(
        capacity_gvi,
        capacity_gvi_error,
    )
    findings = _findings(
        power_delta_evidence,
        residual_evidence,
        zero_branch_evidence,
        model_slice_evidence,
        family_audit_evidence,
        semantic_audit_evidence,
        solver_profile_evidence,
        parameter_probe_evidence,
        formulation_probe_evidence,
        lookup_search_probe_evidence,
        lookup_assumption_probe_evidence,
        lookup_semantic_repro_evidence,
        proto_reduction_evidence,
        witness_audit_evidence,
        witness_domain_evidence,
        lookup_audit_evidence,
        capacity_gvi_evidence,
    )
    hypothesis = _primary_hypothesis(findings)
    checks = _checks(
        power_delta_evidence,
        residual_evidence,
        zero_branch_evidence,
        model_slice_evidence,
        family_audit_evidence,
        semantic_audit_evidence,
        solver_profile_evidence,
        parameter_probe_evidence,
        formulation_probe_evidence,
        lookup_search_probe_evidence,
        lookup_assumption_probe_evidence,
        lookup_semantic_repro_evidence,
        proto_reduction_evidence,
        witness_audit_evidence,
        witness_domain_evidence,
        lookup_audit_evidence,
        capacity_gvi_evidence,
    )
    return {
        "metadata": {
            "source": POWER_PROTOCOL_INTERACTION_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "artifact_join_not_proof_source",
        },
        "paths": {
            "project_root": str(project_root),
            "power_coverage_anchor_delta": _display_path(project_root, power_delta_path),
            "residual_optional_encoding": _display_path(project_root, residual_path),
            "zero_branch_unknown_triage": _display_path(project_root, zero_branch_path),
            "model_slice_dirs": [
                _display_path(project_root, slice_dir) for slice_dir in slice_dirs
            ],
            "family_bound_audit": _display_path(project_root, family_audit_path),
            "family_bound_semantic_audit": _display_path(
                project_root,
                semantic_audit_path,
            ),
            "family_bound_solver_profile": _display_path(
                project_root,
                solver_profile_path,
            ),
            "family_bound_parameter_probe": _display_path(
                project_root,
                parameter_probe_path,
            ),
            "family_bound_formulation_probe": _display_path(
                project_root,
                formulation_probe_path,
            ),
            "family_lookup_search_probe": _display_path(
                project_root,
                lookup_search_probe_path,
            ),
            "family_lookup_assumption_probe": _display_path(
                project_root,
                lookup_assumption_probe_path,
            ),
            "family_lookup_semantic_repro": _display_path(
                project_root,
                lookup_semantic_repro_path,
            ),
            "forced_anchor_proto_reduction": _display_path(
                project_root,
                proto_reduction_path,
            ),
            "power_coverage_witness_audit": _display_path(
                project_root,
                witness_audit_path,
            ),
            "power_coverage_witness_domain": _display_path(
                project_root,
                witness_domain_path,
            ),
            "family_lookup_assignment_audit": _display_path(
                project_root,
                lookup_audit_path,
            ),
            "power_capacity_gvi_audit": _display_path(
                project_root,
                capacity_gvi_path,
            ),
        },
        "candidate": _candidate(
            power_delta_evidence,
            residual_evidence,
            zero_branch_evidence,
        ),
        "power_coverage_anchor_delta": power_delta_evidence,
        "residual_optional_encoding": residual_evidence,
        "zero_branch_unknown_triage": zero_branch_evidence,
        "model_slice": model_slice_evidence,
        "family_bound_audit": family_audit_evidence,
        "family_bound_semantic_audit": semantic_audit_evidence,
        "family_bound_solver_profile": solver_profile_evidence,
        "family_bound_parameter_probe": parameter_probe_evidence,
        "family_bound_formulation_probe": formulation_probe_evidence,
        "family_lookup_search_probe": lookup_search_probe_evidence,
        "family_lookup_assumption_probe": lookup_assumption_probe_evidence,
        "family_lookup_semantic_repro": lookup_semantic_repro_evidence,
        "forced_anchor_proto_reduction": proto_reduction_evidence,
        "power_coverage_witness_audit": witness_audit_evidence,
        "power_coverage_witness_domain": witness_domain_evidence,
        "family_lookup_assignment_audit": lookup_audit_evidence,
        "power_capacity_gvi_audit": capacity_gvi_evidence,
        "findings": findings,
        "analysis": {
            "primary_hypothesis": hypothesis,
            "next_probe_family": _next_probe_family(power_delta_evidence),
            "next_probe_template": _next_probe_template(power_delta_evidence),
            "next_actions": _next_actions(hypothesis),
        },
        "recommendation": _recommendation(hypothesis),
        "checks": checks,
    }


def render_phase3b_power_protocol_interaction_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    analysis = _mapping(report.get("analysis"))
    power_delta = _mapping(report.get("power_coverage_anchor_delta"))
    residual = _mapping(report.get("residual_optional_encoding"))
    zero_branch = _mapping(report.get("zero_branch_unknown_triage"))
    family_audit = _mapping(report.get("family_bound_audit"))
    semantic_audit = _mapping(report.get("family_bound_semantic_audit"))
    solver_profile = _mapping(report.get("family_bound_solver_profile"))
    parameter_probe = _mapping(report.get("family_bound_parameter_probe"))
    formulation_probe = _mapping(report.get("family_bound_formulation_probe"))
    lookup_search_probe = _mapping(report.get("family_lookup_search_probe"))
    lookup_assumption_probe = _mapping(report.get("family_lookup_assumption_probe"))
    lookup_semantic_repro = _mapping(report.get("family_lookup_semantic_repro"))
    proto_reduction = _mapping(report.get("forced_anchor_proto_reduction"))
    witness_audit = _mapping(report.get("power_coverage_witness_audit"))
    witness_domain = _mapping(report.get("power_coverage_witness_domain"))
    lookup_audit = _mapping(report.get("family_lookup_assignment_audit"))
    capacity_gvi = _mapping(report.get("power_capacity_gvi_audit"))
    lines = [
        "# Phase 3B Power/Protocol Interaction Diagnostic",
        "",
        f"- Candidate: {candidate.get('key')}",
        "- Diagnostic semantics: artifact_join_not_proof_source",
        f"- Primary hypothesis: {analysis.get('primary_hypothesis')}",
        f"- Next probe family: {analysis.get('next_probe_family')}",
        f"- Next probe template: {analysis.get('next_probe_template')}",
        f"- Zero-branch UNKNOWN count: {zero_branch.get('zero_branch_unknown_count', 0)}",
        f"- Power-family changed count: {power_delta.get('power_family_changed_count', 0)}",
        f"- Residual slots: {residual.get('residual_slots_by_template', {})}",
        f"- Family-bound audit: {family_audit.get('outcome')}",
        f"- Family-bound semantic audit: {semantic_audit.get('classification')}",
        f"- Family-bound solver profile: {solver_profile.get('classification')}",
        f"- Family-bound parameter probe: {parameter_probe.get('outcome')}",
        f"- Family-bound formulation probe: {formulation_probe.get('classification')}",
        f"- Family lookup search probe: {lookup_search_probe.get('outcome')}",
        f"- Family lookup assumption probe: {lookup_assumption_probe.get('outcome')}",
        f"- Family lookup semantic repro: {lookup_semantic_repro.get('outcome')}",
        f"- Forced-anchor proto reduction: {proto_reduction.get('outcome')}",
        f"- Power-coverage witness audit: {witness_audit.get('classification')}",
        f"- Power-coverage witness domain: {witness_domain.get('outcome')}",
        f"- Family lookup audit: {lookup_audit.get('outcome')}",
        f"- Power-capacity GVI audit: {capacity_gvi.get('classification')}",
        f"- Recommendation: {report.get('recommendation')}",
        "",
        "## Findings",
        "",
    ]
    findings = [str(item) for item in list(report.get("findings", []))]
    lines.extend(f"- {finding}" for finding in (findings or ["none"]))
    lines.extend(
        [
            "",
            "## Top Power-Family Deltas",
            "",
            "| Family | Baseline | Comparison | Delta |",
            "| --- | --- | --- | --- |",
        ]
    )
    for entry in list(power_delta.get("top_power_family_deltas", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("family")),
                        _markdown_cell(entry.get("baseline")),
                        _markdown_cell(entry.get("comparison")),
                        _markdown_cell(entry.get("delta")),
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Optional Template Deltas",
            "",
            "| Template | Baseline | Comparison | Delta |",
            "| --- | --- | --- | --- |",
        ]
    )
    for entry in list(power_delta.get("optional_template_deltas", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("template")),
                        _markdown_cell(entry.get("baseline_surviving_count")),
                        _markdown_cell(entry.get("comparison_surviving_count")),
                        _markdown_cell(entry.get("surviving_delta")),
                    ]
                )
                + " |"
            )
    lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(check.get("check_id")),
                        _markdown_cell(check.get("status")),
                        _markdown_cell(check.get("detail")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_power_protocol_interaction_text(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    analysis = _mapping(report.get("analysis"))
    power_delta = _mapping(report.get("power_coverage_anchor_delta"))
    residual = _mapping(report.get("residual_optional_encoding"))
    zero_branch = _mapping(report.get("zero_branch_unknown_triage"))
    family_audit = _mapping(report.get("family_bound_audit"))
    semantic_audit = _mapping(report.get("family_bound_semantic_audit"))
    solver_profile = _mapping(report.get("family_bound_solver_profile"))
    parameter_probe = _mapping(report.get("family_bound_parameter_probe"))
    formulation_probe = _mapping(report.get("family_bound_formulation_probe"))
    lookup_search_probe = _mapping(report.get("family_lookup_search_probe"))
    lookup_assumption_probe = _mapping(report.get("family_lookup_assumption_probe"))
    lookup_semantic_repro = _mapping(report.get("family_lookup_semantic_repro"))
    proto_reduction = _mapping(report.get("forced_anchor_proto_reduction"))
    witness_audit = _mapping(report.get("power_coverage_witness_audit"))
    witness_domain = _mapping(report.get("power_coverage_witness_domain"))
    lookup_audit = _mapping(report.get("family_lookup_assignment_audit"))
    capacity_gvi = _mapping(report.get("power_capacity_gvi_audit"))
    lines = [
        "Phase 3B power/protocol interaction diagnostic",
        f"candidate={candidate.get('key')}",
        "diagnostic_semantics=artifact_join_not_proof_source",
        f"primary_hypothesis={analysis.get('primary_hypothesis')}",
        f"next_probe_family={analysis.get('next_probe_family')}",
        f"next_probe_template={analysis.get('next_probe_template')}",
        f"zero_branch_unknown_count={zero_branch.get('zero_branch_unknown_count', 0)}",
        f"power_family_changed_count={power_delta.get('power_family_changed_count', 0)}",
        f"residual_slots={residual.get('residual_slots_by_template', {})}",
        f"family_bound_audit={family_audit.get('outcome')}",
        f"family_bound_semantic_audit={semantic_audit.get('classification')}",
        f"family_bound_solver_profile={solver_profile.get('classification')}",
        f"family_bound_parameter_probe={parameter_probe.get('outcome')}",
        f"family_bound_formulation_probe={formulation_probe.get('classification')}",
        f"family_lookup_search_probe={lookup_search_probe.get('outcome')}",
        f"family_lookup_assumption_probe={lookup_assumption_probe.get('outcome')}",
        f"family_lookup_semantic_repro={lookup_semantic_repro.get('outcome')}",
        f"forced_anchor_proto_reduction={proto_reduction.get('outcome')}",
        f"power_coverage_witness_audit={witness_audit.get('classification')}",
        f"power_coverage_witness_domain={witness_domain.get('outcome')}",
        f"family_lookup_assignment_audit={lookup_audit.get('outcome')}",
        f"power_capacity_gvi_audit={capacity_gvi.get('classification')}",
        f"recommendation={report.get('recommendation')}",
    ]
    for finding in list(report.get("findings", [])):
        lines.append(f"finding={finding}")
    for action in list(analysis.get("next_actions", [])):
        lines.append(f"next_action={action}")
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "check "
                f"id={check.get('check_id')} "
                f"status={check.get('status')} "
                f"detail={check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def _power_delta_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    candidate = _mapping(payload.get("candidate"))
    delta = _mapping(payload.get("delta"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == POWER_COVERAGE_ANCHOR_DELTA_SOURCE,
        "candidate_key": candidate.get("key"),
        "power_family_changed_count": int(delta.get("power_family_changed_count", 0)),
        "power_family_positive_delta_sum": int(
            delta.get("power_family_positive_delta_sum", 0)
        ),
        "power_family_negative_delta_sum": int(
            delta.get("power_family_negative_delta_sum", 0)
        ),
        "mandatory_surviving_delta": int(delta.get("mandatory_surviving_delta", 0)),
        "optional_surviving_delta": int(delta.get("optional_surviving_delta", 0)),
        "top_power_family_deltas": _mapping_list(delta.get("top_power_family_deltas")),
        "top_mandatory_group_deltas": _mapping_list(
            delta.get("top_mandatory_group_deltas")
        ),
        "optional_template_deltas": _mapping_list(
            delta.get("optional_template_deltas")
        ),
        "diagnostic_findings": [
            str(item) for item in list(delta.get("diagnostic_findings", []))
        ],
    }


def _residual_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    candidate = _mapping(payload.get("candidate"))
    encoding = _mapping(payload.get("encoding"))
    residual = _mapping(encoding.get("residual_optional_slots"))
    power = _mapping(encoding.get("power_coverage"))
    gvi = _mapping(encoding.get("global_valid_inequalities"))
    ghost_aware = _mapping(gvi.get("ghost_aware_via_pole_feasibility"))
    proto = _mapping(encoding.get("proto"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == RESIDUAL_OPTIONAL_ENCODING_SOURCE,
        "candidate_key": candidate.get("key"),
        "residual_slots_by_template": dict(_mapping(residual.get("by_template"))),
        "residual_slot_total": int(residual.get("total", 0)),
        "power_coverage": {
            "representation": power.get("representation"),
            "encoding": power.get("encoding"),
            "powered_slots": int(power.get("powered_slots", 0)),
            "pole_slots": int(power.get("pole_slots", 0)),
            "witness_indices": int(power.get("witness_indices", 0)),
            "element_constraints": int(power.get("element_constraints", 0)),
            "radius": power.get("radius"),
        },
        "optional_cardinality_bounds": dict(
            _mapping(gvi.get("optional_cardinality_bounds"))
        ),
        "powered_template_demands": dict(_mapping(gvi.get("powered_template_demands"))),
        "lower_bound_optional_powered_demands": dict(
            _mapping(gvi.get("lower_bound_optional_powered_demands"))
        ),
        "ghost_aware_via_pole_feasibility": dict(ghost_aware),
        "proto": {
            "variable_count": int(proto.get("variable_count", 0)),
            "constraint_count": int(proto.get("constraint_count", 0)),
        },
    }


def _zero_branch_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    candidate = _mapping(payload.get("candidate"))
    matrix = _mapping(payload.get("matrix"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == ZERO_BRANCH_UNKNOWN_TRIAGE_SOURCE,
        "candidate_key": candidate.get("key"),
        "zero_branch_unknown_count": int(matrix.get("zero_branch_unknown_count", 0)),
        "findings": [str(item) for item in list(payload.get("findings", []))],
        "recommendation": str(payload.get("recommendation", "")),
    }


def _family_audit_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    status = _mapping(payload.get("status"))
    summary = _mapping(payload.get("summary"))
    audits = _mapping_list(payload.get("audits"))
    first = audits[0] if audits else {}
    derivation = _mapping(first.get("derivation"))
    proto = _mapping(first.get("proto_constraint"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == FAMILY_BOUND_AUDIT_SOURCE,
        "outcome": status.get("outcome"),
        "all_bounds_consistent": bool(summary.get("all_bounds_consistent", False)),
        "audit_count": int(summary.get("audit_count", len(audits))),
        "anchor_idx": first.get("anchor_idx"),
        "target_power_family": first.get("target_power_family"),
        "family_size": derivation.get("family_size"),
        "blocked_family_pose_count": derivation.get("blocked_family_pose_count"),
        "global_upper_bound": derivation.get("global_upper_bound"),
        "derived_conditioned_upper_bound": derivation.get(
            "derived_conditioned_upper_bound"
        ),
        "domain_conditioned_upper_bound": derivation.get(
            "domain_conditioned_upper_bound"
        ),
        "proto_conditioned_upper_bound": proto.get(
            "implied_conditioned_upper_bound"
        ),
        "bounds_consistent": bool(first.get("bounds_consistent", False)),
    }


def _semantic_audit_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    family = _mapping(payload.get("family_bound"))
    relaxed = _mapping(payload.get("target_family_slice"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == FAMILY_BOUND_SEMANTIC_AUDIT_SOURCE,
        "classification": payload.get("classification"),
        "target_power_family": family.get("target_power_family"),
        "derived_conditioned_upper_bound": family.get("derived_conditioned_upper_bound"),
        "relaxed_power_family_count_value": relaxed.get(
            "relaxed_power_family_count_value"
        ),
        "relaxed_family_bound_violation": relaxed.get(
            "relaxed_family_bound_violation"
        ),
        "findings": [str(item) for item in list(payload.get("findings", []))],
        "recommendation": str(payload.get("recommendation", "")),
    }


def _solver_profile_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    comparison = _mapping(payload.get("comparison"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == FAMILY_BOUND_SOLVER_PROFILE_SOURCE,
        "classification": payload.get("classification"),
        "base_status": comparison.get("base_status"),
        "relaxed_status": comparison.get("relaxed_status"),
        "wall_time_speedup": comparison.get("wall_time_speedup"),
        "deterministic_time_speedup": comparison.get("deterministic_time_speedup"),
        "base_branches": comparison.get("base_branches"),
        "base_conflicts": comparison.get("base_conflicts"),
        "relaxed_family_bound_violation": comparison.get(
            "relaxed_family_bound_violation"
        ),
        "recommendation": str(payload.get("recommendation", "")),
    }


def _parameter_probe_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    status = _mapping(payload.get("status"))
    probe = _mapping(payload.get("probe"))
    unknown = _mapping(probe.get("unknown_diagnostics"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == FAMILY_BOUND_PARAMETER_PROBE_SOURCE,
        "outcome": status.get("outcome"),
        "status_counts": dict(_mapping(probe.get("status_counts"))),
        "best_terminal_entry": probe.get("best_terminal_entry"),
        "unknown_count": int(unknown.get("unknown_count", 0)),
        "zero_branch_unknown_count": int(unknown.get("zero_branch_unknown_count", 0)),
        "zero_branch_unknown_profiles": [
            str(item) for item in list(unknown.get("zero_branch_unknown_profiles", []))
        ],
        "recommendation": str(status.get("recommendation", "")),
    }


def _formulation_probe_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    comparison = _mapping(payload.get("comparison"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == FAMILY_BOUND_FORMULATION_PROBE_SOURCE,
        "classification": payload.get("classification"),
        "base_status": comparison.get("base_status"),
        "direct_status": comparison.get("direct_status"),
        "wall_time_speedup": comparison.get("wall_time_speedup"),
        "direct_bound_value": comparison.get("direct_bound_value"),
        "direct_count_value": comparison.get("direct_count_value"),
        "recommendation": str(payload.get("recommendation", "")),
    }


def _family_lookup_search_probe_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    status = _mapping(payload.get("status"))
    probe = _mapping(payload.get("probe"))
    unknown = _mapping(probe.get("unknown_diagnostics"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == FAMILY_LOOKUP_SEARCH_PROBE_SOURCE,
        "outcome": status.get("outcome"),
        "status_counts": dict(_mapping(probe.get("status_counts"))),
        "best_terminal_entry": probe.get("best_terminal_entry"),
        "unknown_count": int(unknown.get("unknown_count", 0)),
        "zero_branch_unknown_count": int(unknown.get("zero_branch_unknown_count", 0)),
        "search_progress_unknown_count": int(
            unknown.get("search_progress_unknown_count", 0)
        ),
        "zero_branch_unknown_by_variant": dict(
            _mapping(unknown.get("zero_branch_unknown_by_variant"))
        ),
        "zero_branch_unknown_by_profile": dict(
            _mapping(unknown.get("zero_branch_unknown_by_profile"))
        ),
        "recommendation": str(status.get("recommendation", "")),
    }


def _family_lookup_assumption_probe_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    status = _mapping(payload.get("status"))
    profile = _mapping(payload.get("profile"))
    probe = _mapping(payload.get("probe"))
    unknown = _mapping(probe.get("unknown_diagnostics"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source")
        == FAMILY_LOOKUP_ASSUMPTION_PROBE_SOURCE,
        "outcome": status.get("outcome"),
        "assumption_count": int(profile.get("assumption_count", 0)),
        "status_counts": dict(_mapping(probe.get("status_counts"))),
        "best_terminal_entry": probe.get("best_terminal_entry"),
        "unknown_count": int(unknown.get("unknown_count", 0)),
        "zero_branch_unknown_count": int(unknown.get("zero_branch_unknown_count", 0)),
        "search_progress_unknown_count": int(
            unknown.get("search_progress_unknown_count", 0)
        ),
        "zero_branch_unknown_by_assumption": dict(
            _mapping(unknown.get("zero_branch_unknown_by_assumption"))
        ),
        "zero_branch_unknown_by_variant": dict(
            _mapping(unknown.get("zero_branch_unknown_by_variant"))
        ),
        "recommendation": str(status.get("recommendation", "")),
    }


def _family_lookup_semantic_repro_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    status = _mapping(payload.get("status"))
    extraction = _mapping(payload.get("extraction"))
    repro = _mapping(payload.get("repro"))
    unknown = _mapping(repro.get("unknown_diagnostics"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source")
        == FAMILY_LOOKUP_SEMANTIC_REPRO_SOURCE,
        "outcome": status.get("outcome"),
        "selected_slot_count": int(extraction.get("selected_slot_count", 0)),
        "selected_family_ids": [
            int(value) for value in list(extraction.get("selected_family_ids", []))
        ],
        "status_counts": dict(_mapping(repro.get("status_counts"))),
        "best_terminal_entry": repro.get("best_terminal_entry"),
        "unknown_count": int(unknown.get("unknown_count", 0)),
        "zero_branch_unknown_count": int(unknown.get("zero_branch_unknown_count", 0)),
        "recommendation": str(status.get("recommendation", "")),
    }


def _forced_anchor_proto_reduction_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    status = _mapping(payload.get("status"))
    reduction = _mapping(payload.get("reduction"))
    unknown = _mapping(reduction.get("unknown_diagnostics"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source")
        == FORCED_ANCHOR_PROTO_REDUCTION_SOURCE,
        "outcome": status.get("outcome"),
        "status_counts": dict(_mapping(reduction.get("status_counts"))),
        "profile_ids": _proto_reduction_profile_ids(reduction),
        "best_terminal_entry": reduction.get("best_terminal_entry"),
        "unlocking_variants": [
            dict(item)
            for item in list(reduction.get("unlocking_variants", []))
            if isinstance(item, Mapping)
        ],
        "unknown_count": int(unknown.get("unknown_count", 0)),
        "zero_branch_unknown_count": int(unknown.get("zero_branch_unknown_count", 0)),
        "search_progress_unknown_count": int(
            unknown.get("search_progress_unknown_count", 0)
        ),
        "zero_branch_unknown_by_variant": dict(
            _mapping(unknown.get("zero_branch_unknown_by_variant"))
        ),
        "search_progress_unknown_samples": [
            dict(item)
            for item in list(unknown.get("search_progress_unknown_samples", []))
            if isinstance(item, Mapping)
        ],
        "recommendation": str(status.get("recommendation", "")),
    }


def _proto_reduction_profile_ids(reduction: Mapping[str, Any]) -> list[str]:
    profile_ids: list[str] = []
    for entry in list(reduction.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        profile = _mapping(entry.get("solver_parameter_profile"))
        profile_id = str(profile.get("profile_id", ""))
        if profile_id:
            profile_ids.append(profile_id)
    return sorted(set(profile_ids))


def _witness_audit_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    witness = _mapping(payload.get("witness_encoding"))
    pressure = _mapping(payload.get("domain_pressure"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == POWER_COVERAGE_WITNESS_AUDIT_SOURCE,
        "classification": payload.get("classification"),
        "encoding": witness.get("encoding"),
        "powered_slots": witness.get("powered_slots"),
        "pole_slots": witness.get("pole_slots"),
        "witness_indices": witness.get("witness_indices"),
        "element_constraints": witness.get("element_constraints"),
        "element_constraints_per_powered_slot": witness.get(
            "element_constraints_per_powered_slot"
        ),
        "cover_choice_vars_complete": bool(
            witness.get("cover_choice_vars_complete", False)
        ),
        "core_blocker_classification": pressure.get("core_blocker_classification"),
        "no_protocol_lower_bound_core_status": pressure.get(
            "no_protocol_lower_bound_core_status"
        ),
        "recommendation": str(payload.get("recommendation", "")),
    }


def _witness_domain_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    status = _mapping(payload.get("status"))
    summary = _mapping(payload.get("summary"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == POWER_COVERAGE_WITNESS_DOMAIN_SOURCE,
        "outcome": status.get("outcome"),
        "anchor_count": int(summary.get("anchor_count", 0)),
        "required_unsupported_slot_count": int(
            summary.get("required_unsupported_slot_count", 0)
        ),
        "optional_unsupported_slot_count": int(
            summary.get("optional_unsupported_slot_count", 0)
        ),
        "classification_counts": dict(_mapping(summary.get("classification_counts"))),
        "recommendation": str(payload.get("recommendation", "")),
    }


def _family_lookup_audit_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    status = _mapping(payload.get("status"))
    encoding = _mapping(payload.get("family_lookup_encoding"))
    summary = _mapping(payload.get("summary"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == FAMILY_LOOKUP_ASSIGNMENT_AUDIT_SOURCE,
        "outcome": status.get("outcome"),
        "use_shell_lookup": bool(encoding.get("use_shell_lookup", False)),
        "shell_lookup_row_count": int(encoding.get("shell_lookup_row_count", 0)),
        "shell_lookup_family_count": int(encoding.get("shell_lookup_family_count", 0)),
        "family_variable_count": int(encoding.get("family_variable_count", 0)),
        "family_variable_domain": list(encoding.get("family_variable_domain", [])),
        "family_constraint_kind_counts": dict(
            _mapping(encoding.get("family_constraint_kind_counts"))
        ),
        "surviving_pose_count": int(summary.get("surviving_pose_count", 0)),
        "missing_lookup_row_count": int(summary.get("missing_lookup_row_count", 0)),
        "recommendation": str(payload.get("recommendation", "")),
    }


def _capacity_gvi_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    capacity = _mapping(payload.get("power_capacity_gvi"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == POWER_CAPACITY_GVI_AUDIT_SOURCE,
        "classification": payload.get("classification"),
        "lower_bound_count": int(capacity.get("lower_bound_count", 0)),
        "aggregated_nonzero_terms": int(capacity.get("aggregated_nonzero_terms", 0)),
        "raw_nonzero_terms": int(capacity.get("raw_nonzero_terms", 0)),
        "family_count": int(capacity.get("family_count", 0)),
        "lower_bounds": [
            dict(row)
            for row in list(capacity.get("lower_bounds", []))
            if isinstance(row, Mapping)
        ],
        "recommendation": str(payload.get("recommendation", "")),
    }


def _model_slice_evidence(reports: list[Mapping[str, Any]]) -> Dict[str, Any]:
    findings: list[str] = []
    status_counts_by_variant: Dict[str, Dict[str, int]] = {}
    loaded: list[Dict[str, Any]] = []
    for report in reports:
        payload = _mapping(report.get("payload"))
        metadata = _mapping(payload.get("metadata"))
        if metadata.get("source") != FORCED_ANCHOR_MODEL_SLICE_SOURCE:
            continue
        matrix = _mapping(payload.get("slice_matrix"))
        findings.extend(str(item) for item in list(matrix.get("diagnostic_findings", [])))
        for variant, counts in _mapping(matrix.get("status_counts_by_variant")).items():
            bucket = status_counts_by_variant.setdefault(str(variant), {})
            for status, count in _mapping(counts).items():
                bucket[str(status)] = int(bucket.get(str(status), 0)) + int(count)
        loaded.append(
            {
                "path": str(report.get("path")),
                "diagnostic_findings": [
                    str(item) for item in list(matrix.get("diagnostic_findings", []))
                ],
                "status_counts_by_variant": dict(
                    _mapping(matrix.get("status_counts_by_variant"))
                ),
            }
        )
    return {
        "present": bool(loaded),
        "report_count": int(len(loaded)),
        "diagnostic_findings": _dedupe(findings),
        "status_counts_by_variant": status_counts_by_variant,
        "reports": loaded,
    }


def _findings(
    power_delta: Mapping[str, Any],
    residual: Mapping[str, Any],
    zero_branch: Mapping[str, Any],
    model_slice: Mapping[str, Any],
    family_audit: Mapping[str, Any],
    semantic_audit: Mapping[str, Any],
    solver_profile: Mapping[str, Any],
    parameter_probe: Mapping[str, Any],
    formulation_probe: Mapping[str, Any],
    lookup_search_probe: Mapping[str, Any],
    lookup_assumption_probe: Mapping[str, Any],
    lookup_semantic_repro: Mapping[str, Any],
    proto_reduction: Mapping[str, Any],
    witness_audit: Mapping[str, Any],
    witness_domain: Mapping[str, Any],
    lookup_audit: Mapping[str, Any],
    capacity_gvi: Mapping[str, Any],
) -> list[str]:
    findings: list[str] = []
    if int(zero_branch.get("zero_branch_unknown_count", 0)) > 0:
        findings.append("zero_branch_unknown_reproduced")
    if int(power_delta.get("power_family_changed_count", 0)) > 0:
        findings.append("conditioned_power_family_bounds_shift")
    if int(power_delta.get("power_family_positive_delta_sum", 0)) > 0:
        findings.append("conditioned_power_family_bounds_loosen_for_some_families")
    if int(power_delta.get("power_family_negative_delta_sum", 0)) < 0:
        findings.append("conditioned_power_family_bounds_tighten_for_some_families")
    optional = _optional_delta_by_template(power_delta)
    if int(_mapping(optional.get("power_pole")).get("surviving_delta", 0)) == 0 and int(
        power_delta.get("power_family_changed_count", 0)
    ) > 0:
        findings.append("power_pole_candidate_domain_stable")
    if int(_mapping(optional.get("protocol_storage_box")).get("surviving_delta", 0)) < 0:
        findings.append("protocol_storage_box_domain_tightens")
    lower_demands = _mapping(residual.get("lower_bound_optional_powered_demands"))
    if int(lower_demands.get("protocol_storage_box", 0)) > 0:
        findings.append("protocol_storage_box_lower_bound_present")
    ghost = _mapping(residual.get("ghost_aware_via_pole_feasibility"))
    if int(ghost.get("conditioned_family_upper_bound_constraints", 0)) > 0:
        findings.append("ghost_conditioned_power_family_bounds_present")
    power_coverage = _mapping(residual.get("power_coverage"))
    if int(power_coverage.get("element_constraints", 0)) > 0:
        findings.append("geometric_power_coverage_element_encoding_present")
    for finding in list(model_slice.get("diagnostic_findings", [])):
        token = str(finding)
        findings.append(token)
        if "skip_power_coverage_unlocks_feasible_core" in token:
            findings.append("skip_power_coverage_unlocks_feasible_slice")
        if "power_coverage_core_required_for_blocker" in token:
            findings.append("power_coverage_core_required_for_blocker")
        if "power_coverage_dynamic_coupling_relaxation_still_unknown" in token:
            findings.append("power_coverage_dynamic_coupling_relaxation_still_unknown")
        if "power_coverage_dynamic_and_family_count_relaxation_still_unknown" in token:
            findings.append(
                "power_coverage_dynamic_and_family_count_relaxation_still_unknown"
            )
        if "power_coverage_dynamic_and_family_count_relaxation_unlocks_core" in token:
            findings.append(
                "power_coverage_dynamic_and_family_count_relaxation_unlocks_core"
            )
        if "power_coverage_dynamic_and_family_membership_count_relaxation_still_unknown" in token:
            findings.append(
                "power_coverage_dynamic_and_family_membership_count_relaxation_still_unknown"
            )
        if "power_coverage_dynamic_and_family_membership_count_relaxation_unlocks_core" in token:
            findings.append(
                "power_coverage_dynamic_and_family_membership_count_relaxation_unlocks_core"
            )
        if "power_coverage_dynamic_and_family_table_relaxation_still_unknown" in token:
            findings.append(
                "power_coverage_dynamic_and_family_table_relaxation_still_unknown"
            )
        if "power_coverage_dynamic_and_family_table_relaxation_unlocks_core" in token:
            findings.append(
                "power_coverage_dynamic_and_family_table_relaxation_unlocks_core"
            )
        if "power_coverage_dynamic_and_family_linear_relaxation_still_unknown" in token:
            findings.append(
                "power_coverage_dynamic_and_family_linear_relaxation_still_unknown"
            )
        if "power_coverage_dynamic_and_family_linear_relaxation_unlocks_core" in token:
            findings.append(
                "power_coverage_dynamic_and_family_linear_relaxation_unlocks_core"
            )
        if "power_coverage_dynamic_and_family_sentinel_relaxation_still_unknown" in token:
            findings.append(
                "power_coverage_dynamic_and_family_sentinel_relaxation_still_unknown"
            )
        if "power_coverage_dynamic_and_family_membership_linear_relaxation_still_unknown" in token:
            findings.append(
                "power_coverage_dynamic_and_family_membership_linear_relaxation_still_unknown"
            )
        if "power_coverage_dynamic_and_family_ordering_linear_relaxation_still_unknown" in token:
            findings.append(
                "power_coverage_dynamic_and_family_ordering_linear_relaxation_still_unknown"
            )
        if "power_coverage_dynamic_and_family_other_linear_relaxation_still_unknown" in token:
            findings.append(
                "power_coverage_dynamic_and_family_other_linear_relaxation_still_unknown"
            )
        if "power_coverage_dynamic_and_family_lookup_relaxation_still_unknown" in token:
            findings.append(
                "power_coverage_dynamic_and_family_lookup_relaxation_still_unknown"
            )
        if "power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core" in token:
            findings.append(
                "power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core"
            )
        if "power_coverage_dynamic_and_family_distance_relaxation_still_unknown" in token:
            findings.append(
                "power_coverage_dynamic_and_family_distance_relaxation_still_unknown"
            )
        if "power_coverage_dynamic_and_family_distance_relaxation_unlocks_core" in token:
            findings.append(
                "power_coverage_dynamic_and_family_distance_relaxation_unlocks_core"
            )
        if "power_coverage_dynamic_and_family_lookup_distance_relaxation_unlocks_core" in token:
            findings.append(
                "power_coverage_dynamic_and_family_lookup_distance_relaxation_unlocks_core"
            )
        if "power_coverage_dynamic_and_family_assignment_relaxation_unlocks_core" in token:
            findings.append(
                "power_coverage_dynamic_and_family_assignment_relaxation_unlocks_core"
            )
        if "power_coverage_dynamic_family_assignment_and_gvi_relaxation_unlocks_core" in token:
            findings.append(
                "power_coverage_dynamic_family_assignment_and_gvi_relaxation_unlocks_core"
            )
        if "family_active_domain_channeling_still_unknown" in token:
            findings.append("family_active_domain_channeling_still_unknown")
        if "family_membership_active_channeling_still_unknown" in token:
            findings.append("family_membership_active_channeling_still_unknown")
        if "family_active_and_membership_channeling_still_unknown" in token:
            findings.append("family_active_and_membership_channeling_still_unknown")
        if "family_active_and_membership_channeling_unlocks_core" in token:
            findings.append("family_active_and_membership_channeling_unlocks_core")
        if "family_shell_pair_tables_still_unknown" in token:
            findings.append("family_shell_pair_tables_still_unknown")
        if "power_coverage_dynamic_and_family_shell_pair_tables_still_unknown" in token:
            findings.append("power_coverage_dynamic_and_family_shell_pair_tables_still_unknown")
        if "family_lookup_rebuilt_channeling_still_unknown" in token:
            findings.append("family_lookup_rebuilt_channeling_still_unknown")
        if "power_coverage_dynamic_and_family_lookup_rebuilt_channeling_still_unknown" in token:
            findings.append(
                "power_coverage_dynamic_and_family_lookup_rebuilt_channeling_still_unknown"
            )
        if "power_coverage_dynamic_and_family_lookup_rebuilt_channeling_unlocks_core" in token:
            findings.append(
                "power_coverage_dynamic_and_family_lookup_rebuilt_channeling_unlocks_core"
            )
        for label in (
            "membership_only",
            "shell_pair_only",
            "ordering_only",
            "membership_shell_pair",
            "membership_ordering",
            "shell_pair_ordering",
        ):
            if (
                f"power_coverage_dynamic_and_family_lookup_rebuilt_{label}_still_unknown"
                in token
            ):
                findings.append(
                    f"power_coverage_dynamic_and_family_lookup_rebuilt_{label}_still_unknown"
                )
            if (
                f"power_coverage_dynamic_and_family_lookup_rebuilt_{label}_unlocks_core"
                in token
            ):
                findings.append(
                    f"power_coverage_dynamic_and_family_lookup_rebuilt_{label}_unlocks_core"
                )
        if "protocol_lower_bound_not_primary" in token:
            findings.append("protocol_lower_bound_not_primary")
        if "target_power_family_bound_relaxation_unlocks_feasible_core" in token:
            findings.append("target_power_family_bound_relaxation_unlocks_feasible_slice")
        if "target_power_family_relaxed_protocol_boxes_unlock_feasible_core" in token:
            findings.append("target_power_family_relaxed_protocol_boxes_unlock_feasible_slice")
    if (
        "protocol_storage_box_domain_tightens" in findings
        and "protocol_lower_bound_not_primary" in findings
    ):
        findings.append("protocol_domain_tightening_not_lower_bound_primary")
    if bool(family_audit.get("bounds_consistent", False)):
        findings.append("target_family_bound_derivation_internally_consistent")
    if (
        "target_power_family_bound_relaxation_unlocks_feasible_slice" in findings
        and bool(family_audit.get("bounds_consistent", False))
    ):
        findings.append("active_blocker_bound_is_consistently_derived")
    for finding in list(semantic_audit.get("findings", [])):
        findings.append(str(finding))
    if (
        semantic_audit.get("classification")
        == "solver_sensitivity_without_bound_violation"
    ):
        findings.append("target_bound_solver_sensitivity_without_semantic_violation")
    if semantic_audit.get("classification") == "relaxation_not_terminal_feasible":
        findings.append("target_family_relaxation_not_terminal_feasible")
    if (
        solver_profile.get("classification")
        == "bound_present_unknown_bound_absent_terminal_without_violation"
    ):
        findings.append("bound_present_unknown_absent_terminal_without_violation")
    if (
        solver_profile.get("classification") == "solver_profile_inconclusive"
        and str(solver_profile.get("relaxed_status")) == "INFEASIBLE"
    ):
        findings.append("target_family_relaxation_profile_infeasible")
    if (
        _float_or_zero(solver_profile.get("wall_time_speedup")) >= 10.0
        and solver_profile.get("base_status") == "UNKNOWN"
    ):
        findings.append("bound_present_slice_spends_time_without_terminal_progress")
    if (
        parameter_probe.get("outcome") == "parameter_probe_unknown_remaining"
        and int(parameter_probe.get("zero_branch_unknown_count", 0)) > 0
    ):
        findings.append("bound_present_parameter_probe_all_zero_branch_unknown")
    if (
        lookup_search_probe.get("outcome")
        == "search_probe_zero_branch_unknown_remaining"
        and int(lookup_search_probe.get("zero_branch_unknown_count", 0)) > 0
    ):
        findings.append("family_lookup_search_probe_all_zero_branch_unknown")
    if (
        lookup_search_probe.get("outcome")
        == "search_probe_progress_without_terminal"
        and int(lookup_search_probe.get("search_progress_unknown_count", 0)) > 0
    ):
        findings.append("family_lookup_search_probe_progress_without_terminal")
    if lookup_search_probe.get("outcome") == "search_probe_terminal_found":
        findings.append("family_lookup_search_probe_terminal_found")
    if (
        lookup_assumption_probe.get("outcome")
        == "assumption_probe_zero_branch_unknown_remaining"
        and int(lookup_assumption_probe.get("zero_branch_unknown_count", 0)) > 0
    ):
        findings.append("family_lookup_assumption_probe_zero_branch_unknown")
    if (
        lookup_assumption_probe.get("outcome")
        == "assumption_probe_progress_without_terminal"
        and int(lookup_assumption_probe.get("search_progress_unknown_count", 0)) > 0
    ):
        findings.append("family_lookup_assumption_probe_progress_without_terminal")
    if lookup_assumption_probe.get("outcome") == "assumption_probe_infeasible_found":
        findings.append("family_lookup_assumption_probe_infeasible_found")
    if lookup_assumption_probe.get("outcome") == "assumption_probe_terminal_found":
        findings.append("family_lookup_assumption_probe_terminal_found")
    if (
        lookup_semantic_repro.get("outcome")
        == "semantic_repro_terminal_without_zero_branch"
    ):
        findings.append("family_lookup_semantic_repro_terminal_without_zero_branch")
    if (
        lookup_semantic_repro.get("outcome")
        == "semantic_repro_zero_branch_reproduced"
    ):
        findings.append("family_lookup_semantic_repro_zero_branch_reproduced")
    if (
        proto_reduction.get("outcome")
        == "proto_reduction_search_progress_without_terminal"
        and int(proto_reduction.get("search_progress_unknown_count", 0)) > 0
    ):
        findings.append("forced_anchor_proto_reduction_search_progress")
        if _proto_reduction_has_progress_variant(
            proto_reduction,
            "remove_power_coverage_elements_and_family_lookup_table",
        ):
            findings.append(
                "forced_anchor_proto_reduction_elements_lookup_table_progress"
            )
        if (
            _proto_reduction_has_progress_variant(
                proto_reduction,
                "remove_power_coverage_elements_and_family_lookup_table",
            )
            and _proto_reduction_has_zero_branch_variant(
                proto_reduction,
                "remove_power_coverage_elements_and_family_lookup_table_first_700",
            )
            and _proto_reduction_has_zero_branch_variant(
                proto_reduction,
                "remove_power_coverage_elements_and_family_lookup_table_first_640",
            )
            and _proto_reduction_has_zero_branch_variant(
                proto_reduction,
                "remove_power_coverage_elements_and_family_lookup_table_first_512",
            )
            and _proto_reduction_has_zero_branch_variant(
                proto_reduction,
                "remove_power_coverage_elements_and_family_lookup_table_last_512",
            )
        ):
            findings.append(
                "forced_anchor_proto_reduction_full_lookup_table_required_for_progress"
            )
        if (
            _proto_reduction_has_progress_variant(
                proto_reduction,
                "remove_power_coverage_elements_and_family_lookup_table",
            )
            and _proto_reduction_has_zero_branch_variant(
                proto_reduction,
                "remove_power_coverage_element_active_and_family_lookup_table",
            )
            and _proto_reduction_has_zero_branch_variant(
                proto_reduction,
                "remove_power_coverage_element_x_and_family_lookup_table",
            )
            and _proto_reduction_has_zero_branch_variant(
                proto_reduction,
                "remove_power_coverage_element_y_and_family_lookup_table",
            )
            and _proto_reduction_has_zero_branch_variant(
                proto_reduction,
                "remove_power_coverage_element_xy_and_family_lookup_table",
            )
            and _proto_reduction_has_zero_branch_variant(
                proto_reduction,
                "remove_power_coverage_element_active_x_and_family_lookup_table",
            )
            and _proto_reduction_has_zero_branch_variant(
                proto_reduction,
                "remove_power_coverage_element_active_y_and_family_lookup_table",
            )
        ):
            findings.append(
                "forced_anchor_proto_reduction_all_element_targets_required_for_progress"
            )
    if (
        proto_reduction.get("outcome") == "proto_reduction_terminal_found"
        and list(proto_reduction.get("unlocking_variants", []))
    ):
        findings.append("forced_anchor_proto_reduction_terminal_unlock")
    if (
        proto_reduction.get("outcome") == "proto_reduction_terminal_found"
        and int(_mapping(proto_reduction.get("status_counts")).get("INFEASIBLE", 0)) > 0
        and int(_mapping(proto_reduction.get("status_counts")).get("UNKNOWN", 0)) > 0
        and int(proto_reduction.get("search_progress_unknown_count", 0)) > 0
        and int(proto_reduction.get("zero_branch_unknown_count", 0)) == 0
        and any("interval_delta" in str(profile_id) for profile_id in list(proto_reduction.get("profile_ids", [])))
    ):
        findings.append("standardized_delta_interval_terminal_progress_split")
    if (
        formulation_probe.get("classification")
        == "direct_bound_replacement_terminal_without_relaxing_semantics"
    ):
        findings.append("solver_friendly_direct_bound_formulation_terminal")
    if (
        formulation_probe.get("classification")
        == "direct_after_force_terminal_enforced_formulation_still_unknown"
    ):
        findings.append("direct_after_force_terminal_enforced_formulation_still_unknown")
    if (
        formulation_probe.get("classification")
        == "target_direct_terminal_enforced_unknown_all_family_direct_infeasible"
    ):
        findings.append("target_direct_terminal_all_family_direct_infeasible")
    if (
        formulation_probe.get("classification")
        in {
            "formulation_probe_inconclusive",
            "direct_bound_replacement_infeasible",
        }
        and str(formulation_probe.get("direct_status")) == "INFEASIBLE"
    ):
        findings.append("target_direct_bound_injection_infeasible")
    if (
        witness_audit.get("classification")
        == "geometric_power_coverage_witness_primary_blocker"
    ):
        findings.append("geometric_power_coverage_witness_primary_blocker")
    if (
        witness_audit.get("classification")
        == "power_coverage_full_skip_only_primary_blocker"
    ):
        findings.append("power_coverage_full_skip_only_primary_blocker")
    if (
        witness_audit.get("classification")
        == "power_coverage_partial_relaxation_model_invalid"
    ):
        findings.append("power_coverage_partial_relaxation_model_invalid")
    if bool(witness_audit.get("cover_choice_vars_complete", False)):
        findings.append("power_coverage_cover_choice_vars_match_powered_slots")
    if witness_domain.get("outcome") == "witness_domain_static_support_pass":
        findings.append("power_coverage_static_witness_domain_support_pass")
    if witness_domain.get("outcome") == "witness_domain_static_support_missing":
        findings.append("power_coverage_static_witness_domain_support_missing")
    if witness_domain.get("outcome") == "residual_optional_witness_domain_gaps_only":
        findings.append("power_coverage_residual_optional_witness_domain_gaps")
    if lookup_audit.get("outcome") == "shell_lookup_survivor_rows_consistent":
        findings.append("family_lookup_survivor_rows_consistent")
    if lookup_audit.get("outcome") == "shell_lookup_missing_survivor_rows":
        findings.append("family_lookup_missing_survivor_rows")
    if (
        capacity_gvi.get("classification")
        == "power_capacity_gvi_full_skip_primary_suspect"
    ):
        findings.append("power_capacity_gvi_full_skip_primary_suspect")
    if (
        capacity_gvi.get("classification")
        == "power_capacity_gvi_lower_bounds_not_sufficient"
    ):
        findings.append("power_capacity_gvi_lower_bounds_not_sufficient")
    if capacity_gvi.get("classification") == "power_capacity_gvi_relaxation_model_invalid":
        findings.append("power_capacity_gvi_relaxation_model_invalid")
    return _dedupe(findings)


def _proto_reduction_has_progress_variant(
    proto_reduction: Mapping[str, Any],
    variant: str,
) -> bool:
    for sample in list(proto_reduction.get("search_progress_unknown_samples", [])):
        if (
            str(_mapping(sample).get("variant")) == str(variant)
            and int(_mapping(sample).get("branches", 0)) > 0
        ):
            return True
    return False


def _proto_reduction_has_zero_branch_variant(
    proto_reduction: Mapping[str, Any],
    variant: str,
) -> bool:
    zero_by_variant = _mapping(proto_reduction.get("zero_branch_unknown_by_variant"))
    return int(zero_by_variant.get(str(variant), 0)) > 0


def _primary_hypothesis(findings: list[str]) -> str:
    if "power_capacity_gvi_relaxation_model_invalid" in findings:
        return "power_capacity_gvi_relaxation_model_invalid"
    if "power_coverage_partial_relaxation_model_invalid" in findings:
        return "power_coverage_partial_relaxation_model_invalid"
    if "power_capacity_gvi_lower_bounds_not_sufficient" in findings:
        return "power_family_count_or_conditioned_bounds_primary_suspect"
    if "power_capacity_gvi_full_skip_primary_suspect" in findings:
        return "power_capacity_gvi_full_skip_primary_suspect"
    if "power_coverage_full_skip_only_primary_blocker" in findings:
        return "power_coverage_full_skip_only_primary_blocker"
    if (
        "power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core"
        in findings
        and "forced_anchor_proto_reduction_full_lookup_table_required_for_progress"
        in findings
        and "family_lookup_semantic_repro_terminal_without_zero_branch" in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_channeling_still_unknown"
        in findings
    ):
        return "power_coverage_elements_full_family_lookup_table_required_progress_blocker"
    if (
        "power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core"
        in findings
        and "forced_anchor_proto_reduction_all_element_targets_required_for_progress"
        in findings
        and "family_lookup_semantic_repro_terminal_without_zero_branch" in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_channeling_still_unknown"
        in findings
    ):
        return "power_coverage_all_element_targets_family_lookup_table_progress_blocker"
    if (
        "power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core"
        in findings
        and "forced_anchor_proto_reduction_elements_lookup_table_progress"
        in findings
        and "family_lookup_semantic_repro_terminal_without_zero_branch" in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_channeling_still_unknown"
        in findings
    ):
        return "power_coverage_element_family_lookup_table_minimal_progress_blocker"
    if (
        "power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core"
        in findings
        and "family_lookup_search_probe_all_zero_branch_unknown" in findings
        and "family_lookup_assumption_probe_zero_branch_unknown" in findings
        and "family_lookup_semantic_repro_terminal_without_zero_branch" in findings
        and "forced_anchor_proto_reduction_search_progress" in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_channeling_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_membership_only_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_only_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only_still_unknown"
        in findings
    ):
        return "power_coverage_family_lookup_proto_reduction_progress_without_terminal"
    if (
        "power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core"
        in findings
        and "family_lookup_search_probe_all_zero_branch_unknown" in findings
        and "family_lookup_assumption_probe_zero_branch_unknown" in findings
        and "family_lookup_semantic_repro_terminal_without_zero_branch" in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_channeling_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_membership_only_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_only_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only_still_unknown"
        in findings
    ):
        return "power_coverage_family_lookup_micro_semantics_terminal_proto_reduction_needed"
    if (
        "power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core"
        in findings
        and "family_lookup_search_probe_all_zero_branch_unknown" in findings
        and "family_lookup_assumption_probe_zero_branch_unknown" in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_channeling_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_membership_only_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_only_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only_still_unknown"
        in findings
    ):
        return "power_coverage_family_lookup_assumption_split_still_zero_branch"
    if (
        "power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core"
        in findings
        and "family_lookup_search_probe_all_zero_branch_unknown" in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_channeling_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_membership_only_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_only_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only_still_unknown"
        in findings
    ):
        return "power_coverage_family_lookup_search_parameter_insensitive_zero_branch"
    if (
        "power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core"
        in findings
        and "family_lookup_search_probe_progress_without_terminal" in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_channeling_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_membership_only_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_only_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only_still_unknown"
        in findings
    ):
        return "power_coverage_family_lookup_search_progress_sensitivity"
    if (
        "power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core"
        in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_channeling_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_membership_only_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_only_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only_still_unknown"
        in findings
    ):
        return "power_coverage_family_lookup_rebuilt_components_all_zero_branch_blocked"
    if (
        "power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core"
        in findings
        and "power_coverage_dynamic_and_family_table_relaxation_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_linear_relaxation_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_sentinel_relaxation_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_membership_linear_relaxation_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_ordering_linear_relaxation_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_shell_pair_tables_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_lookup_rebuilt_channeling_still_unknown"
        in findings
    ):
        return "power_coverage_family_lookup_semantic_combo_rebuild_still_blocked"
    if (
        "power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core"
        in findings
        and "power_coverage_dynamic_and_family_table_relaxation_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_linear_relaxation_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_sentinel_relaxation_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_membership_linear_relaxation_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_ordering_linear_relaxation_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_shell_pair_tables_still_unknown"
        in findings
    ):
        return "power_coverage_family_lookup_table_linear_combo_not_redundant_channeling"
    if (
        "power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core"
        in findings
        and "power_coverage_dynamic_and_family_table_relaxation_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_linear_relaxation_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_sentinel_relaxation_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_membership_linear_relaxation_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_ordering_linear_relaxation_still_unknown"
        in findings
    ):
        return "power_coverage_family_lookup_table_full_linear_combination_blocker"
    if (
        "power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core"
        in findings
        and "power_coverage_dynamic_and_family_table_relaxation_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_linear_relaxation_still_unknown"
        in findings
    ):
        return "power_coverage_family_lookup_table_linear_combination_blocker"
    if (
        "power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core"
        in findings
        and "power_coverage_dynamic_and_family_distance_relaxation_still_unknown"
        in findings
        and "family_lookup_survivor_rows_consistent" in findings
        and "family_active_and_membership_channeling_still_unknown" in findings
    ):
        return "power_coverage_family_lookup_table_propagation_blocker"
    if (
        "power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core"
        in findings
        and "power_coverage_dynamic_and_family_distance_relaxation_still_unknown"
        in findings
        and "family_lookup_survivor_rows_consistent" in findings
    ):
        return "power_coverage_family_lookup_domain_strength_coupling_blocker"
    if (
        "power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core"
        in findings
        and "power_coverage_dynamic_and_family_distance_relaxation_still_unknown"
        in findings
    ):
        return "power_coverage_family_lookup_coupling_blocker"
    if (
        "power_coverage_dynamic_and_family_assignment_relaxation_unlocks_core"
        in findings
        and "power_coverage_dynamic_and_family_count_relaxation_still_unknown"
        in findings
        and "power_coverage_dynamic_and_family_membership_count_relaxation_still_unknown"
        in findings
    ):
        return "power_coverage_family_assignment_lookup_coupling_blocker"
    if (
        "power_coverage_dynamic_and_family_assignment_relaxation_unlocks_core"
        in findings
    ):
        return "power_coverage_family_assignment_coupling_blocker"
    if (
        "power_coverage_dynamic_family_assignment_and_gvi_relaxation_unlocks_core"
        in findings
    ):
        return "power_coverage_family_assignment_coupling_blocker"
    if (
        "geometric_power_coverage_witness_primary_blocker" in findings
        and "power_coverage_static_witness_domain_support_pass" in findings
    ):
        return "power_coverage_dynamic_coupling_blocker"
    if "geometric_power_coverage_witness_primary_blocker" in findings:
        return "geometric_power_coverage_witness_primary_blocker"
    if (
        "skip_power_coverage_unlocks_feasible_slice" in findings
        and (
            "target_family_relaxation_not_terminal_feasible" in findings
            or "target_family_relaxation_profile_infeasible" in findings
            or "target_direct_bound_injection_infeasible" in findings
        )
    ):
        return "power_coverage_core_primary_family_bound_injection_blocked"
    if (
        "target_family_relaxation_not_terminal_feasible" in findings
        or "target_family_relaxation_profile_infeasible" in findings
        or "target_direct_bound_injection_infeasible" in findings
    ):
        return "target_family_bound_slice_inconclusive_or_stale"
    if "target_direct_terminal_all_family_direct_infeasible" in findings:
        return "target_family_only_direct_bound_injection_candidate"
    if "direct_after_force_terminal_enforced_formulation_still_unknown" in findings:
        return "anchor_specialized_direct_bound_injection_candidate"
    if "solver_friendly_direct_bound_formulation_terminal" in findings:
        return "solver_friendly_conditioned_family_bound_formulation_candidate"
    if "bound_present_parameter_probe_all_zero_branch_unknown" in findings:
        return "target_conditioned_power_family_bound_formulation_sensitivity"
    if "bound_present_unknown_absent_terminal_without_violation" in findings:
        return "target_conditioned_power_family_bound_presolve_search_sensitivity"
    if "target_bound_solver_sensitivity_without_semantic_violation" in findings:
        return "target_conditioned_power_family_bound_solver_sensitivity"
    if (
        "target_power_family_bound_relaxation_unlocks_feasible_slice" in findings
        and "active_blocker_bound_is_consistently_derived" in findings
    ):
        return "target_conditioned_power_family_bound_is_consistent_active_blocker"
    if "target_power_family_bound_relaxation_unlocks_feasible_slice" in findings:
        return "target_conditioned_power_family_bound_is_active_blocker"
    required = {
        "zero_branch_unknown_reproduced",
        "conditioned_power_family_bounds_shift",
        "power_pole_candidate_domain_stable",
        "protocol_storage_box_domain_tightens",
        "skip_power_coverage_unlocks_feasible_slice",
    }
    if required.issubset(set(findings)):
        return "conditioned_power_family_bounds_interact_with_protocol_residuals"
    if "skip_power_coverage_unlocks_feasible_slice" in findings:
        return "power_coverage_core_is_primary_blocker_layer"
    if "protocol_storage_box_domain_tightens" in findings:
        return "protocol_residual_domain_tightening_is_primary_suspect"
    return "insufficient_artifact_join_evidence"


def _recommendation(hypothesis: str) -> str:
    if hypothesis == "power_capacity_gvi_relaxation_model_invalid":
        return (
            "Template-specific GVI relax slices are MODEL_INVALID after safe proto "
            "handling, so they cannot support a blocker conclusion. Keep final long "
            "run blocked and design a safer additive/guarded relaxation method before "
            "isolating power-capacity GVI rows."
        )
    if hypothesis == "power_coverage_partial_relaxation_model_invalid":
        return (
            "Partial power-coverage relax slices are MODEL_INVALID after safe proto "
            "handling. Keep using the full skip_power_coverage core slice as the "
            "reliable signal and design a safer relaxation method before promotion."
        )
    if hypothesis == "power_family_count_or_conditioned_bounds_primary_suspect":
        return (
            "Template-specific power-capacity lower-bound rows were relaxed and the "
            "forced-anchor slice remained INFEASIBLE, while full skip_power_coverage "
            "is terminal. Next isolate the remaining power-family count, family "
            "membership, and ghost-conditioned upper-bound layer; keep final long "
            "run blocked."
        )
    if hypothesis == "power_capacity_gvi_full_skip_primary_suspect":
        return (
            "Power-capacity GVI audit confirms that full skip_power_coverage is "
            "terminal only when the aggregated power-capacity lower-bound layer is "
            "also skipped. Next isolate the four template lower bounds in forced-anchor "
            "diagnostic slices; keep runtime promotion and final long run blocked."
        )
    if hypothesis == "power_coverage_full_skip_only_primary_blocker":
        return (
            "Power-coverage witness audit shows that partial witness active/geometry "
            "relaxations remain INFEASIBLE, while full skip_power_coverage is "
            "terminal. Next audit the power-capacity/global-valid-inequality layer "
            "also skipped by skip_power_coverage; keep runtime promotion and final "
            "long run blocked."
        )
    if hypothesis == "geometric_power_coverage_witness_primary_blocker":
        return (
            "Power-coverage witness audit confirms the geometric witness encoding "
            "invariants while the forced-anchor slice becomes terminal only when "
            "power coverage is removed. Next isolate anchor119 witness-domain "
            "feasibility; keep family-bound injection, runtime promotion, and final "
            "long run blocked."
        )
    if hypothesis == "power_coverage_dynamic_coupling_blocker":
        return (
            "Anchor119 witness-domain probing shows every powered slot has static "
            "power-pole witness support, so the blocker is not a simple empty "
            "cover-choice domain. Next isolate dynamic coupling between active pole "
            "selection, no-overlap, and witness choices; keep final long run blocked."
        )
    if hypothesis == "power_coverage_family_assignment_coupling_blocker":
        return (
            "Forced-anchor slices now show that relaxing power-coverage dynamic "
            "witness/no-overlap alone remains UNKNOWN, while relaxing that layer "
            "together with the power-family assignment/count layer reaches terminal "
            "OPTIMAL. GVI lower-bound relaxation does not add a distinct unlock. "
            "Next isolate the family assignment/count sublayer under active "
            "coverage coupling; keep final long run blocked."
        )
    if hypothesis == "power_coverage_family_assignment_lookup_coupling_blocker":
        return (
            "Forced-anchor sublayer slices show that dynamic coverage plus family "
            "count relaxation remains UNKNOWN, and dynamic coverage plus "
            "membership/count relaxation also remains UNKNOWN. Only the full "
            "family assignment layer relaxation reaches terminal OPTIMAL. The next "
            "suspect is the family__ lookup/shell-distance assignment encoding "
            "under active power-coverage coupling, not the aggregate count or "
            "membership totals alone."
        )
    if hypothesis == "power_coverage_family_lookup_coupling_blocker":
        return (
            "Forced-anchor lookup/distance slices show that dynamic coverage plus "
            "family__ lookup relaxation reaches terminal OPTIMAL, while dynamic "
            "coverage plus dx/dy/d_lo/d_hi distance relaxation remains UNKNOWN. "
            "The next suspect is the family__ assignment table/domain link under "
            "active power-coverage coupling; distance bounds alone are not the "
            "minimal unlock."
        )
    if hypothesis == "power_coverage_family_lookup_domain_strength_coupling_blocker":
        return (
            "Family lookup audit confirms that anchor119 surviving power-pole poses "
            "are covered by existing shell lookup rows, so the blocker is not a "
            "missing family__ table row. Combined with the lookup-relaxation slice, "
            "the current suspect is lookup table/domain propagation strength under "
            "active power-coverage coupling."
        )
    if hypothesis == "power_coverage_family_lookup_table_propagation_blocker":
        return (
            "Family lookup audit confirms survivor rows are present, and redundant "
            "active-domain plus membership-sum channeling still leaves the forced "
            "anchor at zero-branch UNKNOWN. Since relaxing family__ lookup unlocks "
            "OPTIMAL while simple channeling does not, the next suspect is the "
            "table propagation structure itself under active power-coverage coupling."
        )
    if hypothesis == "power_coverage_family_lookup_table_linear_combination_blocker":
        return (
            "Dynamic family lookup slices show that relaxing only the 763 family__ "
            "table constraints remains UNKNOWN, and relaxing only the 56,459 "
            "family__ linear constraints also remains UNKNOWN. The forced anchor "
            "reaches OPTIMAL only when both table and linear lookup/channeling "
            "constraints are relaxed together, so the current suspect is their "
            "combined propagation structure under active power coverage."
        )
    if hypothesis == "power_coverage_family_lookup_table_full_linear_combination_blocker":
        return (
            "Dynamic family linear-category slices show sentinel inactive, membership "
            "reification, family ordering, and all family__ linear constraints each "
            "remain zero-branch UNKNOWN when relaxed without the table. Table-only "
            "relaxation also remains UNKNOWN. Only relaxing table plus all family__ "
            "linear lookup/channeling constraints reaches OPTIMAL, so the blocker is "
            "the full table-linear propagation combination under active power coverage."
        )
    if hypothesis == "power_coverage_family_lookup_table_linear_combo_not_redundant_channeling":
        return (
            "Explicit redundant shell-pair tables add 26,705 enforced family->shell "
            "constraints but still leave the forced anchor at zero-branch UNKNOWN, "
            "even with dynamic coverage relaxed. Since only relaxing the original "
            "family__ table plus all family__ linear lookup/channeling constraints "
            "reaches OPTIMAL, the remaining suspect is a nontrivial interaction in "
            "the original table-linear encoding rather than a missing redundant "
            "family->shell channel."
        )
    if hypothesis == "power_coverage_family_lookup_semantic_combo_rebuild_still_blocked":
        return (
            "The alternative family lookup rebuild removes the original 57,222 "
            "family__ lookup constraints and adds 83,166 diagnostic replacement "
            "constraints, yet the forced anchor remains zero-branch UNKNOWN even "
            "with dynamic coverage relaxed. Since full family lookup relaxation is "
            "still the only terminal OPTIMAL unlock, the blocker now points at the "
            "semantic combination of family selection, shell-pair domain, and "
            "ordering under active power coverage rather than a missing row or a "
            "single weak channel."
        )
    if hypothesis == "power_coverage_family_lookup_rebuilt_components_all_zero_branch_blocked":
        return (
            "The rebuilt component split shows that even isolated family lookup "
            "semantics are zero-branch blockers under active power coverage: "
            "membership-only, shell-pair-only, ordering-only, all two-way rebuilds, "
            "and the full rebuild remain UNKNOWN, while full family lookup relaxation "
            "is OPTIMAL. The next diagnostic should stop adding equivalent channels "
            "and instead profile assumption splitting or solver search behavior on "
            "the membership, shell-pair, and ordering variables."
        )
    if hypothesis == "power_coverage_family_lookup_search_parameter_insensitive_zero_branch":
        return (
            "Family lookup search-parameter probing confirms the rebuilt component "
            "blocker is insensitive to the tested CP-SAT search modes: fixed, "
            "automatic, portfolio, low probing, and low symmetry all remain "
            "zero-branch/zero-conflict UNKNOWN. The next step should be explicit "
            "assumption splitting or a smaller semantic repro around membership, "
            "shell-pair, and ordering variables, not another search-profile tweak."
        )
    if hypothesis == "power_coverage_family_lookup_assumption_split_still_zero_branch":
        return (
            "Family lookup assumption splitting forced sampled family literals in "
            "membership and shell-pair rebuilt slices, but every sampled assumption "
            "still remained zero-branch/zero-conflict UNKNOWN. Together with the "
            "search-parameter probe, this points away from solver profile tuning "
            "and toward building a smaller semantic reproduction of the active "
            "power-coverage plus family lookup interaction."
        )
    if hypothesis == "power_coverage_family_lookup_micro_semantics_terminal_proto_reduction_needed":
        return (
            "The extracted micro semantic repro for active coverage plus family "
            "lookup solves terminally across coverage, membership, shell-pair, "
            "ordering, and full rebuilt variants. Because the full forced-anchor "
            "slice, search-parameter probe, and sampled assumption split all remain "
            "zero-branch UNKNOWN, the blocker now points to full-proto scale or "
            "constraint-family interaction. Next reduce the actual forced-anchor "
            "proto by constraint family rather than rewriting the basic semantics."
        )
    if hypothesis == "power_coverage_family_lookup_proto_reduction_progress_without_terminal":
        return (
            "Controlled full-proto reduction keeps the base forced anchor at "
            "zero-branch UNKNOWN, while removing the combined power-coverage dynamic "
            "and family-lookup constraints produces ordinary CP-SAT search progress "
            "without reaching terminal status. This confirms the blocker is a "
            "full-proto interaction between those constraint families; next bisect "
            "inside that combined removal to find the smallest progress-producing "
            "constraint subset."
        )
    if hypothesis == "power_coverage_element_family_lookup_table_minimal_progress_blocker":
        return (
            "Proto-reduction bisection found the smallest progress-producing subset "
            "so far: removing power-coverage Element constraints together with the "
            "family__ lookup table removes only 3,052 constraints and turns the "
            "forced anchor from zero-branch UNKNOWN into ordinary search progress. "
            "This points specifically at the interaction between cover_choice "
            "Element constraints and the family lookup table, not the larger "
            "family linear layer or no-overlap alone."
        )
    if hypothesis == "power_coverage_all_element_targets_family_lookup_table_progress_blocker":
        return (
            "Element-target proto bisection shows that removing family__ lookup "
            "table plus only cover_choice active, x, y, or any two of those Element "
            "target groups still leaves zero-branch UNKNOWN. Ordinary search "
            "progress appears only when all three cover_choice Element target "
            "groups are removed with the family lookup table. The blocker is now "
            "isolated to the full active/x/y cover_choice Element system interacting "
            "with family__ table lookup."
        )
    if hypothesis == "power_coverage_elements_full_family_lookup_table_required_progress_blocker":
        return (
            "Table-slot threshold probing shows that removing all cover_choice "
            "Element constraints plus first_700, first_640, first_512, first_384, "
            "last_512, or last_384 family lookup table constraints still leaves "
            "zero-branch UNKNOWN. Search progress appears only when all 763 "
            "family__ table constraints are removed with the Element system. The "
            "blocker now looks global across the family lookup table rather than "
            "localized to a small contiguous slot subset."
        )
    if hypothesis == "power_coverage_family_lookup_search_progress_sensitivity":
        return (
            "Family lookup search-parameter probing found at least one profile that "
            "branches or conflicts before timeout without reaching terminal status. "
            "Compare that profile against zero-branch profiles before changing "
            "formulation or runtime defaults."
        )
    if hypothesis == "power_coverage_core_primary_family_bound_injection_blocked":
        return (
            "Current model slices show that removing the power-coverage core turns "
            "the forced-anchor blocker terminal, while refreshed target-family "
            "relaxation/direct-bound slices are INFEASIBLE. Treat the older "
            "family-bound terminal evidence as stale, keep injection blocked, and "
            "focus the next diagnostic on the geometric power-coverage core."
        )
    if hypothesis == "target_family_bound_slice_inconclusive_or_stale":
        return (
            "Current refreshed target-family model slices no longer provide a "
            "terminal feasible relaxation or direct-bound replacement. Treat the "
            "older terminal family-bound evidence as stale, keep injection and "
            "runtime promotion blocked, and reconcile the model-slice mutation "
            "path before another B5A rerun."
        )
    if hypothesis == "conditioned_power_family_bounds_interact_with_protocol_residuals":
        return (
            "Before another B5A sprint, add a guarded diagnostic that isolates "
            "conditioned power-family upper bounds for the top shifted families and "
            "protocol-storage residual constraints; keep this diagnostic out of proof "
            "semantics until it turns UNKNOWN into a terminal explanation."
        )
    if hypothesis == "target_conditioned_power_family_bound_is_active_blocker":
        return (
            "The diagnostic slice shows that relaxing the target conditioned "
            "power-family bound unlocks a feasible core. Audit the derivation of "
            "that family bound and build a proof-safe verifier before any runtime "
            "promotion or B5A rerun."
        )
    if hypothesis == "target_conditioned_power_family_bound_is_consistent_active_blocker":
        return (
            "The target conditioned power-family bound is internally consistent "
            "across derivation, domain artifact, and proto, and relaxing it unlocks "
            "the forced-anchor core. Next audit whether this bound is semantically "
            "proof-safe or over-strong before any runtime promotion or B5A rerun."
        )
    if hypothesis == "target_conditioned_power_family_bound_solver_sensitivity":
        return (
            "The target conditioned power-family bound is internally consistent and "
            "relaxing it unlocks a feasible slice, but the relaxed solution does not "
            "violate the bound. Treat this as a solver/presolve sensitivity and "
            "compare bound-present versus bound-absent search behavior before any "
            "runtime promotion or B5A rerun."
        )
    if hypothesis == "target_conditioned_power_family_bound_presolve_search_sensitivity":
        return (
            "The bound-present slice remains UNKNOWN while removing one conditioned "
            "family bound solves quickly, without a bound violation in the relaxed "
            "solution. Treat this as confirmed presolve/search sensitivity; next try "
            "bound-present solver parameter probes or a redundant solver-friendlier "
            "formulation, not proof promotion."
        )
    if hypothesis == "target_conditioned_power_family_bound_formulation_sensitivity":
        return (
            "Bound-present parameter probes all remain zero-branch UNKNOWN, while "
            "removing one conditioned family bound solves quickly without a bound "
            "violation. Treat this as formulation-level solver sensitivity; next "
            "prototype a redundant or decomposed solver-friendlier encoding for the "
            "conditioned family bound, still outside proof promotion."
        )
    if hypothesis == "solver_friendly_conditioned_family_bound_formulation_candidate":
        return (
            "A diagnostic solver-friendly direct-bound formulation reaches terminal "
            "status without relaxing the forced-anchor bound. Next design a guarded "
            "runtime formulation experiment with proof-neutral equivalence checks; "
            "do not promote it to production or proof until fresh B5A evidence passes."
        )
    if hypothesis == "anchor_specialized_direct_bound_injection_candidate":
        return (
            "The direct-after-force diagnostic reaches terminal status, but the "
            "general enforced formulation still remains UNKNOWN. Next design an "
            "anchor-specialized solve-time direct-bound injection or deeper "
            "formulation experiment with proof-neutral equivalence checks; do not "
            "treat the generic enforced switch as validated."
        )
    if hypothesis == "target_family_only_direct_bound_injection_candidate":
        return (
            "The target-family direct-after-force diagnostic reaches terminal status, "
            "but the generic enforced formulation stays UNKNOWN and all-family direct "
            "substitution is INFEASIBLE. Next design a target-family-only, "
            "anchor-specialized solve-time injection with proof-neutral equivalence "
            "checks; broad substitution is explicitly not validated."
        )
    if hypothesis == "power_coverage_core_is_primary_blocker_layer":
        return (
            "Prioritize power-coverage core slicing before B5A rerun; current evidence "
            "does not yet isolate protocol residuals."
        )
    if hypothesis == "protocol_residual_domain_tightening_is_primary_suspect":
        return (
            "Prioritize protocol-storage residual domain diagnostics before changing "
            "power coverage or proof semantics."
        )
    return "Gather missing power-delta, residual-encoding, model-slice, and zero-branch artifacts."


def _next_actions(hypothesis: str) -> list[str]:
    if hypothesis == "power_capacity_gvi_relaxation_model_invalid":
        return [
            "design_safe_power_capacity_gvi_relaxation_method",
            "avoid_destructive_proto_constraint_deletion_for_gvi",
            "rerun_template_gvi_slices_after_model_validity_gate",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_coverage_partial_relaxation_model_invalid":
        return [
            "design_safe_power_coverage_relaxation_method",
            "avoid_destructive_proto_constraint_deletion_for_coverage",
            "rerun_partial_coverage_slices_after_model_validity_gate",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_family_count_or_conditioned_bounds_primary_suspect":
        return [
            "audit_power_family_count_membership_layer",
            "compare_ghost_conditioned_family_upper_bounds_with_gvi_relaxed",
            "build_forced_anchor_family_count_layer_slice",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_capacity_gvi_full_skip_primary_suspect":
        return [
            "add_template_specific_power_capacity_gvi_relax_slices",
            "test_protocol_storage_box_power_capacity_lower_bound_alone",
            "test_mandatory_manufacturing_power_capacity_lower_bounds",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_coverage_full_skip_only_primary_blocker":
        return [
            "audit_power_capacity_gvi_skipped_by_skip_power_coverage",
            "compare_power_capacity_lower_bounds_against_witness_domain",
            "build_minimal_power_capacity_gvi_repro",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "geometric_power_coverage_witness_primary_blocker":
        return [
            "isolate_anchor119_power_coverage_witness_domain_feasibility",
            "compare_cover_choice_idx_active_x_y_domains_for_blocker",
            "build_minimal_witness_domain_repro",
            "keep_family_bound_injection_blocked",
        ]
    if hypothesis == "power_coverage_dynamic_coupling_blocker":
        return [
            "build_power_coverage_dynamic_coupling_slice",
            "separate_active_pole_selection_from_no_overlap_pressure",
            "compare_witness_choice_domains_with_fixed_pole_counts",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_coverage_family_assignment_coupling_blocker":
        return [
            "split_power_family_assignment_from_count_constraints_under_dynamic_coverage",
            "compare_family_lookup_table_vs_shell_distance_constraints",
            "build_minimal_family_assignment_coverage_repro",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_coverage_family_assignment_lookup_coupling_blocker":
        return [
            "split_family_lookup_table_from_shell_distance_constraints",
            "compare_family__domain_table_against_dx_dy_dlo_dhi_constraints",
            "build_minimal_family_assignment_lookup_coverage_repro",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_coverage_family_lookup_coupling_blocker":
        return [
            "audit_family__assignment_table_rows_under_anchor119",
            "compare_family__domain_values_against_power_pole_pose_family_ids",
            "build_minimal_family_lookup_power_coverage_repro",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_coverage_family_lookup_domain_strength_coupling_blocker":
        return [
            "profile_family_lookup_table_propagation_under_dynamic_coverage",
            "build_minimal_family_lookup_power_coverage_repro",
            "test_redundant_family_domain_channeling_constraints",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_coverage_family_lookup_table_propagation_blocker":
        return [
            "build_minimal_family_lookup_table_power_coverage_repro",
            "test_split_shell_lookup_table_into_implication_channeling",
            "compare_table_encoding_with_explicit_shell_family_cases",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_coverage_family_lookup_table_linear_combination_blocker":
        return [
            "build_minimal_family_lookup_table_linear_repro",
            "split_family_linear_constraints_by_sentinel_membership_ordering",
            "test_explicit_shell_family_case_encoding_against_table_linear_combo",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_coverage_family_lookup_table_full_linear_combination_blocker":
        return [
            "build_minimal_family_lookup_table_linear_repro",
            "replace_shell_lookup_table_with_explicit_implication_channeling_in_diagnostic",
            "compare_explicit_family_case_encoding_against_table_linear_combo",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_coverage_family_lookup_table_linear_combo_not_redundant_channeling":
        return [
            "build_minimal_family_lookup_table_linear_repro",
            "test_alternative_exact_family_lookup_encoding_without_original_table",
            "compare_original_table_linear_encoding_against_rebuilt_case_encoding",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_coverage_family_lookup_semantic_combo_rebuild_still_blocked":
        return [
            "build_minimal_family_lookup_semantic_combo_repro",
            "split_rebuilt_family_lookup_semantics_by_membership_shell_ordering",
            "test_anchor119_family_case_branching_or_assumption_splitting",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_coverage_family_lookup_rebuilt_components_all_zero_branch_blocked":
        return [
            "build_minimal_rebuilt_family_lookup_component_repro",
            "profile_assumption_splitting_on_membership_shell_ordering_variables",
            "probe_zero_branch_solver_search_parameters_on_ordering_only_slice",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_coverage_family_lookup_search_parameter_insensitive_zero_branch":
        return [
            "build_minimal_rebuilt_family_lookup_component_repro",
            "implement_diagnostic_assumption_split_on_family_lookup_literals",
            "compare_membership_shell_ordering_assumption_groups",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_coverage_family_lookup_assumption_split_still_zero_branch":
        return [
            "extract_minimal_active_coverage_family_lookup_repro",
            "reduce_family_lookup_slots_and_families_to_smallest_zero_branch_case",
            "compare_proto_size_and_constraint_families_before_and_after_reduction",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_coverage_family_lookup_micro_semantics_terminal_proto_reduction_needed":
        return [
            "reduce_actual_forced_anchor_proto_by_constraint_family",
            "bisect_power_coverage_family_lookup_proto_constraints",
            "compare_zero_branch_status_after_proto_constraint_deletions",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_coverage_family_lookup_proto_reduction_progress_without_terminal":
        return [
            "bisect_combined_power_coverage_dynamic_family_lookup_removal",
            "separate_progress_effect_by_coverage_element_linear_no_overlap",
            "separate_progress_effect_by_family_lookup_table_linear_categories",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_coverage_element_family_lookup_table_minimal_progress_blocker":
        return [
            "bisect_power_coverage_element_constraints_against_family_lookup_table",
            "split_cover_choice_idx_active_x_y_elements",
            "split_family_lookup_table_by_slot_or_shell_family_rows",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_coverage_all_element_targets_family_lookup_table_progress_blocker":
        return [
            "split_family_lookup_table_by_slot_or_shell_family_rows",
            "test_all_element_targets_against_family_lookup_table_subsets",
            "compare_cover_choice_element_reformulation_without_table_lookup_change",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_coverage_elements_full_family_lookup_table_required_progress_blocker":
        return [
            "test_sparse_family_lookup_table_removal_patterns",
            "prototype_family_lookup_table_reformulation_without_element_changes",
            "prototype_cover_choice_element_reformulation_without_table_deletion",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_coverage_family_lookup_search_progress_sensitivity":
        return [
            "compare_progress_search_profile_against_zero_branch_profiles",
            "rerun_progress_profile_on_single_ordering_slice_with_longer_budget",
            "keep_runtime_defaults_unchanged_until_terminal_evidence",
            "keep_final_long_run_blocked",
        ]
    if hypothesis == "power_coverage_core_primary_family_bound_injection_blocked":
        return [
            "audit_anchor119_power_coverage_witness_encoding",
            "build_power_coverage_core_slice_matrix",
            "compare_power_coverage_witness_domains_for_family009_and_protocol_storage_box",
            "keep_family_bound_injection_blocked",
        ]
    if hypothesis == "target_family_bound_slice_inconclusive_or_stale":
        return [
            "reconcile_stale_target_family_bound_slice_artifacts",
            "audit_model_slice_proto_mutation_equivalence",
            "rerun_current_forced_anchor_slice_matrix",
            "keep_anchor_specialized_injection_blocked",
        ]
    if hypothesis == "conditioned_power_family_bounds_interact_with_protocol_residuals":
        return [
            "profile_top_shifted_power_family_bounds",
            "add_diagnostic_only_family_bound_relaxation_slice",
            "compare_protocol_storage_box_residual_constraints",
            "rerun_small_forced_anchor_matrix_only_after_slice_is_terminal",
        ]
    if hypothesis == "target_conditioned_power_family_bound_is_active_blocker":
        return [
            "audit_target_family_bound_derivation",
            "build_proof_safe_family_bound_verifier",
            "rerun_forced_anchor_matrix_after_verifier",
            "keep_runtime_promotion_blocked_until_terminal_evidence",
        ]
    if hypothesis == "target_conditioned_power_family_bound_is_consistent_active_blocker":
        return [
            "audit_family_bound_semantic_soundness",
            "compare_blocked_pole_cells_against_power_coverage_reachability",
            "build_proof_safe_family_bound_verifier",
            "keep_runtime_promotion_blocked_until_terminal_evidence",
        ]
    if hypothesis == "target_conditioned_power_family_bound_solver_sensitivity":
        return [
            "compare_bound_present_vs_absent_presolve",
            "try_targeted_search_parameters_with_bound_present",
            "capture_solver_response_stats_for_family009_bound",
            "keep_runtime_promotion_blocked_until_terminal_evidence",
        ]
    if hypothesis == "target_conditioned_power_family_bound_presolve_search_sensitivity":
        return [
            "run_bound_present_parameter_probe",
            "test_fixed_vs_portfolio_search_on_anchor119",
            "prototype_redundant_solver_friendly_family_bound_encoding",
            "keep_runtime_promotion_blocked_until_terminal_evidence",
        ]
    if hypothesis == "target_conditioned_power_family_bound_formulation_sensitivity":
        return [
            "prototype_solver_friendly_conditioned_family_bound_encoding",
            "compare_reified_linear_vs_indicator_bound_formulations",
            "rerun_anchor119_bound_present_slice_after_formulation_probe",
            "keep_runtime_promotion_blocked_until_terminal_evidence",
        ]
    if hypothesis == "solver_friendly_conditioned_family_bound_formulation_candidate":
        return [
            "design_guarded_runtime_formulation_experiment",
            "add_equivalence_tests_for_conditioned_family_bounds",
            "rerun_b5a_workspace_after_guarded_experiment",
            "keep_proof_and_release_promotion_blocked",
        ]
    if hypothesis == "anchor_specialized_direct_bound_injection_candidate":
        return [
            "design_anchor_specialized_direct_bound_injection",
            "add_equivalence_tests_for_forced_anchor_bound_substitution",
            "rerun_anchor119_base_slice_with_injection",
            "keep_generic_enforced_switch_unpromoted",
        ]
    if hypothesis == "target_family_only_direct_bound_injection_candidate":
        return [
            "design_target_family_only_direct_bound_injection",
            "prove_single_family_substitution_equivalence_under_forced_anchor",
            "rerun_anchor119_slice_with_target_only_injection",
            "keep_all_family_substitution_blocked",
        ]
    if hypothesis == "power_coverage_core_is_primary_blocker_layer":
        return ["add_power_coverage_core_slice", "rerun_zero_branch_triage"]
    if hypothesis == "protocol_residual_domain_tightening_is_primary_suspect":
        return ["add_protocol_residual_slice", "rerun_zero_branch_triage"]
    return ["rebuild_missing_diagnostic_artifacts"]


def _checks(
    power_delta: Mapping[str, Any],
    residual: Mapping[str, Any],
    zero_branch: Mapping[str, Any],
    model_slice: Mapping[str, Any],
    family_audit: Mapping[str, Any],
    semantic_audit: Mapping[str, Any],
    solver_profile: Mapping[str, Any],
    parameter_probe: Mapping[str, Any],
    formulation_probe: Mapping[str, Any],
    lookup_search_probe: Mapping[str, Any],
    lookup_assumption_probe: Mapping[str, Any],
    lookup_semantic_repro: Mapping[str, Any],
    proto_reduction: Mapping[str, Any],
    witness_audit: Mapping[str, Any],
    witness_domain: Mapping[str, Any],
    lookup_audit: Mapping[str, Any],
    capacity_gvi: Mapping[str, Any],
) -> list[Dict[str, str]]:
    optional = _optional_delta_by_template(power_delta)
    findings = set(
        _findings(
            power_delta,
            residual,
            zero_branch,
            model_slice,
            family_audit,
            semantic_audit,
            solver_profile,
            parameter_probe,
            formulation_probe,
            lookup_search_probe,
            lookup_assumption_probe,
            lookup_semantic_repro,
            proto_reduction,
            witness_audit,
            witness_domain,
            lookup_audit,
            capacity_gvi,
        )
    )
    return [
        _check(
            "power_coverage_anchor_delta_present",
            "pass" if bool(power_delta.get("present", False)) else "fail",
            "power delta loaded"
            if bool(power_delta.get("present", False))
            else str(power_delta.get("load_error")),
        ),
        _check(
            "residual_optional_encoding_present",
            "pass" if bool(residual.get("present", False)) else "fail",
            "residual optional encoding loaded"
            if bool(residual.get("present", False))
            else str(residual.get("load_error")),
        ),
        _check(
            "zero_branch_unknown_triage_present",
            "pass" if bool(zero_branch.get("present", False)) else "fail",
            "zero-branch triage loaded"
            if bool(zero_branch.get("present", False))
            else str(zero_branch.get("load_error")),
        ),
        _check(
            "model_slice_reports_present",
            "pass" if bool(model_slice.get("present", False)) else "fail",
            f"report_count={int(model_slice.get('report_count', 0))}",
        ),
        _check(
            "zero_branch_unknown_present",
            "pass" if int(zero_branch.get("zero_branch_unknown_count", 0)) > 0 else "fail",
            f"zero_branch_unknown_count={int(zero_branch.get('zero_branch_unknown_count', 0))}",
        ),
        _check(
            "power_family_bounds_shift_present",
            "pass" if int(power_delta.get("power_family_changed_count", 0)) > 0 else "fail",
            f"changed_count={int(power_delta.get('power_family_changed_count', 0))}",
        ),
        _check(
            "power_pole_candidate_domain_stable",
            "pass"
            if int(_mapping(optional.get("power_pole")).get("surviving_delta", 0)) == 0
            else "fail",
            f"delta={int(_mapping(optional.get('power_pole')).get('surviving_delta', 0))}",
        ),
        _check(
            "protocol_storage_box_domain_tightens",
            "pass"
            if int(_mapping(optional.get("protocol_storage_box")).get("surviving_delta", 0)) < 0
            else "fail",
            f"delta={int(_mapping(optional.get('protocol_storage_box')).get('surviving_delta', 0))}",
        ),
        _check(
            "power_coverage_slice_unlocks_core",
            "pass" if "skip_power_coverage_unlocks_feasible_slice" in findings else "fail",
            "skip power coverage slice is feasible/optimal"
            if "skip_power_coverage_unlocks_feasible_slice" in findings
            else "no unlocking power-coverage slice finding",
        ),
        _check(
            "target_power_family_bound_relaxation_unlocks_core",
            "pass"
            if "target_power_family_bound_relaxation_unlocks_feasible_slice" in findings
            else "skipped",
            "target family bound relaxation is feasible/optimal"
            if "target_power_family_bound_relaxation_unlocks_feasible_slice" in findings
            else "target family bound relaxation slice not present",
        ),
        _check(
            "family_bound_audit_consistent",
            "pass"
            if bool(family_audit.get("bounds_consistent", False))
            else "skipped",
            "family bound derivation/domain/proto agree"
            if bool(family_audit.get("bounds_consistent", False))
            else "family bound audit not present or inconsistent",
        ),
        _check(
            "family_bound_semantic_audit_present",
            "pass" if bool(semantic_audit.get("present", False)) else "skipped",
            str(semantic_audit.get("classification"))
            if bool(semantic_audit.get("present", False))
            else "family-bound semantic audit not present",
        ),
        _check(
            "family_bound_solver_profile_present",
            "pass" if bool(solver_profile.get("present", False)) else "skipped",
            str(solver_profile.get("classification"))
            if bool(solver_profile.get("present", False))
            else "family-bound solver profile not present",
        ),
        _check(
            "family_bound_parameter_probe_present",
            "pass" if bool(parameter_probe.get("present", False)) else "skipped",
            str(parameter_probe.get("outcome"))
            if bool(parameter_probe.get("present", False))
            else "family-bound parameter probe not present",
        ),
        _check(
            "family_bound_formulation_probe_present",
            "pass" if bool(formulation_probe.get("present", False)) else "skipped",
            str(formulation_probe.get("classification"))
            if bool(formulation_probe.get("present", False))
            else "family-bound formulation probe not present",
        ),
        _check(
            "family_lookup_search_probe_present",
            "pass" if bool(lookup_search_probe.get("present", False)) else "skipped",
            str(lookup_search_probe.get("outcome"))
            if bool(lookup_search_probe.get("present", False))
            else "family lookup search probe not present",
        ),
        _check(
            "family_lookup_assumption_probe_present",
            "pass"
            if bool(lookup_assumption_probe.get("present", False))
            else "skipped",
            str(lookup_assumption_probe.get("outcome"))
            if bool(lookup_assumption_probe.get("present", False))
            else "family lookup assumption probe not present",
        ),
        _check(
            "family_lookup_semantic_repro_present",
            "pass" if bool(lookup_semantic_repro.get("present", False)) else "skipped",
            str(lookup_semantic_repro.get("outcome"))
            if bool(lookup_semantic_repro.get("present", False))
            else "family lookup semantic repro not present",
        ),
        _check(
            "forced_anchor_proto_reduction_present",
            "pass" if bool(proto_reduction.get("present", False)) else "skipped",
            str(proto_reduction.get("outcome"))
            if bool(proto_reduction.get("present", False))
            else "forced-anchor proto reduction not present",
        ),
        _check(
            "power_coverage_witness_audit_present",
            "pass" if bool(witness_audit.get("present", False)) else "skipped",
            str(witness_audit.get("classification"))
            if bool(witness_audit.get("present", False))
            else "power-coverage witness audit not present",
        ),
        _check(
            "power_coverage_witness_domain_present",
            "pass" if bool(witness_domain.get("present", False)) else "skipped",
            str(witness_domain.get("outcome"))
            if bool(witness_domain.get("present", False))
            else "power-coverage witness-domain probe not present",
        ),
        _check(
            "family_lookup_assignment_audit_present",
            "pass" if bool(lookup_audit.get("present", False)) else "skipped",
            str(lookup_audit.get("outcome"))
            if bool(lookup_audit.get("present", False))
            else "family lookup assignment audit not present",
        ),
        _check(
            "power_capacity_gvi_audit_present",
            "pass" if bool(capacity_gvi.get("present", False)) else "skipped",
            str(capacity_gvi.get("classification"))
            if bool(capacity_gvi.get("present", False))
            else "power-capacity GVI audit not present",
        ),
    ]


def _candidate(
    power_delta: Mapping[str, Any],
    residual: Mapping[str, Any],
    zero_branch: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "key": power_delta.get("candidate_key")
        or residual.get("candidate_key")
        or zero_branch.get("candidate_key")
    }


def _next_probe_family(power_delta: Mapping[str, Any]) -> Optional[str]:
    top = list(power_delta.get("top_power_family_deltas", []))
    if top and isinstance(top[0], Mapping):
        family = top[0].get("family")
        return str(family) if family is not None else None
    return None


def _next_probe_template(power_delta: Mapping[str, Any]) -> Optional[str]:
    optional = _optional_delta_by_template(power_delta)
    protocol = _mapping(optional.get("protocol_storage_box"))
    if int(protocol.get("surviving_delta", 0)) < 0:
        return "protocol_storage_box"
    return None


def _optional_delta_by_template(power_delta: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    return {
        str(entry.get("template")): entry
        for entry in list(power_delta.get("optional_template_deltas", []))
        if isinstance(entry, Mapping) and entry.get("template") is not None
    }


def _float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _load_model_slice_reports(slice_dirs: Sequence[Path]) -> list[Dict[str, Any]]:
    reports: list[Dict[str, Any]] = []
    for slice_dir in slice_dirs:
        if not slice_dir.exists() or not slice_dir.is_dir():
            continue
        for path in sorted(slice_dir.glob("*.json")):
            payload, error = _load_json_mapping(path)
            if not isinstance(payload, Mapping):
                continue
            reports.append({"path": path, "payload": payload, "load_error": error})
    return reports


def _load_json_mapping(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not path.exists():
        return None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"json_load_error:{type(exc).__name__}:{exc}"
    if not isinstance(payload, Mapping):
        return None, "json_payload_not_object"
    return dict(payload), None


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_list(value: Any) -> list[Dict[str, Any]]:
    return [dict(entry) for entry in list(value or []) if isinstance(entry, Mapping)]


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
