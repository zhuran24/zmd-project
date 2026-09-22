"""Exact audit of two statements in frozen meeting consensus v1.

This checks local logical implications and cut orientation, not a factory.
The frozen consensus and other seats' files are read only.
"""
from pathlib import Path
from collections import deque
from time import perf_counter
import hashlib
import json


def main():
    started = perf_counter()
    meeting = Path(__file__).resolve().parents[1]
    frozen = meeting/'共识稿-v1-ca4c1fbe.md'
    raw = frozen.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    assert sha == 'ca4c1fbe867b3326da30773579a15b5096c485238bdbc76709fc90a2af21d59f'
    text = raw.decode()
    start = text.index('## 二、问题 2：')
    end = text.index('## 三、问题 3：', start)
    second = text[start:end].strip()+'\n'
    signed = (meeting/'seat-codex-3/问题2-数值域认可-a4467900.md').read_text()
    assert second == signed

    # A non-transport output faces one belt; the belt exits to empty ground.
    # h=z=1 on the input interface, all physical flows and recipe rates zero.
    # Geometry does not force positive flow; f<=z does not exclude this marker.
    f, z, h = 0, 1, 1
    assert 0 <= f <= z <= h
    assert f == 0  # Incoming and outgoing belt flow are both zero.
    S, R, D, M = 1, 0, 0, 0
    support_inequality = -2*M <= R-S <= 2*D
    assert not support_inequality

    # Lower-bound circulation: a->b fixed to 1, b->a fixed to 0.
    nodes = ('a', 'b')
    arcs = (('a','b',1,1), ('b','a',0,0))
    d = dict.fromkeys(nodes, 0)  # d = inflow - outflow.
    residual_demand = dict(d)
    residual = {v: {} for v in nodes+('SS','TT')}
    for a,b,lower,upper in arcs:
        residual_demand[a] += lower
        residual_demand[b] -= lower
        residual[a][b] = upper-lower
    required = 0
    for v, value in residual_demand.items():
        if value < 0:
            residual['SS'][v] = -value
        elif value > 0:
            residual[v]['TT'] = value
            required += value
    reachable = {'SS'}
    queue = deque(['SS'])
    while queue:
        a = queue.popleft()
        for b, cap in residual[a].items():
            if cap > 0 and b not in reachable:
                reachable.add(b)
                queue.append(b)
    assert 'TT' not in reachable
    source_side = set(nodes) & reachable
    sink_side = set(nodes)-source_side
    assert source_side == {'b'} and sink_side == {'a'}

    def cut(X):
        demand = sum(d[v] for v in X)
        lower_out = sum(lo for a,b,lo,up in arcs if a in X and b not in X)
        upper_in = sum(up for a,b,lo,up in arcs if a not in X and b in X)
        return {'nodes': sorted(X), 'demand': demand, 'lower_out': lower_out,
                'upper_in': upper_in, 'violated': demand+lower_out > upper_in}

    source_check, complement_check = cut(source_side), cut(sink_side)
    assert not source_check['violated'] and complement_check['violated']
    supplement = (meeting/'seat-codex-3/共识段-四五.md').read_text()
    entries = [line[2:] for line in supplement.splitlines() if line.startswith('- ')]
    result = {
        'scope': 'frozen-text, local support-marker, and cut-orientation checks only',
        'frozen_sha256': sha, 'frozen_lines': len(text.splitlines()),
        'second_section_matches_signed_a4467900': True,
        'P6_explicit': 'P6 粉碎机、采种机每台只做一个配方（显式限制' in text,
        'supplement_entries_present': [entry in text for entry in entries],
        'support_marker_example': {'f':f, 'z':z, 'h':h, 'S':S, 'R':R,
                                   'D':D, 'M':M, 'inequality_holds': support_inequality},
        'lower_bound_example': {'required_auxiliary_flow': required,
                                'maximum_auxiliary_flow': 0,
                                'source_side_formula': source_check,
                                'complement_formula': complement_check},
        'elapsed_seconds_excluding_imports_and_write': perf_counter()-started,
    }
    Path(__file__).with_name('vote_v1_turn7_audit.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
