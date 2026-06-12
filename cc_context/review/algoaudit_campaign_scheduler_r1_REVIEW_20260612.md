# IndustrialPlanner certified evidence persistence review

Scope: independent review of `zmd_f78_snapshot_1ebcc03b.zip` only.

Snapshot gate: `sha256sum /mnt/data/zmd_f78_snapshot_1ebcc03b.zip` matched `1ebcc03bf93cfd980286392e39e10c02f48c8393cf1d5df108f0b1eaf42527f4`. No other snapshot package was used.

Reviewed surfaces:

- 面 A: `src/search/exact_campaign.py`, specifically `load_or_create`, `_validate_resume_state`, `_validate_candidate_record`, `mark_candidate_started`, `mark_candidate_result`, bound/running proof summary update helpers, `mark_campaign_stopped`, `best_certified_result`, `save`, `atomic_write_json`, and the terminal-certified validation family.
- 面 B: `src/search/exact_parallel_scheduler.py` worker dispatch/result merge, queue drain/respawn/error paths, and `src/search/outer_search.py` parallel wave consumption before writing results into the campaign.

## Finding F-01 — HIGH: stale candidate `solution` could survive a status rewrite and certify the wrong run

Files: `src/search/exact_campaign.py:1421-1426`, `src/search/exact_campaign.py:1997-2128`.

The original `mark_candidate_started` copied any existing candidate record into a new RUNNING record without removing `solution`. The original `mark_candidate_result` removed `solution` only when the incoming status was not `CERTIFIED`; therefore a later `CERTIFIED` result with `solution=None` preserved the old `solution`. `_validate_candidate_record` required a solution for `CERTIFIED`, but did not reject a solution on `RUNNING`/`UNKNOWN`/`UNPROVEN`/`INFEASIBLE`, so a stale witness could cross a resume boundary.

Impact: a previous certified candidate witness could be reused by a later run that did not supply a fresh witness. Once terminal frontier evidence was attached, the stale solution could satisfy the terminal consistency checks because the record still looked like `CERTIFIED` with a solution. This is a false-CERTIFIED direction because the persisted evidence is stronger than the latest candidate result actually carried.

Pre-fix probe:

```bash
cd /mnt/data/zmd_review_work/project
python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from src.tests.test_v89_terminal_ghost_pick_protocol_validation import _write_project
from src.tests.certified_frontier_helpers import attach_terminal_frontier_evidence
from src.search.exact_campaign import ExactCampaign, validate_exact_campaign_resume_state, TERMINAL_FULL_FRONTIER_CERTIFIED_REASON
from src.models.cut_manager import RUN_STATUS_CERTIFIED

with TemporaryDirectory() as td:
    root = Path(td) / 'project'
    _write_project(root)
    camp = ExactCampaign.load_or_create(root, campaign_hours=1.0, resume=False)
    stale_solution = {
        'solid_001': {'facility_type': 'solid', 'pose_idx': 0},
        'ghost_pick': {'anchor': {'x': 1, 'y': 0}},
    }
    camp.mark_candidate_started(2, 3)
    camp.mark_candidate_result(2, 3, RUN_STATUS_CERTIFIED, solution=stale_solution, proof_summary={'old':'cert'}, exact_safe_cuts=[], loaded_exact_safe_cut_count=0, generated_exact_safe_cut_count=0)
    camp.mark_candidate_started(2, 3)
    print('after start status=', camp.get_candidate_record(2,3)['status'], 'solution_present=', 'solution' in camp.get_candidate_record(2,3))
    camp.mark_candidate_result(2, 3, RUN_STATUS_CERTIFIED, solution=None, proof_summary={'new':'certified_without_solution'}, exact_safe_cuts=[], loaded_exact_safe_cut_count=0, generated_exact_safe_cut_count=0)
    rec = camp.get_candidate_record(2,3)
    print('after result status=', rec['status'], 'solution=', rec.get('solution'))
    camp.state['final_result'] = {
        'search_status': RUN_STATUS_CERTIFIED,
        'ghost_rect': {'w': 2, 'h': 3, 'area': 6, 'anchor_x': 1, 'anchor_y': 0},
        'placement_solution': {'solid_001': {'facility_type': 'solid', 'pose_idx': 0}},
        'search_stats': {'campaign_resumed': False},
    }
    camp.mark_campaign_stopped(TERMINAL_FULL_FRONTIER_CERTIFIED_REASON, status=RUN_STATUS_CERTIFIED)
    attach_terminal_frontier_evidence(camp, root, min_side=1, fill_unresolved_better_candidates_as_infeasible=True)
    reason = validate_exact_campaign_resume_state(camp.state, camp.artifact_hashes, project_root=root)
    print('resume validation reason=', reason)
    print('best_certified_result exists=', camp.best_certified_result() is not None)
PY
```

