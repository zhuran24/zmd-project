# Production Candidate-Domain Discrepancy

The benchmark specifies intended physical semantics: a facility body may touch the grid boundary, and only a port actually bound to a commodity requires an in-grid, body-free access cell. Inactive physical ports may face outside the map or be blocked.

During preparation, the production placement enumerator was found to apply a stronger pre-binding rule to the protocol core: it discarded a boundary-touching mode when any one physical port side faced outside the grid, even though the core may activate ports on other sides. The same issue affected `protocol_storage_box`, whose output side may remain entirely idle. Both templates therefore require the full body-in-grid domain.

Manufacturing templates retain side-starvation pruning. Every fixed manufacturing operation requires at least one active input and one active output, and its physical mode places all inputs on one side and all outputs on the opposite side. A mode whose entire input or output access side is unusable cannot satisfy any such operation, so this narrower pruning remains sound.

The strict external benchmark therefore does not include or derive from the production candidate pool. Absolute placements are defined directly by body-in-grid geometry; port legality is evaluated only after the witness declares complete active/inactive bindings. This separation is essential to the clean-room experiment and to the reference validator.

The production correction and artifact reseal are tracked separately from this experiment package. Historical candidate counts and hashes are intentionally absent from the external material.
