#!/usr/bin/env python3
"""Validate this review's artifacts and write a SHA-256 manifest in this folder."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

OUT=Path(__file__).resolve().parent
ROUND=OUT.parent
REPORT=ROUND/'复核93F.md'
REPO=ROUND.parents[2]


def read(name):
    return json.loads((OUT/name).read_text())


def digest(path):
    data=path.read_bytes()
    return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def main():
    a,b=read('plant_a.json'),read('plant_b.json')
    a.pop('implementation'); b.pop('implementation')
    assert a==b
    delayed=a['delayed']
    assert delayed['first_full']['step']==3249
    assert delayed['first_full']['stock']['C']==50
    assert delayed['second_50_accepted'] is False
    verify=read('verify_plant.json')
    assert verify['checked_order_cases']==4*len(list(__import__('itertools').permutations(range(6))))*24
    assert verify['cross_checked_states']==6081 and verify['differences']==0
    steady=verify['permanent_saturation_state']
    assert steady['stock']==dict.fromkeys('ABCK',50)
    assert steady['output']=={'A':50,'B':50,'C':49,'K':50}
    assert steady['phi2']==429
    assert all(steady['enabled'].values())
    geometric=read('local_geometry.json')
    assert geometric['L1_plus_L2']==38
    assert geometric['lengths_by_cells']==geometric['lengths_by_segments']
    assert geometric['occupied_cells']==geometric['occupied_cells_independent_sum']==267
    assert geometric['formed_channels']==geometric['channel_count_by_path_lengths']==72
    assert geometric['unintended_channels']==0
    numbers=read('lemmas_and_counts.json')['arithmetic']
    assert numbers['dedicated_machines']==221 and numbers['dedicated_area']==3375
    assert numbers['threshold_97_both_encodings']==97
    assert numbers['max_per_kind_startup_requirement_with_long_routes']==sum([50]*11)+sum([2]*4900)
    assert numbers['warehouse_stock_at_least']>=numbers['max_per_kind_startup_requirement_with_long_routes']
    repaired=read('repaired_startup.json')
    assert len(repaired['cases'])==12 and repaired['differences']==0
    for case in repaired['cases']:
        assert case['debug_end_phi2']>=case['required_phi2']
    text=REPORT.read_text()
    links=re.findall(r'\[[^\]]+\]\(([^)]+)\)',text)
    for link in links:
        assert (ROUND/link).exists(),link
    verdicts=read('verdicts.json')
    assert verdicts['report_path']==str(REPORT)
    expected=['无分流网络的判定先后无关','全厂专用进路接法的调试办法']
    assert [v['name'] for v in verdicts['verdicts']]==expected
    assert [v['verdict'] for v in verdicts['verdicts']]==['未否证','修正']
    for verdict in verdicts['verdicts']:
        assert verdict['verdict'] in ('未否证','已否证','修正')
        assert all(isinstance(verdict[k],str) for k in ('name','verdict','reason','revised_text'))
        assert bool(verdict['revised_text'])==(verdict['verdict']=='修正')
    clause=next(line[2:] for line in text.splitlines() if line.startswith('> 制造单位与通道'))
    normalize=lambda s:s.translate(str.maketrans({'“':'"','”':'"','‘':'"','’':'"'}))
    assert normalize(clause)==normalize(verdicts['verdicts'][1]['revised_text'])
    local_modules={p.stem for p in OUT.glob('*.py')}
    imports=set()
    for script in OUT.glob('*.py'):
        tree=ast.parse(script.read_text(),filename=str(script))
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                imports.update(alias.name for alias in node.names)
            if isinstance(node,ast.ImportFrom) and node.module:
                imports.add(node.module)
    assert not any('sim2' in name or 'stepsim' in name or '推导' in name for name in imports)
    inputs=[ROUND/'前提快照'/n for n in ('《明日方舟：终末地》游戏规则.txt','求解任务.txt',
                                    '求解约束.txt','求解充分条件.txt','不补的设定.txt')]
    assert len(inputs[0].read_text().splitlines())==115
    def entries(path):
        return sum(bool(s and not s[0].isspace() and '：' in s and not s.endswith('：'))
                   for s in path.read_text().splitlines())
    assert entries(inputs[2])==77
    assert entries(inputs[3])==11
    materials=[ROUND/'推导92F.md',ROUND/'推导92F'/'s11_sim.py',ROUND/'推导92F'/'stepsim.py',
               ROUND/'推导92F'/'netgen.py',REPO/'求解器/规则修订/2026-09-30-迟滞/sim2/simulator.py',
               REPO/'求解器/规则修订/2026-09-30-迟滞/核对-模拟2.md']
    outputs=[REPORT]+sorted(p for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json')
    manifest={'generated_utc':datetime.now(timezone.utc).isoformat(),
              'checks':{'independent_results_equal':True,'geometry_checked':True,
                        'report_links_resolve':len(links),'schema_and_revised_text_match':True,
                        'python_syntax_checked':len(local_modules),'author_simulator_imports':0,
                        'snapshot_rule_lines':115,'snapshot_necessary_conditions':77,
                        'snapshot_sufficient_conditions':11},
              'premise_snapshot':{str(p.relative_to(REPO)):digest(p) for p in inputs},
              'reviewed_materials':{str(p.relative_to(REPO)):digest(p) for p in materials},
              'outputs_except_manifest_itself':{str(p.relative_to(REPO)):digest(p) for p in outputs}}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(manifest['checks'],ensure_ascii=False))


if __name__=='__main__':
    main()
