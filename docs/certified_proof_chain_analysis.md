# Certified Proof Chain Analysis

> **HISTORICAL SNAPSHOT (2026-06-19; superseded for current behavior).** This file preserves a pre-PR1
> write-point audit and intentionally retains the code excerpts and line numbers observed then. In the
> 2026-07-11 working tree, `outer_search` is a producer that commits `CANDIDATE_PROPOSED` only;
> `ExactCampaign.supervisor_seal()` is the sole durable terminal `CERTIFIED` mint, and
> `publish_verified_certified_delivery_surface()` is the sole canonical publisher. Use `NAV_MAP.md`,
> `specs/11_pipeline_orchestration.md`, and `docs/exact_campaign_operations.md` for current behavior.

<!-- codex session 2026-06-19 -->

Scope:
- `src/search/outer_search.py`
- `src/search/benders_loop.py`
- `src/search/exact_campaign.py`

Focus:
- `CERTIFIED` result construction path.
- All proof-bearing field write points found in these files.
- `outer_search` terminal full-frontier commit logic.

Notes:
- Repository root had no `.codegraph/`, so evidence was gathered by direct file reads and `rg`.
- The project root did not contain an `AGENTS.md` file on disk at inspection time; the user-provided instructions were used.

## 1. `src/search/outer_search.py`

### Write Point Index

| Function | Lines | Writes / emits |
|---|---:|---|
| `_mark_certified_campaign_blocked` | 176 | Clears `state["final_result"]`, `state["final_status"]`, `state["terminal_frontier_evidence"]`; then writes `last_stop_reason`/`final_status` through `mark_campaign_stopped(..., status=UNPROVEN)`. |
| `_compute_exact_frontier_state` | 624 | Reads candidate records and recognizes `status == CERTIFIED`; selects `best_certified_candidate` / `best_certified_record`. |
| `_build_certified_result` | 833 | Constructs public result and writes `search_status = RUN_STATUS_CERTIFIED`. |
| `_commit_terminal_full_frontier_certified_result` | 868 | Writes terminal proof-bearing campaign state: `final_result`, `final_status`, `last_stop_reason`, `terminal_frontier_evidence`; validates project-bound terminal evidence before saving. |
| `_build_campaign_result_payload` | 960 | Builds candidate `proof_summary` envelope from Benders/precheck metadata plus frontier metrics and safe-cut counts. |
| `_campaign_payload_from_run_metadata` | 1309 | Reads `run_benders_for_ghost_rect.last_run_metadata["proof_summary"]` and safe-cut fields into campaign payload. |
| `_campaign_payload_from_precheck_proof` | 1326 | Reads pre-master `proof_summary` into campaign payload. |
| `_augment_campaign_payload_with_selection` | 1343 | Adds `selection_reason` and optional `frontier_probe` proof fields. |
| `_record_precheck_elimination` | 1517 | Writes precheck INFEASIBLE candidate result with `proof_summary` via `ExactCampaign.mark_candidate_result`. |
| `_candidate_result_entry` | 1599 | Writes telemetry entry `status` and `proof_summary`. |
| `run_outer_search` | 1691 | Main caller for candidate commits and terminal commit. |

### Key Complete Excerpts

`_build_certified_result` lines 833-865:

```python
def _build_certified_result(
    *,
    candidate: Tuple[int, int, int],
    solution: Dict[str, Any],
    attempts: int,
    solve_mode: str,
    campaign_resumed: bool,
    frontier_peak_size: int,
    derived_pruned_candidates: int,
    frontier_selection_policy: str,
    frontier_candidate_metrics: Mapping[str, Any],
) -> Dict[str, Any]:
    area, ghost_w, ghost_h = candidate
    ghost_rect = {"w": ghost_w, "h": ghost_h, "area": area}
    ghost_anchor = _ghost_anchor_from_solution(solution)
    if ghost_anchor is not None:
        ghost_rect["anchor_x"] = int(ghost_anchor[0])
        ghost_rect["anchor_y"] = int(ghost_anchor[1])
    return {
        "ghost_rect": ghost_rect,
        "placement_solution": _placement_solution_without_ghost_marker(solution),
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {
            "attempts": attempts,
            "explicit_candidate_solves": attempts,
            "solve_mode": solve_mode,
            "campaign_resumed": campaign_resumed,
            "frontier_peak_size": frontier_peak_size,
            "derived_pruned_candidates": derived_pruned_candidates,
            "frontier_selection_policy": str(frontier_selection_policy),
            "frontier_candidate_metrics": dict(frontier_candidate_metrics),
        },
    }
```

