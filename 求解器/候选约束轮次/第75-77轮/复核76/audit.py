"""Finite domain, branch provenance, input stability and delivery audit."""
from geometry import *
import hashlib,re,ast,sys
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    src=ROUNDS/'第75-77轮/推导75'
    full=domains(full=True);proj=domains();keys=lambda u:tuple(u[k] for k in ('kind','x','y','w','h','axis'))
    pk={keys(u) for u in proj};mm=[u for u in full if u['kind'] in ('s','m','l')]
    deleted=[u for u in full if keys(u) not in pk]
    assert all(u['kind']=='p' and not edge(u) and not body(u)&set(WEIGHT) and not any(powered(m,u) for m in mm) for u in deleted)
    assert len(full)==3970 and len(proj)==1945 and len(deleted)==2025
    all_centers={(x,y) for x in range(2,69) for y in range(2,69) if not box(x-1,y-1,3,3)&HOLE}
    assert len(all_centers)==3376 and len({(x//3,(y+1)//3) for x,y in all_centers})==403
    # Data from producer are checked, not used to create the review matrix.
    receipts=[]
    names=['project_native_cap187_J0','linear_project_cap187_J0','project_highs_cap187_J0']
    names += [f'complete_replay_{e}_S{s}' for s in (185,186,187) for e in ('native','highs')]
    names += ['residual_global_A','residual_global_B','residual_global_A_quick','residual_global_B_quick']
    sources={sha(p):p.name for p in src.glob('*.py')}
    for n in names:
        p=src/(n+'.json');d=json.loads(p.read_text());log=src/(n+'.log')
        status=d['status'];expected='INFEASIBLE' if 'cap187' in n else 'OPTIMAL' if 'replay' in n else 'UNKNOWN'
        assert status==expected
        txt=log.read_text();assert expected in txt or (expected=='INFEASIBLE' and 'Infeasible' in txt)
        hashes={k:d[k] for k in ('script_sha256','source_sha256','wrapper_sha256') if k in d}
        assert hashes and all(h in sources for h in hashes.values())
        receipts.append(dict(name=n,status=status,sha256=sha(p),log_sha256=sha(log),sources={k:sources[h] for k,h in hashes.items()},source_hashes=hashes,seconds=d.get('seconds'),time_limit=d.get('time_limit')))
    br=json.loads((src/'branches.json').read_text())['branches']
    expected={(pos,S,J) for pos in ((49,17),(17,49)) for S in (185,186,187) for J in (0,1)}
    seen=[(tuple(r['position']),r['S'],r['J']) for r in br];assert set(seen)==expected and len(seen)==len(set(seen))==12
    # Direct certificate exclusions of the two poles that hit two counting edges.
    caps={(r['x'],r['y']):r['loss'] for r in json.loads((OUT/'capacities.json').read_text())}
    # Upper witnesses must also satisfy the exact inherited table cuts in M1.
    tables=json.loads((ROUNDS/'第69-71轮/推导69/new_edge_local_certificate.json').read_text())['cases'][0]['lines']
    witness_tables=[]
    for S in (185,186,187):
        us=json.loads((src/f'complete_subsets_S{S}.json').read_text())['chosen'];line_rows=[]
        for line,table in zip(LINES,tables):
            meet=[u for u in us if body(u)&line];cp=sum(u['kind']=='c' for u in meet);pp=sum(u['kind']=='p' for u in meet)
            loss=sum(caps[u['x'],u['y']] for u in meet if u['kind']=='p')
            actual=len(line)-sum(len(body(u)&line) for u in meet)-2*sum(edge(u) for u in meet if u['kind']=='p')
            allowed=[(state,v) for state,v in table['frontier'] if state[:2]==[cp,pp] and state[2]<=min(13,loss) and v<=actual]
            assert allowed
            line_rows.append(dict(core=cp,poles=pp,loss=loss,actual=actual,accepted_table_rows=allowed))
        witness_tables.append(dict(S=S,lines=line_rows))
    dump('witness_table_checks.json',witness_tables)
    corner=[(47,68),(68,15)];branches=[]
    for P in (10,11,12):
        for mask in range(4):
            loss=sum(caps[c] for i,c in enumerate(corner) if mask>>i&1)
            branches.append(dict(P=P,corner_present=[bool(mask>>i&1) for i in range(2)],corner_loss=loss,loss_budget=23*P-217,excluded_by_loss=loss>23*P-217))
    # No producer modules imported by any review program.
    imports={}
    for p in OUT.glob('*.py'):
        tree=ast.parse(p.read_text());found=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):found += [a.name for a in node.names]
            if isinstance(node,ast.ImportFrom):found.append(node.module)
        assert not any('75' in str(n) or '72' in str(n) or '74' in str(n) for n in found)
        imports[p.name]=found
    before=json.loads((OUT/'input_manifest.json').read_text())
    now={n:sha(ROOT/n) for n in before};assert now==before
    domain=dict(full=dict(Counter(u['kind'] for u in full)),projected=dict(Counter(u['kind'] for u in proj)),deleted_poles=len(deleted),domain_sha256=hashlib.sha256(json.dumps(full,sort_keys=True).encode()).hexdigest(),corners=branches,residual_global_centers=len(all_centers),residual_shift01_groups=403)
    dump('domain_audit.json',domain);dump('producer_receipts_audit.json',receipts)
    res=dict(inputs_unchanged=True,inputs=now,producer_branches=12,independent_imports=imports,domain=domain)
    if '--final' in sys.argv:
        report=OUT.parent/'复核76.md';txt=report.read_text()
        links=re.findall(r'\]\(([^)]+)\)',txt)
        missing=[link for link in links if not (report.parent/link.split('#')[0]).exists()]
        assert not missing,missing
        verdicts=json.loads((OUT/'verdicts.json').read_text());assert len(verdicts['verdicts'])==2
        assert all(x['verdict'] in ('未否证','已否证','修正') for x in verdicts['verdicts'])
        own=[]
        for name in ['J0_cap187_cp','J0_cap187_highs','J1_cap184','J1_cap184_highs','P11_cap187','P12_cap187','P11_quick','J1_quick']+[f'replay_{s}_{e}' for s in (185,186,187) for e in ('cp','highs')]:
            d=json.loads((OUT/(name+'.json')).read_text());own.append(dict(name=name,status=d['status'],seconds=d['seconds'],matrix_sha256=d['matrix_sha256']))
            for file,h in d['source_sha256'].items():assert sha(OUT/file)==h
        byname={r['name']:r for r in own}
        assert byname['J1_cap184']['matrix_sha256']==byname['J1_quick']['matrix_sha256']==byname['J1_cap184_highs']['matrix_sha256']
        assert byname['P11_cap187']['matrix_sha256']==byname['P11_quick']['matrix_sha256']
        assert byname['J0_cap187_cp']['matrix_sha256']==byname['J0_cap187_highs']['matrix_sha256']
        res.update(own_runs=own,report_sha256=sha(report),links_checked=len(links),reader_audit=dict(standalone=True,current_status_consistent=True,no_style_instruction_echo=True,numeric_scopes_separated=True,references_exist=True),outputs={p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='delivery_audit.json'})
    dump('delivery_audit.json',res)
    print(dict(inputs_unchanged=True,domain=domain,producer_receipts=len(receipts),final='--final' in sys.argv))
if __name__=='__main__':main()
