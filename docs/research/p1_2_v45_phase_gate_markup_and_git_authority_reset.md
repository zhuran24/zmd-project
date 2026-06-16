# P1.2 V45 phase-gate markup and Git authority reset

Package: v45_candidate

The V45 clean review against `zmd_21.7z` / HEAD `5e5a7e658cb362c01502913e182e5a27d44b397b` found three reset-grade sibling bypasses in the V44 reset families. The consecutive-clean counter remains 0/3 and the review anchor advances to `v45_candidate`.

## Reset findings

1. Git source authority accepted `.git/config.worktree` include/includeIf indirection when `current_review_package.source_head` was validated. The V44 checker scanned `.git/config` but not `.git/config.worktree`, so a worktree config include could keep an external Git config authority root reachable during the phase-gate source-head check.
2. Git source authority accepted dangling symlink entries below `.git/objects` / `.git/refs` because `_check_git_authority_path()` returned before testing `Path.is_symlink()` when `Path.exists()` was false. A broken `.git/objects/info/alternates` symlink therefore passed the declared self-contained authority-tree check.
3. Clean-review evidence metadata accepted stale visible package identity wrapped in generic HTML/XML/SVG/MathML markup, for example `<svg><text>Package: zmd_18.7z</text></svg>`, while later plain ASCII metadata satisfied `current_review_package` binding.

## Required closure

The reset family is closed only when the phase-gate checker rejects worktree-config include indirection, rejects dangling symlinks anywhere in the checked Git authority paths, rejects markup-wrapped metadata keys in clean-review evidence, and the proof-obligation manifest requires regression tests for those witnesses.