`_commit_terminal_full_frontier_certified_result` lines 868-895:

```python
def _commit_terminal_full_frontier_certified_result(
    exact_campaign: ExactCampaign,
    result: Mapping[str, Any],
    *,
    candidates: Sequence[Tuple[int, int, int]],
    candidate_generation: Mapping[str, Any],
) -> None:
    exact_campaign.state["final_result"] = dict(result)
    exact_campaign.state["final_status"] = RUN_STATUS_CERTIFIED
    exact_campaign.mark_campaign_stopped(
        TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
        status=RUN_STATUS_CERTIFIED,
    )
    exact_campaign.state["terminal_frontier_evidence"] = build_terminal_frontier_evidence(
        candidates=candidates,
        candidate_records=exact_campaign.state.get("candidates", {}),
        final_result=result,
        candidate_generation=candidate_generation,
    )
    if not has_valid_terminal_full_frontier_certified_evidence_for_project(
        exact_campaign.state,
        project_root=exact_campaign.project_root,
    ):
        raise RuntimeError(
            "terminal certified_exact export attempted before project-bound full-frontier evidence was committed"
        )
    exact_campaign.save()
```

Candidate proof envelope lines 960-981:

```python
def _build_campaign_result_payload(...):
    proof_summary = dict(proof_summary)
    return {
        "proof_summary": {
            "search_attempts": attempts,
            "frontier_selection_policy": str(frontier_selection_policy),
            "frontier_candidate_metrics": dict(frontier_candidate_metrics),
            **proof_summary,
        },
        "exact_safe_cuts": [dict(raw_cut) for raw_cut in exact_safe_cuts],
        "loaded_exact_safe_cut_count": int(loaded_exact_safe_cut_count),
        "generated_exact_safe_cut_count": int(generated_exact_safe_cut_count),
    }
```

Terminal path in `run_outer_search` lines 1870-1937:

```python
if not frontier_state["potential_domain"]:
    if exact_campaign is not None and not _declare_mode_is_strict(exact_campaign):
        blocker = _non_strict_terminal_certified_blocker(exact_campaign)
        _mark_certified_campaign_blocked(...)
        return RUN_STATUS_UNPROVEN, None

    best_candidate = frontier_state["best_certified_candidate"]
    best_record = frontier_state["best_certified_record"]
    if best_candidate is not None and isinstance(best_record, dict):
        best_proof_summary = dict(best_record.get("proof_summary", {}))
        result = _build_certified_result(
            candidate=best_candidate,
            solution=dict(best_record.get("solution", {})),
            attempts=solve_attempts,
            solve_mode=solve_mode,
            campaign_resumed=exact_campaign.resumed if exact_campaign is not None else False,
            frontier_peak_size=frontier_peak_size,
            derived_pruned_candidates=int(frontier_state["derived_pruned_candidates"]),
            frontier_selection_policy=str(best_proof_summary.get("frontier_selection_policy", FRONTIER_SELECTION_POLICY)),
            frontier_candidate_metrics=dict(best_proof_summary.get("frontier_candidate_metrics", {})),
        )
        try:
            if exact_campaign is not None:
                _commit_terminal_full_frontier_certified_result(
                    exact_campaign,
                    result,
                    candidates=candidates,
                    candidate_generation=candidate_generation,
                )
            _save_final_result(project_root, result, facility_pools=facility_pools)
            if exact_campaign is not None:
                _refresh_certified_delivery_manifest_if_any(...)
        except Exception as exc:
            if exact_campaign is None:
                raise
            _mark_certified_campaign_blocked(... reason="terminal_certified_export_failed" ...)
            return RUN_STATUS_UNPROVEN, None
        return RUN_STATUS_CERTIFIED, result
```

Parallel candidate `CERTIFIED` write lines 2397-2413:

```python
elif (
    worker_result.status == RUN_STATUS_CERTIFIED
    and worker_result.solution is not None
):
    exact_campaign.mark_candidate_result(
        ghost_w,
        ghost_h,
        RUN_STATUS_CERTIFIED,
        exact_safe_cuts=payload["exact_safe_cuts"],
        solution=worker_result.solution,
        proof_summary=payload["proof_summary"],
        loaded_exact_safe_cut_count=payload["loaded_exact_safe_cut_count"],
        generated_exact_safe_cut_count=payload["generated_exact_safe_cut_count"],
    )
```