Observed pre-fix output:

```text
after start status= RUNNING solution_present= True
after result status= CERTIFIED solution= {'solid_001': {'facility_type': 'solid', 'pose_idx': 0}, 'ghost_pick': {'anchor': {'x': 1, 'y': 0}}}
resume validation reason= None
best_certified_result exists= True
```

Fix:

- Added `STRONG_CANDIDATE_STATUSES = {CERTIFIED, INFEASIBLE}`.
- `_validate_candidate_record` now rejects `solution` on any non-`CERTIFIED` status: `candidate_non_certified_solution_present:<key>`.
- `mark_candidate_started` no-ops on an existing same-artifact strong result, preventing a rerun preamble from downgrading a terminal proof to `RUNNING`. For weak records it explicitly removes any `solution`.
- `mark_candidate_result` now validates status up front, requires a fresh mapping for every incoming `CERTIFIED`, rejects solutions on non-`CERTIFIED`, rejects contradictory strong statuses (`CERTIFIED` vs `INFEASIBLE`), and blocks strong-to-weak downgrades with an audit event instead of overwriting the strong record.
- Added regression tests in `src/tests/test_exact_campaign_state_soundness.py` and updated the older v63 negative test so invalid “certified without solution” states are now produced by direct state tampering, not by the public writer API.

Post-fix probe result:

```text
after start status= CERTIFIED solution_present= True
fresh_solution_guard= CERTIFIED candidate result requires a fresh solution mapping
after weak downgrade status= CERTIFIED
tamper_resume_validation= candidate_non_certified_solution_present:2x3
```

## Finding F-02 — HIGH: parallel wave merge trusted `dispatch_seq` without binding it to the dispatched candidate

Files: `src/search/exact_parallel_scheduler.py:79-135`, `src/search/exact_parallel_scheduler.py:452-550`, `src/search/outer_search.py:115-160`, `src/search/outer_search.py:2193-2363`.

The original scheduler collected `WorkerResult` objects into `results_by_seq` by `dispatch_seq` only. Crash-drain/final-drain paths used `setdefault`, so the first object for a sequence won. There was no check that the result’s `attempt_index`, `(area, w, h)`, or derived `candidate_key` matched the `WorkerTask` originally sent for that sequence. A malformed or stale queue payload could therefore make a wave appear complete while carrying a result for a different candidate.

The consumer side in `outer_search` then matched the result back to `solve_wave_entries` by `worker_result.candidate_key`; if there was no match, it fell back to `selection_reason='prune_fill'` and still called `mark_candidate_result` for the result’s candidate. That meant the queue boundary could inject a candidate result that was never dispatched in the wave.

Pre-fix scheduler probe:

