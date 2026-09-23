#!/usr/bin/env python3
"""Read-only status summary; never starts or interrupts a solver."""
from pathlib import Path
from datetime import datetime,timezone
import json,time

root=Path(__file__).resolve().parent
state=json.loads((root/'campaign_state.json').read_text())
out={'utc':datetime.now(timezone.utc).isoformat(),'state':state['state']}
counts={};finished=[]
for p in (root/'results').glob('*.json'):
    try:d=json.loads(p.read_text())
    except json.JSONDecodeError:continue
    if 'solve_seconds' not in d or 'tag' not in d:continue
    counts[d['status']]=counts.get(d['status'],0)+1
    finished.append((d['ended_utc'],d['tag'],d['status'],round(d['solve_seconds'],2)))
out['completed_status_counts']=counts
out['last_finished']=sorted(finished)[-1] if finished else None
if state['state']=='running':
    tag=state['tag'];cmd=state['command'];out['tag']=tag
    out['process_elapsed_seconds']=round(time.time()-datetime.fromisoformat(state['utc']).timestamp(),1)
    out['limit_seconds']=float(cmd[cmd.index('--seconds')+1])
    p=root/'logs'/f'{tag}.load.jsonl'
    if p.exists():
        lines=p.read_text().splitlines()
        if lines:
            try:
                d=json.loads(lines[-1]);out['load']=d['load'];out['rss_gib']=round(d['rss_bytes']/2**30,2)
            except json.JSONDecodeError:pass
print(json.dumps(out,ensure_ascii=False,indent=2))