Serial candidate `CERTIFIED` write lines 2625-2638:

```python
if status == RUN_STATUS_CERTIFIED and solution is not None:
    if exact_campaign is not None:
        exact_campaign.mark_candidate_result(
            ghost_w,
            ghost_h,
            RUN_STATUS_CERTIFIED,
            exact_safe_cuts=campaign_payload["exact_safe_cuts"],
            solution=solution,
            proof_summary=campaign_payload["proof_summary"],
            loaded_exact_safe_cut_count=campaign_payload["loaded_exact_safe_cut_count"],
            generated_exact_safe_cut_count=campaign_payload["generated_exact_safe_cut_count"],
        )
```

### Required Inputs To Reach Terminal `CERTIFIED`

`run_outer_search` must read:
- `solve_mode == "certified_exact"`.
- No unsafe certified master-domain env blockers.
- `exact_campaign.state["declare_mode"] == "strict"`.
- `frontier_state["potential_domain"]` empty.
- `frontier_state["best_certified_candidate"]` present.
- `frontier_state["best_certified_record"]` is a dict from `exact_campaign.state["candidates"][candidate_key]`.
- That best record must contain `status == CERTIFIED`, `solution` mapping, and `proof_summary` with optional `frontier_selection_policy` / `frontier_candidate_metrics`.
- `candidates` full generated frontier and `candidate_generation` are passed to terminal evidence builder.
- `has_valid_terminal_full_frontier_certified_evidence_for_project(...)` must accept the just-written state.

Candidate-level `CERTIFIED` is only an incumbent: outer writes it via `mark_candidate_result`, then loops until the whole frontier is exhausted before calling terminal commit.

## 2. `src/search/benders_loop.py`

### Write Point Index

| Function | Lines | Writes / emits |
|---|---:|---|
| `_publish_last_run_metadata` | 1527 | Writes `run_benders_for_ghost_rect.last_run_metadata["proof_summary"]`, safe cuts, counts, and projected proof fields. |
| `_merge_reuse_metadata` | 2266 | Adds reuse/timing fields into proof summaries. |
| `_maybe_build_anchor119_row_domain_runtime_precheck_result` | 752 | Returns INFEASIBLE pre-master proof payload. |
| `_mandatory_rectangle_precheck_proof_summary` | 2442 | Builds pre-master INFEASIBLE proof summary. |
| `_coordinate_validation_precheck_proof_summary` | 2659 | Builds coordinate-validation INFEASIBLE proof summary. |
| `evaluate_exact_candidate_pre_master_precheck` | 2735 | Returns `{"status": INFEASIBLE, "proof_summary": ...}` for supported pre-master eliminations. |
| `LBBDController.__init__` | 3130 / 3171 | Initializes `self.last_proof_summary = {}`. |
| `LBBDController._run_exploratory` | 4680 | Writes exploratory `last_proof_summary`; emits `RUN_STATUS_CERTIFIED` when flow diagnostic is `FEASIBLE`. |
| `LBBDController._run_certified_exact` | 4771 | Writes certified `last_proof_summary` for master/power/max-iteration outcomes; returns `CERTIFIED` only from binding+routing result. |
| `LBBDController._run_power_placement_subproblem` | 5501 | Writes power subproblem `proof_summary` into persisted Benders cut. |
| `LBBDController._run_exact_binding_and_routing` | 5749 | Main proof producer for binding/routing; terminal `CERTIFIED` write is `last_proof_summary` with master/binding/routing all `FEASIBLE`. |
| `_record_unexpected_binding_status` | 7240 | Writes fail-closed `last_proof_summary`. |
| `_record_unexpected_routing_precheck_status` | 7282 | Writes fail-closed `last_proof_summary`. |
| `_record_unexpected_routing_build_domain_status` | 7324 | Writes fail-closed `last_proof_summary`. |
| `_add_exact_persisted_nogood` | 7404 | Writes `BendersCut(... proof_summary=dict(proof_summary), source_mode="certified_exact", exact_safe=True, ...)`. |
| `_add_exact_whole_layout_nogood` | 7452 | Delegates proof summary to `_add_exact_persisted_nogood`. |
| `run_benders_for_ghost_rect` | 7503 | Writes running heartbeat proof summary; publishes final proof metadata for outer. |

