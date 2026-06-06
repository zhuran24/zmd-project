# Subject: documentation tree architecture

This subject defines the documentation tree as a graph of abstract subjects and concrete projections.

The central unit is not a file path. A file path is only a projection surface. The central unit is a subject: a context-independent source for a fact, rule, status, or governance pattern. Concrete documents are allowed to branch that subject into audience-specific front doors, runbooks, inventories, research archives, or project-book chapters, but registered projection blocks must remain synchronized with the subject.

The first implementation layer is exact-field transclusion. Subject fields live in `docs/subjects/*.md`. Projection targets are declared in `cc_context/knowledge/PROJECT_SUBJECT_PROJECTIONS.json`. The sync tool can fan subject edits out to all projections, or absorb an intentional projection edit back into the subject when the projection's checksum proves it was edited from the latest subject state.

<!-- SUBJECT-FIELD:docs_readme_summary START -->
The documentation tree is organized around **subjects** and **projections**. Subjects live in `docs/subjects/` as context-independent sources; concrete docs carry registered projection blocks that are synchronized by `scripts/sync_doc_subjects.py`. This replaces copy-based current-status prose with a small transclusion graph.
<!-- SUBJECT-FIELD:docs_readme_summary END -->

<!-- SUBJECT-FIELD:project_book_entry START -->
`docs/项目说明/` is the living project book: overview, math, lifecycle, phase plans, go criteria, risks, workflow, and glossary. Its current-state statements should be registered projections of `docs/subjects/current_project_state.md` rather than independent copies.
<!-- SUBJECT-FIELD:project_book_entry END -->

<!-- SUBJECT-FIELD:research_archive_entry START -->
`docs/research/` is the research and review archive. Archive documents may preserve historical values, but any present-tense claim reused outside the archive should be promoted to a subject field and projected from there.
<!-- SUBJECT-FIELD:research_archive_entry END -->

<!-- SUBJECT-FIELD:governance_gate_summary START -->
Preflight runs `python scripts/sync_doc_subjects.py --check`. A changed subject with stale projections, or an edited projection that has not been absorbed into its subject, blocks the gate instead of silently drifting.
<!-- SUBJECT-FIELD:governance_gate_summary END -->
