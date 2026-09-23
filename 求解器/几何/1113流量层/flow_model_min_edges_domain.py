#!/usr/bin/env python3
"""First-solution auxiliary-objective retry with the original audited P domains.

For y=6,7,9, P=12 was excluded by the original exact boundary DP. This
restriction is disabled in cut_mode=none, so weakening rechecks reopen all P.
"""
import hashlib,json,sys
sys.dont_write_bytecode=True
import flow_model_min_edges
import flow_model as base

original_build=base.build
original_run=base.run


def build(position,layer='all',cut_mode='formal'):
    model,meta=original_build(position,layer,cut_mode)
    if cut_mode=='formal':
        proof=json.loads((base.ROOT/'original_domain_recheck.json').read_text())
        src=base.ROOT/'inputs/positions.json'
        assert proof['ok'] and hashlib.sha256(src.read_bytes()).hexdigest()==proof['positions_sha256']
        allowed=position['allowed_P']
        checked=next(p for p in proof['positions'] if p['rect']==list(position['rect']))
        assert checked['allowed_P']==allowed and allowed in ([10,11],[10,11,12])
        if allowed==[10,11]:model.add(meta['P']<=11)
    return model,meta


def run(args):
    res=original_run(args)
    pos=next(p for p in json.loads((base.ROOT/'inputs/positions.json').read_text()) if p['rect'][1]==args.y)
    res['variant']='global_min_edges_original_P_domain'
    res['variant_file']='flow_model_min_edges_domain.py'
    res['P_domain_used']=pos['allowed_P'] if args.cut_mode=='formal' else [10,11,12]
    res['P_domain_source']='original_domain_recheck.json; same-source exact integer replay of previously audited boundary DP'
    (base.ROOT/'results'/f'{res["tag"]}.json').write_text(json.dumps(res,ensure_ascii=False,indent=2))
    return res


base.build=build;base.run=run
if __name__=='__main__':base.main()