```bash
cd /mnt/data/zmd_review_work/project
python - <<'PY'
import queue
from src.search.exact_parallel_scheduler import ExactParallelWorkerPool, WorkerTask, WorkerResult

class FakeTaskQueue:
    def put(self, item):
        pass

class FakeResultQueue:
    def __init__(self, messages):
        self.messages = list(messages)
    def get(self, timeout=None):
        if not self.messages:
            raise queue.Empty()
        return self.messages.pop(0)
    def get_nowait(self):
        raise queue.Empty()

tasks = [
    WorkerTask(0, 1, (9,3,3), 1,1,1,1,1, False, tuple()),
    WorkerTask(1, 2, (4,2,2), 1,1,1,1,1, False, tuple()),
]
messages = [
    {'message_type': 'RESULT', 'result': WorkerResult(0, 1, (1,1,1), 'INFEASIBLE', None, {}, [], 0, 0, 0.0, 1, None)},
    {'message_type': 'RESULT', 'result': WorkerResult(1, 2, (4,2,2), 'INFEASIBLE', None, {}, [], 0, 0, 0.0, 1, None)},
]
pool = ExactParallelWorkerPool.__new__(ExactParallelWorkerPool)
pool._closed = False
pool._started = True
pool._processes = []
pool._task_queue = FakeTaskQueue()
pool._result_queue = FakeResultQueue(messages)
pool.rss_sample_interval_seconds = 0.01
pool._total_crash_respawns = 0
pool.start = lambda: None
pool._respawn_all_workers = lambda: None
pool.terminate = lambda: None
pool._sum_process_tree_rss = lambda: 0
wave = ExactParallelWorkerPool.run_wave(pool, tasks)
print('completed=', wave.completed)
print('dispatched=', wave.dispatched_candidate_keys)
print('results=', [(r.dispatch_seq, r.candidate_key) for r in wave.results])
PY
```

Observed pre-fix output:

```text
completed= True
dispatched= ('3x3', '2x2')
results= [(0, '1x1'), (1, '2x2')]
```

Fix:

- `ExactParallelWorkerPool.run_wave` now builds a unique `tasks_by_seq` map per wave.
- All result collection paths use `_record_worker_result`, which checks `dispatch_seq`, `attempt_index`, `candidate`, and `candidate_key` against the original `WorkerTask`, rejects duplicate dispatch sequences, rejects invalid status/solution combinations, and drops errored results instead of returning them as proof-bearing outputs.
- `outer_search` now independently revalidates every `ParallelWaveExecution.results` entry against the `tasks` it just dispatched before writing to the campaign. If the wave object is malformed, the effective wave is `completed=False`, telemetry records the failure reason, no mismatched result is written, and the campaign is stopped as `worker_process_failed`/`UNKNOWN`.
- Added regressions in `src/tests/test_parallel_scheduler.py`: scheduler candidate mismatch, errored strong result dropped, and consumer-side candidate mismatch rejected.

Post-fix probe result:

```text
mismatch completed= False failure= worker_result_candidate_mismatch:0 results= [(1, '2x2')]
error completed= False failure= RuntimeError: synthetic crash results= ()
```

The valid `2x2` sibling can still be retained after a malformed queue item if it independently passes identity validation. The invalid `1x1` result is not retained and cannot be written into the campaign. `outer_search` additionally drops all results from a malformed wave object before campaign writes, which is the safer consumer-side stance.

## Additional soundness checks with no new finding

`resume` hash compatibility is fail-closed. `compute_exact_artifact_hashes` covers the required exact artifacts and the optional `rules/preprocess_plan.json`; when the optional file is absent the state carries the sentinel `__MISSING_OPTIONAL_EXACT_ARTIFACT__`. `_validate_resume_state` compares the stored `artifact_hashes` dict with the freshly computed dict by exact equality, so missing/extra/new optional keys and sentinel/hash changes produce `artifact_hash_mismatch` rather than a stronger resume.

`atomic_write_json` is structurally fail-closed for crash consistency: it writes a same-directory temp file, flushes and fsyncs the file, uses `os.replace`, then best-effort fsyncs the directory. On restart, `load_or_create` parses with strict JSON duplicate-key/constant rejection; unreadable or partial JSON becomes `state_json_invalid` and resets instead of resuming a half-written stronger state. Linux gets the directory fsync path; Windows-style directory fsync failures are best-effort, but a torn payload still fails strict JSON/resume validation.

`mark_candidate_started` crash behavior remains safe. A weak candidate started and then crashed is `RUNNING` with `finished_at=None`; `_validate_candidate_record` accepts it as non-terminal, and frontier computation treats it as unresolved/potential, so it is rerun rather than treated as completed. After the fix, a weak RUNNING record cannot carry a stale `solution`.

