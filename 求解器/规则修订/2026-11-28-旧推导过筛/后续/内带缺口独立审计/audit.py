"""Run: python3 -B audit.py. Writes replayable coordinate lists next to this script."""
from pathlib import Path
from collections import Counter
from itertools import combinations
from math import ceil
import json
from geometry import *
from local_checks import *

HERE=Path(__file__).resolve().parent
def emit(obj): return json.dumps(obj,ensure_ascii=False,separators=(',',':'))

def normal_form_core(board,corelist):
    # Probe each core take-port environment in a translated interior window. Other big
    # units can be at every relative offset. Translate every ray to the board again below.
    x,y,axis,heads,fs=next(v for v in corelist if v[:3]==(30,30,0))
    for axis in (0,1):
        x,y,axis,heads,fs=next(v for v in corelist if v[:3]==(30,30,axis))
        s=next(s for s in SPECS if s.name=='协议核心' and s.orient==axis)
        case=Case(board,solid=(s,x,y),extra_heads=heads)
        for f in fs: check_face(case,f,'core')
    # No 3x1 depot omitted by translation: an alleged tangential port is in the
    # interval between two source heads, both coordinates >=3, so never in row/col 0.

def explicit_perimeter(qrect,solid):
    x,y,w,h=qrect
    Q=set(cells(x,y,w,h))
    xx=[face((69,i),0) for i in range(1,70)]+[face((i,69),1) for i in range(1,70)]
    xx=[f for f in xx if f[:2] not in solid|Q]
    yy=[face(step(p,d),opp(d)) for p in Q for d in D
        if inside(step(p,d)) and step(p,d) not in Q and step(p,d) not in solid]
    assert len(set(xx+yy))==len(xx+yy)
    return sorted(xx),sorted(yy)

def process(board,corelist):
    q=check_q(board)
    case=Case(board)
    inner=[]
    tang=[]
    owners=[]
    for p in sorted(I-board.B-board.heads.keys()):
        d=2 if p[0]==1 else 3
        inner.append(check_face(case,face(p,d),'inner',pole_exempt=True))
    for p,din in board.heads.items():
        norm=opp(din)
        ts=((norm+1)%4,(norm+3)%4)
        for t in ts:
            if step(p,t) not in board.B:
                tang.append(check_face(case,face(p,t),'source tangent'))
        if all(board.heads.get(step(p,t,3))==din for t in ts):
            owners.append((p,branch_options(board,p,norm,ts)))
    g=len(owners)
    if board.q==(0,0):
        c=(1,1)
        rest=[check_face(case,face(c,d),'free corner') for d in D if face(c,d) not in inner]
        corner={'free':rest}
    else:
        o=(1,1)
        norm=opp(board.heads[o])
        p=step(o,norm)
        pnorm=opp(board.heads[p])
        arc=check_face(case,face(o,norm),'corner first')
        # If p's ore entered o, o would need an additional ore inlet opposite its full
        # source. In a bridge that raw lane ends at the output-only warehouse port.
        assert not case.can_flow(o,extra_raw_in=norm)
        corner={k:[arc,*v] for k,v in branch_options(board,p,pnorm,(norm,),True).items()}
    groups=[('q',q),('inner',inner),('tangent',tang)]
    # Within a source only one alternative is charged. Between sources test the entire
    # union of alternatives, which is stronger than choosing a particular branch.
    assert all(len(v)==3 and len(set(v))==3 for v in corner.values())
    groups.append(('corner',set().union(*corner.values())))
    for p,options in owners:
        assert all(len(v)==2 and len(set(v))==2 for v in options.values())
        groups.append((str(p),set().union(*options.values())))
    used=set()
    for k,fs in groups:
        assert len(set(fs))==len(fs) and not used.intersection(fs),(board.gaps,k,used.intersection(fs))
        used.update(fs)
    # All eligible core positions must miss the union for this particular belt layout.
    # Any shape can be translated as checked in normal_form_core. A core tangential
    # face points to another forced head three cells away, so no empty Q can pay it.
    chosen=None
    eligible=0
    for x,y,axis,heads,fs,r,hm in corelist:
        if board.obstacles&(r|hm): continue
        eligible+=1
        assert used.isdisjoint(fs)
        if (x,y,axis)==(30,30,0): chosen=fs
    assert chosen and len(chosen)==8
    d=sum(board.q)
    h=9 if d in (0,69) else 2 if d in (3,66) else 0
    total=len(q)+len(inner)+len(tang)+2*g+3+len(chosen)
    selection=[*q,*inner,*tang,*chosen,*next(iter(corner.values()))]
    for _,options in owners: selection.extend(options['forward transport'])
    assert len(selection)==len(set(selection))==total==273+h,(board.gaps,total)
    
    # Also check every single eligible pole at its actual anchor. For multiple disjoint
    # poles the lost inner origins are their disjoint union.
    innerpts={f[:2] for f in inner}
    for p,hit in board.poles:
        loss=len(hit&innerpts)
        assert loss==len(hit-board.B) and loss<=len(hit)<=2
    sample_x,sample_y=explicit_perimeter((48,48,6,6),board.depots|set(cells(30,30,9,9)))
    assert used.union(chosen).isdisjoint(sample_x+sample_y)
    row=dict(gaps=board.gaps,q=board.q,d=d,h=h,t=92-len(tang),B=sorted(board.B),g=g,total=total,
             eligible_core_rotations_mod_180=eligible,
             poles=[(p,sorted(hit)) for p,hit in board.poles],
             sample_selected_faces=selection,q_faces=q,inner_faces=inner,source_tangents=tang,ordinary_sources=owners,corner=corner,
             example_core_anchor_axis=[30,30,0],example_core_faces=chosen,
             example_empty_rectangle=[48,48,6,6],example_X0=sample_x,example_Y0=sample_y)
    return row

def global_core_table():
    result=[]
    with (HERE/'核心位置.jsonl').open('w') as fo:
        for x,y,axis,heads,fs in core_placements():
            r=rect(x,y,9,9)
            hm=mask(heads)
            for f in fs:
                assert not eligible_x(f)
                assert all(tile&hm for xx,yy,tile in q_windows(f))
            result.append((x,y,axis,heads,fs,r,hm))
            print(emit([x,y,axis,fs]),file=fo)
    return result

if __name__=='__main__':
    corelist=global_core_table()
    boards=list(each_board())
    assert len(boards)==47
    normal_form_core(boards[0],[c[:5] for c in corelist])
    summary=Counter()
    with (HERE/'47种排布.jsonl').open('w') as fo:
        for b in boards:
            row=process(b,corelist)
            key=(row['t'],len(row['B']),row['g'],row['total'])
            summary[key]+=1
            print(emit(row),file=fo,flush=True)
    print('layouts (t, |B|, g, nominal faces)',sorted(summary.items()))
    print('core placements (symmetry mod 180)',len(corelist))
    print('local calls',sorted(stats.items()))
    (HERE/'逐面统计.json').write_text(emit(dict(stats)))