### Key Complete Excerpts

Metadata export lines 1527-1548:

```python
def _publish_last_run_metadata(...):
    normalized_proof_summary = dict(proof_summary)
    run_benders_for_ghost_rect.last_run_metadata = {
        "proof_summary": normalized_proof_summary,
        "exact_safe_cuts": [cut.to_dict() for cut in exact_safe_cuts],
        "loaded_exact_safe_cut_count": int(loaded_exact_safe_cut_count),
        "generated_exact_safe_cut_count": int(generated_exact_safe_cut_count),
        "persisted_exact_safe_cut_replay_input_count": int(persisted_exact_safe_cut_replay_input_count),
        "persisted_exact_safe_cut_replay_enabled": bool(persisted_exact_safe_cut_replay_enabled),
        ...
    }
```

Certified routing success lines 6927-6944:

```python
if routing_status == "FEASIBLE":
    self.last_proof_summary = {
        "mode": "certified_exact",
        "benders_iterations": iteration,
        "master_status": "FEASIBLE",
        "binding_status": "FEASIBLE",
        "routing_status": "FEASIBLE",
        "diagnostic_flow_status": diagnostic_flow_status,
        "enumerated_bindings": enumerated_bindings,
        "routing_attempts": routing_attempts,
        "binding_summary": binding_model.extract_conflict_summary(),
        "routing_summary": dict(routing_model.build_stats),
        **self._exact_warm_start_summary(),
        **self._subproblem_reuse_summary(),
        **self._routing_shrink_summary(),
        **self._exact_cut_ladder_summary(),
    }
    return RUN_STATUS_CERTIFIED, solution
```

Certified path handoff lines 5326-5338:

```python
result_status, certified_solution = self._run_exact_binding_and_routing(...)
if result_status == _EXACT_INTERNAL_STATUS_MASTER_CUT_ADDED_CONTINUE:
    continue
if result_status == RUN_STATUS_CERTIFIED:
    return RUN_STATUS_CERTIFIED, certified_solution
if result_status == RUN_STATUS_INFEASIBLE:
    return RUN_STATUS_INFEASIBLE, None
if result_status == RUN_STATUS_UNKNOWN:
    return RUN_STATUS_UNKNOWN, None
```

Persisted safe-cut proof commit lines 7418-7434:

```python
cut = BendersCut(
    schema_version=3 if condition_set else 2,
    cut_type=cut_type,
    conflict_set={str(k): int(v) for k, v in conflict_set.items()},
    iteration=iteration,
    metadata=dict(metadata or {}),
    source_mode="certified_exact",
    exact_safe=True,
    artifact_hashes=dict(self.artifact_hashes),
    proof_stage=proof_stage,
    binding_exhausted=binding_exhausted,
    routing_exhausted=routing_exhausted,
    proof_summary=dict(proof_summary),
    created_at=now_iso(),
    epsilon_stage=self.epsilon_stage,
    condition_set={str(k): v for k, v in (condition_set or {}).items()},
)
```

Final metadata publish lines 8165-8196:

```python
status, solution = controller.run_with_status()
binding_summary = dict(controller.last_proof_summary.get("binding_summary", {}))
proof_summary = _merge_reuse_metadata(
    {
        **dict(controller.last_proof_summary),
        **controller._master_search_summary(),
        "binding_search_profile": str(...),
        **controller._routing_shrink_summary(),
    },
    used_exact_core_reuse=used_exact_core_reuse,
    core_build_seconds=core_build_seconds,
    overlay_build_seconds=overlay_build_seconds,
    ghost_constraint_seconds=ghost_constraint_seconds,
    cut_replay_seconds=cut_replay_seconds,
)
_publish_last_run_metadata(
    proof_summary,
    [*loaded_exact_safe_cuts, *controller.generated_exact_safe_cuts],
    loaded_exact_safe_cut_count=len(loaded_exact_safe_cuts),
    generated_exact_safe_cut_count=len(controller.generated_exact_safe_cuts),
    persisted_exact_safe_cut_replay_input_count=persisted_cut_replay_input_count,
    persisted_exact_safe_cut_replay_enabled=False,
)
return status, solution
```

### Required Inputs To Reach `CERTIFIED`

