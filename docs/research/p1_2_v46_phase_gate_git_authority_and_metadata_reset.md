# P1.2 V46 phase-gate Git authority and metadata reset

Package: v46_candidate
Date: 2026-06-08
Baseline reviewed: `zmd_22.7z`
Baseline archive SHA256: `5AC8255BB93CF299FF96481806CE7C957CBA9E30590568182E5925624618FBA1`
Baseline archive size: `157479435` bytes
Baseline Git HEAD: `648ede596cd7f7d6365d84dd56aa8a3caee19b26`

The V46 clean review candidate was not clean. It found three reset-grade sibling bypasses in the P1.2 phase-gate provenance surface after the V45 reset fixes. The consecutive-clean counter remains 0/3 and the review anchor advances to `v46_candidate`.

## Reset findings

1. Git authority control files still skipped dangling symlinks. `_git_control_file_text()` checked `exists()` before `_check_git_authority_path()`, so broken symlinks at `.git/config`, `.git/config.worktree`, and `.git/gitdir` were accepted as missing instead of rejected fail-closed while `current_review_package.source_head` was being validated.

2. Git promisor and partial-clone object authority could lazy-fetch source objects from outside the review package. `_project_git_head()` used sanitized config and replacement-ref settings, but did not set `GIT_NO_LAZY_FETCH=1` and did not reject local `remote.*.promisor`, `partialclonefilter`, `extensions.partialClone`, or `.git/objects/pack/*.promisor` authority. A fake worktree could point `refs/heads/master` at a commit absent from local objects and let Git fetch it from a sibling promisor remote during the source-head check.

3. Evidence metadata markup filtering still accepted XML/SVG/MathML payload and attribute wrappers. Clean-review evidence with a stale visible identity such as `<![CDATA[Package: zmd_18.7z]]>`, `<!-- Package: zmd_18.7z -->`, `<?review Package: zmd_18.7z ?>`, or `<svg data-package="zmd_18.7z"></svg>` could coexist with later plain current package metadata and still produce a closed/ready gate.

## Machine-enforced closure added

The patch makes the phase gate fail closed for these cases by:

- checking Git authority control paths for symlinks and junctions before any missing-path skip;
- rejecting include/includeIf plus promisor/partial-clone Git config authority in `.git/config` and `.git/config.worktree`;
- rejecting `.git/objects/pack/*.promisor` markers and setting `GIT_NO_LAZY_FETCH=1` for the source-head Git subprocesses;
- rejecting metadata keys hidden in CDATA, comments, processing instructions, and markup attributes before ordinary line metadata is accepted.

The following tests are required by `PO-PHASE-GATE-PROVENANCE` and exercise the new fail-closed behavior:

- `test_validator_rejects_broken_git_authority_control_file_symlink_for_source_head_authority`
- `test_validator_rejects_git_promisor_remote_for_source_head_authority`
- `test_validator_rejects_git_promisor_pack_marker_for_source_head_authority`
- `test_project_git_env_disables_lazy_fetch`
- `test_validator_rejects_xml_payload_and_attribute_wrapped_metadata_conflicts`

## Phase-gate state

`data/review_gates/phase_1_2_spike_close.json` remains blocked with `consecutive_clean_full_reviews_after_reset = 0`, `remaining_clean_full_reviews = 3`, `current_review_anchor = v46_candidate`, and `next_phase_entry.allowed = false`. P1.3B entry remains blocked until three consecutive independent full reviews after `v46_candidate` are clean.
