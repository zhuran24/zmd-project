# Typed memory graph

This directory is the machine-readable layer over `cc_context/memory/`.

The Markdown files remain the human editing surface. The graph layer gives the
agent a smaller, stricter thing to maintain:

- `facts.jsonl` records fact slots and their current versions.
- `edges.jsonl` records typed hard dependencies. Direction is **dependent -> dependency**.
- `events.jsonl` is append-only evidence/source material.
- `changes.jsonl` is the change transaction ledger.
- `generated/graph.json` is generated cache, not hand-edited.

Edge types:

- `DEPENDS_ON`: hard update propagation edge. If the target changes, the source must be reconsidered.
- `DERIVED_FROM`: hard fact-to-fact derivation edge.
- `SUPERSEDES`: replacement relationship between fact versions.
- `CONTRADICTS`: conflict edge requiring review.
- `SUPPORTS`, `PROJECTS_TO`, `MENTIONS`, `RELATED_TO`: soft reading/search edges. They do not trigger automatic rewrites.

Basic commands:

```bash
python cc_context/tools/memgraph.py check --write-graph
python cc_context/tools/memgraph.py impact fact-understand-before-output
python cc_context/tools/memgraph.py freshness
python cc_context/tools/memgraph.py index --check
python cc_context/tools/sync_knowledge.py --check
```

Update protocol:

1. Save source material with `memgraph.py add-event`.
2. Propose a change with `memgraph.py propose-change --touches <fact-or-entry> ...`.
3. Review the impact set. Only the returned dependents need rewrite.
4. Edit Markdown / graph files.
5. Run `memgraph.py check`, `memgraph.py freshness --accept <changed-node>`, and `memgraph.py index --apply`.

The main rule is simple: links in prose are allowed to be fuzzy; edges in
`edges.jsonl` are not. Hard edges are the nervous system. Do not make them
"generally related" links.
