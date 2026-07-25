# v2 handoff framework status

This directory contains a copied research composition adapter and a pure-stdlib
fail-closed contract for `connected_bay_selection.v2`. It does not contain a
formal selection and does not establish geometry assembly or routing.

The adapter requires a hash-pinned `routing_geometry_bundle.v2` with terminal
status `ROUTING_GEOMETRY_BUNDLE_READY`. It emits an explicit
`protected_rectangle: [x,y,6,7]`, verifies all 35 pole anchors, rehashes the
bundle's c4/c5/c9/c10/c11 result and independent-replay references, and reparses
the in-memory v2 result with both the local contract and the read-only assembler
parser. Extra bundle fields are allowed, but every required field and fixed
semantic is checked.

The successful validation run is
`framework_validation/validation-20260720T092959Z-10a8f9`. It passed one
positive 219-pose fixture and 15 mutation-negative cases covering schema fields,
protected shape/grid/body collision, pole uniqueness, source hashes, bundle
schema/status, protected cell accounting, backbone overlap accounting, and
recursive source hashes. It wrote zero formal selection files.

The earlier run `validation-20260720T092942Z-1b97a9` stopped before validation
because the read-only assembler's package root was not on `sys.path`. Its two
fixture files are retained as crash history. The bootstrap was corrected in the
copied adapter before the successful fresh run; no existing run was overwritten.
