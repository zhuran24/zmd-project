ZMD CERTIFICATION REVIEWS
=========================

Each packet receives a separate review directory:

  certification_lab/reviews/<packet-id>/

The directory contains independent reconstruction, counterexamples, mutation
canaries, check receipts, implementation notes when applicable, and the final
VERDICT.txt. It must not rewrite the frozen packet.

A review may have several commits and branches, but only one current scoped
verdict for the packet identity. Superseded verdicts remain historical or are
renamed explicitly; they are not silently overwritten with a new subject.