For certified exact:
- `run_benders_for_ghost_rect` must be called with `solve_mode == "certified_exact"`.
- Env/domain blockers must be absent.
- Exact session must match project root, solve mode, and master search profile.
- Area precheck and pre-master elimination must not return INFEASIBLE.
- `MasterPlacementModel` must solve to `OPTIMAL` or `FEASIBLE` and extract a non-empty solution.
- If power placement subproblem is enabled, it must return `"FEASIBLE"` and provide a witness-compatible updated solution, or the path fails closed.
- Binding model must build and solve with `binding_status == "FEASIBLE"`.
- Routing precheck status must be within verified statuses and pass consistency/safe-reject checks.
- Routing model build must have no duplicate terminal-front keys, no non-feasible domain analysis status, and no port-adherence blocked ports.
- Routing solver must return `"FEASIBLE"`.
- The resulting `last_proof_summary` is exported through `_publish_last_run_metadata`, then outer_search reads it.

## 3. `src/search/exact_campaign.py`

### Write Point Index

| Function | Lines | Writes / validates |
|---|---:|---|
| `_candidate_defaults` | 1513 | Initializes candidate `status="UNKNOWN"`, `proof_summary={}`, safe-cut counts, `bound_state`. |
| `_build_initial_state` | 1530 | Initializes campaign `final_result=None`, `final_status=None`, `last_stop_reason=None`, `terminal_frontier_evidence=None`, `declare_mode="strict"`, `proof_summary_schema_version`. |
| `_sanitize_resume_state_for_untrusted_infeasible_evidence` | 1567 | Downgrades checkpoint-loaded `INFEASIBLE` to `UNKNOWN`, replaces `proof_summary` with replay-required audit summary, clears terminal certified state. |
| `_validate_candidate_record` | 1638 | Validates `CERTIFIED` records must have `solution`, non-CERTIFIED must not, `proof_summary` must be mapping, safe cuts must be certified exact safe cuts. |
| `_validate_resume_state` | 1725 | Validates final state consistency and calls terminal evidence validators. |
| `has_certified_export_surface` | 1865 | Detects certified-looking state. |
| `has_terminal_full_frontier_certified_evidence` | 1876 | Requires strict declare mode, `final_status=CERTIFIED`, `final_result`, and terminal stop reason. |
| `terminal_certified_final_result_violation` | 1894 | Replays final result against candidate record and terminal frontier evidence. |
| `has_valid_terminal_full_frontier_certified_evidence_for_project` | 2046 | Project-bound validator used by outer commit and export gate. |
| `ExactCampaign.load_or_create` | 2091 | Loads/validates/sanitizes resume state or builds initial state. |
| `update_candidate_bound_state` | 2204 | Writes proof-adjacent `bound_state` fields. |
| `mark_candidate_started` | 2285 | Writes `status="RUNNING"` and clears stale `solution`; does not downgrade strong statuses. |
| `mark_candidate_result` | 2316 | Main candidate proof commit: writes `status`, `proof_summary`, safe cuts, counts, and `solution` for `CERTIFIED`. |
| `update_candidate_running_proof_summary` | 2425 | Merges heartbeat/running proof summary into running candidate record. |
| `mark_campaign_stopped` | 2450 | Writes `last_stop_reason` and `final_status`; clears terminal evidence unless terminal certified reason/status. |
| `best_certified_result` | 2467 | Export gate: returns final result only after project-bound terminal evidence validation; forces `search_status="CERTIFIED"` in copy. |
| `save` | 2480 | Atomic JSON write of campaign state. |

### Key Complete Excerpts

Candidate commit lines 2316-2423:

```python
def mark_candidate_result(...):
    normalized_status = str(status)
    if normalized_status not in VALID_CANDIDATE_STATUSES:
        raise ValueError(...)
    if normalized_status == "CERTIFIED" and not isinstance(solution, Mapping):
        raise ValueError("CERTIFIED candidate result requires a fresh solution mapping")
    if normalized_status != "CERTIFIED" and solution is not None:
        raise ValueError("non-CERTIFIED candidate result must not carry a solution")
    ...
    record["status"] = normalized_status
    record["updated_at"] = timestamp
    record["finished_at"] = timestamp
    ...
    record["proof_summary"] = dict(proof_summary or {})
    record["exact_safe_cuts"] = [dict(cut) for cut in exact_safe_cuts]  # when provided
    record["loaded_exact_safe_cut_count"] = ...
    record["generated_exact_safe_cut_count"] = ...
    if normalized_status == "CERTIFIED":
        record["solution"] = dict(solution)
        if str(self.state.get("declare_mode")) != "strict":
            record["proof_summary"] = dict(record.get("proof_summary", {}))
            record["proof_summary"]["final_result_blocked_reason"] = (
                "final_result_requires_strict_declare_mode"
            )
    else:
        record.pop("solution", None)

    candidates[key] = record
    self.state["updated_at"] = timestamp
```

