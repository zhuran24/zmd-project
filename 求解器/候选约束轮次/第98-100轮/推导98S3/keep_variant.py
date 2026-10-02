#!/usr/bin/env python3
"""98S3: the other reading of temporary rule 4 (owner 10-02 supplement).

Offline rebuild changes the connection order exactly as search.rebuild does
(same random permutation, same rng consumption), but KEEPS every channel's
last-success record: each sender's per-route last success step and each
receiver's round-robin cursor (the route it last received from).  Then runs
search.py or disturb_search.py unchanged.

usage: keep_variant.py search  <search.py args>
       keep_variant.py disturb <disturb_search.py args>
"""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import search as S

_orig = S.rebuild


def rebuild_keep(f, rng):
    sent = {id(u): dict(u.sent) for u in f.ms + f.sources}
    cur = {id(u): u.cursor for u in f.incoming}
    _orig(f, rng)
    for u in f.ms + f.sources:
        u.sent = sent[id(u)]
    for u in f.incoming:
        u.cursor = cur[id(u)]


S.rebuild = rebuild_keep

if __name__ == '__main__':
    mode = sys.argv[1]
    sys.argv = [sys.argv[0]] + sys.argv[2:]
    if mode == 'search':
        S.main()
    elif mode == 'disturb':
        import disturb_search
        disturb_search.main()
    else:
        raise SystemExit(mode)
