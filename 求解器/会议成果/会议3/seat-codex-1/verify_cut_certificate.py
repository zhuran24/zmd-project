"""Independent rational verifier for a supplied fixed-mother-matrix cut.
Does not import the producer's solver or verifier, and never trusts self_check.
"""
import argparse, hashlib, json, math
from collections import Counter, defaultdict
from fractions import Fraction as Q
from pathlib import Path


def no_duplicates(pairs):
    d={}
    for k,v in pairs:
        if k in d:
            raise ValueError('duplicate JSON key: '+str(k))
        d[k]=v
    return d


def q(v):
    if isinstance(v,bool):
        raise ValueError('boolean where rational expected')
    return Q(str(v))


def norm(d):
    return {k:v for k,v in d.items() if v}


def verify(path):
    data=path.read_bytes()
    obj=json.loads(data,object_pairs_hook=no_duplicates)
    rows,cols=obj['rows'],obj['cols']
    on=set(obj['master_true_literals'])
    assert len(on)==len(obj['master_true_literals'])
    dual={}
    expected=defaultdict(Q)
    rhs=Q(0)
    rhs_weighted_now=Q(0)
    kinds=Counter()
    cap_constant_rows=[]
    for key,row in rows.items():
        kind=row['kind']; kinds[kind]+=1
        assert kind in ('eq','cap','tgt'),(key,kind)
        val=q(row['y']);dual[key]=val
        now=q(row['rhs_now'])
        literal=row.get('literal')
        # Producer serializes the absence of a literal with repr(None).
        if literal == 'None':
            literal=None
        rhs_weighted_now+=val*now
        if kind=='eq':
            assert now==0 and literal is None,(key,row)
        elif kind=='tgt':
            assert val>=0 and literal is None,(key,row)
            rhs+=val*now
        else:
            assert val<=0,(key,val)
            assert now>=0,(key,now)
            if literal is None:
                # The supplied schema declares this a constant RHS.
                rhs+=val*now
                cap_constant_rows.append({'row':key,'rhs':str(now)})
            else:
                assert now==int(literal in on),(key,now,literal)
                expected[literal]+=-val
    residuals=[]
    used=set()
    for idx,col in enumerate(cols):
        assert col,idx
        assert set(col)<=set(rows),(idx,set(col)-set(rows))
        residual=sum((q(coef)*dual[key] for key,coef in col.items()),Q(0))
        assert residual<=0,(idx,residual)
        residuals.append(residual)
        used.update(col)
    expected=norm(dict(expected))
    raw=obj['cut_raw']
    supplied_raw=norm({k:q(v) for k,v in raw['terms'].items()})
    assert supplied_raw==expected,(supplied_raw,expected)
    assert q(raw['rhs'])==rhs
    lhs=sum((a for k,a in expected.items() if k in on),Q(0))
    assert q(raw['lhs_now'])==lhs
    assert rhs-lhs==rhs_weighted_now
    assert lhs<rhs,(lhs,rhs)
    rounded=obj['cut_rounded'];K=rounded['K']
    assert isinstance(K,int) and K>0
    round_expected=norm({k:math.ceil(K*a) for k,a in expected.items()})
    round_rhs=math.ceil(K*rhs)
    assert norm(rounded['terms'])==round_expected
    assert rounded['rhs']==round_rhs
    round_lhs=sum(a for k,a in round_expected.items() if k in on)
    assert rounded['lhs_now']==round_lhs
    assert round_lhs<round_rhs
    return {
        'status':'PASS',
        'scope':'algebraic validity and strict separation for the supplied matrix and literal RHS map; not a game-model or all-cuts certification',
        'input':str(path),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),
        'rows':len(rows),'row_kinds':dict(kinds),'columns':len(cols),
        'used_rows':len(used),'nonzero_dual_rows':sum(v!=0 for v in dual.values()),
        'all_dual_signs_valid':True,'all_literal_rhs_values_consistent':True,
        'max_column_residual':str(max(residuals)),
        'min_column_residual':str(min(residuals)),
        'positive_column_residuals':sum(v>0 for v in residuals),
        'zero_column_residuals':sum(v==0 for v in residuals),
        'capacity_constant_rows':cap_constant_rows,
        'raw_cut_reconstructed':True,'raw_terms':len(expected),'raw_lhs':str(lhs),'raw_rhs':str(rhs),'raw_violation':str(rhs-lhs),
        'weighted_rhs_now':str(rhs_weighted_now),
        'rounding_recomputed':True,'rounding_scale':K,'rounded_lhs':round_lhs,'rounded_rhs':round_rhs,'rounded_violation':round_rhs-round_lhs,
        'producer_self_check_used':False,
    }

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('certificate',type=Path)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    report=verify(args.certificate)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
