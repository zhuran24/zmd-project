---
name: project-knowledge-tree-architecture
metadata:
  node_type: memory
  type: project
  originSessionId: gpt-5.5-pro-handoff-20260606
---

This node is the memory-side projection of the project knowledge-tree architecture. It prevents future handoff windows from flattening `docs/` and `cc_context/memory/` into one noisy directory, or from treating them as two unrelated sources of truth.

## One logical tree, two physical projections

<!-- DOC-SUBJECT:project_knowledge_tree FIELD:shared_subject_layer START sha256:9dd6b559dd17a70fab730793a77d2e4a91c27eedcdfbf1bf81fdeba5f658592f -->
The project uses **one logical knowledge tree with two physical projections**. `docs/` is the stable documentation projection; `cc_context/memory/` is the collaboration-continuity projection. Neither tree is allowed to become a second independent truth source: volatile living claims should be promoted into a subject field and projected to every surface that needs them.
<!-- DOC-SUBJECT:project_knowledge_tree FIELD:shared_subject_layer END -->

## Memory-tree role

<!-- DOC-SUBJECT:project_knowledge_tree FIELD:memory_role START sha256:29ad99c8cfd99eeb1c5b120f5028478ab5d2083ee1d4075293639ba3e6c66ea9 -->
The memory tree is the collaboration-continuity surface. It answers: what the previous working window knew, which mistakes were already corrected, what user preferences or process constraints matter, which old statements must not be trusted blindly, and what the next window should read first.
<!-- DOC-SUBJECT:project_knowledge_tree FIELD:memory_role END -->

## Projection rule

<!-- DOC-SUBJECT:project_knowledge_tree FIELD:projection_rule START sha256:671f0705419a7ca28ff595ea1437d45799031db2ba94a84ac2ec8645b59a4f03 -->
Living/current claims should flow through subject fields and registered projection slots. Historical review notes, raw transcripts, dated decisions, and evidence archives should remain evidence nodes: they may link to subjects, but they should not be auto-rewritten into present-tense truth.
<!-- DOC-SUBJECT:project_knowledge_tree FIELD:projection_rule END -->

Operationally, a new GPT window should first read the subject/front-door docs for the stable contract, then memory nodes for collaboration continuity. Evidence/archive memory nodes stay dated; living/current memory nodes should either project a subject field or link to the subject that owns the claim.

Related: [[memory-tree-publish-safety]], [[memory-currency-protocol]], [[memory-tree-structural-health]], [[github-backup]], [[windows-ninth-review-pending]].