Campaign stop/final status lines 2450-2465:

```python
def mark_campaign_stopped(self, reason: str, status: Optional[str] = None) -> None:
    timestamp = now_iso()
    stop_record = {
        "reason": str(reason),
        "status": None if status is None else str(status),
        "updated_at": timestamp,
    }
    self.state["last_stop_reason"] = stop_record
    if status is not None:
        self.state["final_status"] = str(status)
    if (
        str(stop_record.get("status")) != "CERTIFIED"
        or str(stop_record.get("reason")) != TERMINAL_FULL_FRONTIER_CERTIFIED_REASON
    ):
        self.state["terminal_frontier_evidence"] = None
    self.state["updated_at"] = timestamp
```

Terminal evidence predicate lines 1876-1891:

```python
def has_terminal_full_frontier_certified_evidence(state: Mapping[str, Any]) -> bool:
    if str(state.get("declare_mode")) != "strict":
        return False
    if str(state.get("final_status")) != "CERTIFIED":
        return False
    if not isinstance(state.get("final_result"), Mapping):
        return False
    stop_record = state.get("last_stop_reason")
    if not isinstance(stop_record, Mapping):
        return False
    return (
        str(stop_record.get("status")) == "CERTIFIED"
        and str(stop_record.get("reason")) == TERMINAL_FULL_FRONTIER_CERTIFIED_REASON
    )
```

Terminal replay validator core lines 1918-1989:

```python
if str(final_result.get("search_status", "")) != "CERTIFIED":
    return "terminal_certified_final_result_status_invalid"
...
record = candidates.get(key)
...
if str(record.get("status", "")) != "CERTIFIED":
    return "terminal_certified_candidate_record_not_certified"
record_solution = record.get("solution")
if not isinstance(record_solution, Mapping):
    return "terminal_certified_candidate_solution_missing"
if _solution_without_ghost_marker(record_solution) != _solution_without_ghost_marker(placement_solution):
    return "terminal_certified_final_result_solution_mismatch"
...
frontier_reason = terminal_frontier_evidence_violation(
    evidence=state.get("terminal_frontier_evidence"),
    candidate_records=candidates,
    final_result=final_result,
    grid_dimensions=grid_dimensions,
    safe_area_upper_bound=safe_area_upper_bound,
    min_side_admissibility=min_side_admissibility,
)
if frontier_reason is not None:
    return frontier_reason
```

Export gate lines 2467-2478:

```python
def best_certified_result(self) -> Optional[Dict[str, Any]]:
    if not has_valid_terminal_full_frontier_certified_evidence_for_project(
        self.state,
        project_root=self.project_root,
    ):
        return None
    result = self.state.get("final_result")
    if not isinstance(result, dict):
        return None
    result_copy = dict(result)
    result_copy["search_status"] = "CERTIFIED"
    return result_copy
```

### Required Inputs For Certified Export / Commit

Candidate commit requires:
- Incoming `status` in `VALID_CANDIDATE_STATUSES`.
- If incoming status is `CERTIFIED`, incoming `solution` must be a mapping.
- If incoming status is not `CERTIFIED`, incoming `solution` must be absent.
- Existing strong candidate status cannot be contradicted or downgraded.
- `proof_summary`, safe cuts, loaded/generated counts come from outer_search payload.

Terminal export requires:
- `declare_mode == "strict"`.
- `final_status == "CERTIFIED"`.
- `final_result` mapping with `search_status == "CERTIFIED"`.
- `last_stop_reason.status == "CERTIFIED"` and reason exactly `search_exhausted_all_candidates`.
- Candidate record for final ghost size exists and has `status == "CERTIFIED"` plus `solution`.
- Public placement solution matches candidate solution after removing `ghost_pick`.
- `terminal_frontier_evidence` validates against full candidate records and candidate generation domain.
- Project-bound solution validator accepts mandatory instances, optional lower bounds, pose metadata, geometry, power coverage, ghost anchor, and no better empty rectangle.

