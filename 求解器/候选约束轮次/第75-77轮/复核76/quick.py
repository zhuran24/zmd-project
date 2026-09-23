"""Alternative search policy on the unchanged independent review matrix."""
from model import *
from ortools.sat.python import cp_model
import ortools
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--P',type=int,default=10);ap.add_argument('--j',type=int);ap.add_argument('--cap',type=int,default=184);ap.add_argument('--name',required=True);a=ap.parse_args()
    start=time.monotonic();m,us,gain=build(a.P,a.cap,a.j)
    c=cp_model.CpModel();vs=[c.new_int_var(0,b,n) for b,n in zip(m.ub,m.names)]
    for r,lo,hi in zip(m.rows,m.lo,m.hi):
        e=sum(vs[i]*v for i,v in r.items())
        if lo is not None:c.add(e>=lo)
        if hi is not None:c.add(e<=hi)
    s=cp_model.CpSolver();s.parameters.num_search_workers=1;s.parameters.max_time_in_seconds=600;s.parameters.subsolvers.append('quick_restart');s.parameters.log_search_progress=True;s.parameters.linearization_level=2
    st=s.solve(c)
    r=dict(arguments=vars(a),status=s.status_name(st),seconds=time.monotonic()-start,stats=s.response_stats(),version=ortools.__version__,matrix_sha256=hashlib.sha256(json.dumps([m.ub,m.rows,m.lo,m.hi],sort_keys=True).encode()).hexdigest(),source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT/'geometry.py',OUT/'model.py',Path(__file__))})
    dump(a.name+'.json',r);print({k:v for k,v in r.items() if k!='stats'},flush=True)
if __name__=='__main__':main()
