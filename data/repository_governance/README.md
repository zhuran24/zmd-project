# Repository governance ledger

Two registries live here. `code_assets.json` governs code assets; `doc_classes.json` governs
documents. Both are descriptive projections: neither can authorize an edit, close a phase, or
certify anything.

## `doc_classes.json` — document classification

`doc_classes.json` names which tracked markdown files the prune-system docs adapter
(`devtools/docs_reference_scan.py`) may look at, and how. Three classes: `locked` documents are
never scanned at all; `historical` documents can only ever produce FYI observations, because a
stale reference inside dated evidence is a property of the evidence; `living` documents are the
only ones whose findings become cleanup candidates. A tracked markdown file inside the declared
scan scope that matches no rule is reported as `unregistered_doc`, and every tracked markdown file
must be either in scope or listed under `scan_scope.out_of_scope_notes` with a reason — there is no
silent third state.

To add a document, register it in `rules` (or widen `scan_scope`), then run
`python devtools/docs_reference_scan.py validate-registry`, which fails closed if a registered
member is untracked, a list is unsorted, or a markdown file has fallen through the coverage
invariant. Changing a classification is an owner-visible judgement, not a mechanical fix:
demoting a document to `historical` permanently exempts it from cleanup candidates.

Two consequences worth knowing before adding markdown anywhere in this repository. First, the
coverage invariant is a **repository-wide gate, not an advisory signal**: a tracked markdown file
that is neither in `scan_scope` nor listed under `out_of_scope_notes` makes the scanner and its
test fail, so a new `data/README.md`, a new `docs/项目说明/子目录/x.md`, or any new top-level
directory containing markdown turns the fast test lane red until someone updates this registry.
That is the intended R22 negative-example semantics — registration is the point — but it is a
cost paid by whoever adds the file, not by whoever maintains the registry. Second, a path claimed
by two rules with different classes is a **structural error**, not a first-match-wins race: rule
order carries no meaning, so a broad rule cannot silently reclassify the documents below it.
Redundant rules that agree on the class are fine.

## `code_assets.json` — code asset ledger

`code_assets.json` and its adjacent schema are the repository code-asset governance ledger. The
`read_only_historical_evidence_roots` entries name non-authorizing, read-only `.artifacts/<root>/`
collection boundaries whose contents remain Git-visible but are not inspected or counted as code assets. A registration
does not make the evidence current, executable, certified, or production-authoritative, and it does not enforce filesystem
immutability; byte preservation remains an independent review obligation.

For a future campaign, first compare the live inventory with `inventory --commit HEAD` and obtain owner confirmation that
the exact new top-level sibling root is historical evidence. Do not append to an already registered root. Add one sorted
registry entry with its nature, `non_code_asset` treatment, read-only expectation, and rationale in the same change; do not
add a Git or search ignore. Then rerun the live check, the tracked-only inventory, governance tests, and the negative case
showing that an unregistered sibling `.artifacts` code asset still fails the count gate.