Terminal export remains guarded. `best_certified_result` returns only after `has_valid_terminal_full_frontier_certified_evidence_for_project`, which requires strict declare mode, `final_status=CERTIFIED`, `last_stop_reason.reason=search_exhausted_all_candidates`, terminal frontier evidence, final candidate record status `CERTIFIED`, solution equality, project-level layout validation, and ghost-pick binding. `mark_campaign_stopped` clears terminal frontier evidence whenever the stop is not the strict full-frontier certified stop.

Partial worker failure remains fail-closed. Completed sibling results may be persisted only if they pass task/result identity validation. The campaign is then stopped as `worker_process_failed` with `UNKNOWN`, so terminal export is blocked even though completed sibling progress is preserved for resume.

`best_certified_result` objective agrees with `max_lex(area, min_side)`: terminal-frontier code uses candidate objective `(area, min(w,h))`, and terminal validation rejects a final certified result if any other certified candidate has a better objective.

Engineering-only fields remain outside the proof surface. Heartbeats, external/internal RSS stats, and telemetry append failures are not consumed by terminal evidence; telemetry append is best-effort and exceptions are captured without mutating the campaign proof state.

## Frozen artifact clause

No frozen/canonical artifacts were changed. This patch touches only Python code and tests:

- `src/search/exact_campaign.py`
- `src/search/exact_parallel_scheduler.py`
- `src/search/outer_search.py`
- `src/tests/test_exact_campaign_state_soundness.py`
- `src/tests/test_parallel_scheduler.py`
- `src/tests/test_v63_terminal_evidence_contract.py`

No regeneration step is required, no expected artifact sha256/byte-size changes are introduced, and no registration locations need same-batch updates (`FROZEN_ARTIFACTS`, `EXACT_HASH_FILES` family, `PROJECT_LOCK`, and `specs` unchanged).

## Validation run

Environment: Python 3.13.5, dependencies installed offline from `zmd_py313_linux_x86_64.zip` with `pip install --no-index --find-links ... -r requirements.txt`.

Passed:

```bash
python -m py_compile \
  src/search/exact_campaign.py \
  src/search/exact_parallel_scheduler.py \
  src/search/outer_search.py \
  src/tests/test_exact_campaign_state_soundness.py \
  src/tests/test_parallel_scheduler.py

python -m pytest -q --randomly-dont-reset-seed \
  src/tests/test_exact_campaign_state_soundness.py \
  src/tests/test_parallel_scheduler.py
# 15 passed

python -m pytest -q --randomly-dont-reset-seed \
  src/tests/test_exact_campaign_state_soundness.py \
  src/tests/test_exact_campaign_bound_state.py \
  src/tests/test_exact_campaign_inspector.py \
  src/tests/test_parallel_scheduler.py \
  src/tests/test_preprocess_plan_exact_hash.py \
  src/tests/test_v63_terminal_evidence_contract.py \
  src/tests/test_v84_terminal_layout_max_empty_rect.py \
  src/tests/test_v85_terminal_required_optionals.py \
  src/tests/test_v86_terminal_power_witness_validation.py \
  src/tests/test_v87_terminal_ghost_anchor_validation.py \
  src/tests/test_v88_terminal_ghost_anchor_required.py \
  src/tests/test_v89_terminal_ghost_pick_protocol_validation.py \
  src/tests/test_v91_terminal_nested_public_field_validation.py \
  src/tests/test_v94_terminal_protocol_storage_surplus_validation.py \
  src/tests/test_v95_terminal_optional_metadata_validation.py \
  src/tests/test_v97_canonical_campaign_state_authority.py
# 94 passed

python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored
```

Notes:

- A default pytest invocation hit an environment/plugin reseeding error in `pytest-randomly`/NumPy/Thinc before test bodies ran. The scoped validation was therefore run with `--randomly-dont-reset-seed`.
- Full `python -m pytest -q --randomly-dont-reset-seed src/tests` was not completed; an earlier attempt timed out at 600 seconds. I did not claim full-suite green.
