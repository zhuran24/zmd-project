# Repository governance ledger

`code_assets.json` and its adjacent schema are the repository code-asset governance ledger. The
`read_only_historical_evidence_roots` entries name non-authorizing, read-only `.artifacts/<root>/`
collection boundaries whose contents remain Git-visible but are not inspected or counted as code assets. A registration
does not make the evidence current, executable, certified, or production-authoritative, and it does not enforce filesystem
immutability; byte preservation remains an independent review obligation.

For a future campaign, first compare the live inventory with `inventory --commit HEAD` and obtain owner confirmation that
the exact new top-level sibling root is historical evidence. Do not append to an already registered root. Exception: a root registered while its research line is still
running may name append-only extension subpaths in its rationale; bytes that
already exist stay immutable, and the exception ends when the line closes. Add one sorted
registry entry with its nature, `non_code_asset` treatment, read-only expectation, and rationale in the same change; do not
add a Git or search ignore. Then rerun the live check, the tracked-only inventory, governance tests, and the negative case
showing that an unregistered sibling `.artifacts` code asset still fails the count gate.
