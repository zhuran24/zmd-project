#!/usr/bin/env python3
"""复核100S2：汇总各日志为 summary.json。"""
import json, os
def lines(p):
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []
S = {}
ra = lines('run_a.log')
S['run_a'] = dict(cases=len(ra), all_pass=all(r['period'] and r['bat_per_tick_x100'] == 60 and r['cap_per_tick_x100'] == 55 and r['ore_per_tick'] == [1.0] and r['nviol'] == 0 and r['multi_out_rej'] == 0 for r in ra),
                  periods=sorted(set(r['period'] for r in ra)), max_cycle_start=max(r['cycle_start'] for r in ra),
                  histories=sorted(set(r['history'] for r in ra)), maxlens=sorted(set(r['maxlen'] for r in ra)),
                  events=sum(r['events'] for r in ra))
rl = lines('run_long.log')
S['run_long'] = dict(cases=len(rl), all_pass=all(r['period'] and r['bat_per_tick_x100'] == 60 and r['cap_per_tick_x100'] == 55 and r['ore_per_tick'] == [1.0] and r['nviol'] == 0 and r['multi_out_rej'] == 0 for r in rl),
                     belt_cells=[min(r['total_belt_cells'] for r in rl), max(r['total_belt_cells'] for r in rl)] if rl else None)
rf = lines('run_freq.log')
S['run_freq'] = dict(cases=len(rf), all_exact=all(r['battery'] == r['battery_target'] and r['capsule'] == r['capsule_target'] and r['ore_min'] == r['ore_max'] == r['ore_target'] and r['nviol'] == 0 for r in rf),
                     offlines=sum(r['offlines'] for r in rf))
rg = lines('run_a_agereset.log')
S['age_reset_sensitivity'] = dict(cases=len(rg), rates_ok=sum(1 for r in rg if r['period'] and r['bat_per_tick_x100'] == 60 and r['cap_per_tick_x100'] == 55 and r['ore_per_tick'] == [1.0]),
                                  cases_with_invariant_violation=sum(1 for r in rg if r['nviol'] > 0),
                                  min_stock_seen=sorted({v[1].split(',')[-1].strip(' )') for r in rg for v in r['viol']}))
xc = lines('xcheck.log')
S['xcheck_sim2'] = dict(cases=len(xc), steps=sum(r['steps'] for r in xc), mismatches=sum(1 for r in xc if r['mismatch']))
su = lines('startup_a.log')
S['startup'] = dict(cases=len(su), all_ok=all(r['ok'] and r['bat_per_tick'] == 0.6 and r['cap_per_tick'] == 0.55 and r['nviol'] == 0 for r in su),
                    loops=sorted(set(r['loops'] for r in su)))
if os.path.exists('lemma_bfs.json'):
    d = json.load(open('lemma_bfs.json'))
    S['lemma_bfs'] = d['summary']
if os.path.exists('lemma_controls.json'):
    S['lemma_controls'] = [(c['note'], c['ok']) for c in json.load(open('lemma_controls.json'))]
if os.path.exists('lemma_event.json'):
    S['lemma_event'] = json.load(open('lemma_event.json'))['stats']
if os.path.exists('arith_check.json'):
    a = json.load(open('arith_check.json'))
    S['arith'] = {k: a[k] for k in ('agree_inventory', 'agree_total', 'spare_match_report', 'rate_upper_battery', 'rate_upper_capsule', 'bodies', 'A_pure_belt', 'direction_budget_best', 'best_rect_under_direction_budget')}
if os.path.exists('offsets_a.json'):
    S['offsets'] = json.load(open('offsets_a.json'))
json.dump(S, open('summary.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(S, ensure_ascii=False, indent=1))
