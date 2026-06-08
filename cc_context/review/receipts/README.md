# Review receipts

This directory is reserved for strict JSON receipts that count toward the Phase
1.2 algorithmic clean-review counter.  A human report may be Markdown or any
other prose format, but the phase gate only grants clean-review credit from a
receipt whose `report_sha256` binds that report and whose archive/source-tree
fields match the current review package.

Do not put API keys, private reviewer notes, or free-form metadata parsers here.
Receipt files should be small canonical JSON objects using the
`p1_2_clean_review_receipt` schema recorded in
`data/review_gates/schemas/p1_2_clean_review_receipt.schema.json`.
