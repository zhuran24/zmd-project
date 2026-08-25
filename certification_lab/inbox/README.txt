ZMD CERTIFICATION INBOX
=======================

Each admitted or pending candidate occupies one immutable directory:

  certification_lab/inbox/<packet-id>/

A packet is copied into this tree and hash-verified before review. Do not review
from a mutable path in research/main. Do not edit packet semantic bytes after
admission; findings and derived material belong under
certification_lab/reviews/<packet-id>/.

The active packet pointer lives in certification_lab/MODE.txt and STATE.txt.
When no packet is active, this tree remains idle.
