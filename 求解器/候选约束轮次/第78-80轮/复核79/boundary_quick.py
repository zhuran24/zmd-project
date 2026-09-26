"""Second search strategy on this review's native Boolean model, not a new encoding."""
from boundary_cp import *

start=time.monotonic();m,units,vs,score,full=build(186,False)
m.clear_objective()
label='boundary_le186_native_quick'
(OUT/(label+'_domain.json')).write_text(json.dumps(units,separators=(',',':')))
raw=str(m.proto);(OUT/(label+'_model.txt')).write_text(raw)
solver=cp_model.CpSolver();solver.parameters.num_search_workers=1;solver.parameters.max_time_in_seconds=180
solver.parameters.subsolvers.append('quick_restart');solver.parameters.linearization_level=2
solver.parameters.log_search_progress=True;solver.parameters.log_to_stdout=False
with (OUT/(label+'.log')).open('w') as log:
    solver.log_callback=lambda x:log.write(x+'\n')
    status=solver.solve(m)
out=dict(status=solver.status_name(status),units=len(units),cap=186,seconds=time.monotonic()-start,solver_seconds=solver.wall_time,model_sha256=hashlib.sha256(raw.encode()).hexdigest(),stats=solver.response_stats())
if status in (cp_model.OPTIMAL,cp_model.FEASIBLE):out.update(S=solver.value(score),chosen=[u for u,v in zip(units,vs) if solver.value(v)])
(OUT/(label+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in out.items() if k not in ('stats','chosen')},ensure_ascii=False),flush=True)
