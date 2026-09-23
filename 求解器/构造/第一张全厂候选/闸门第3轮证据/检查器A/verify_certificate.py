#!/usr/bin/env python3
"""不调用求解器，从候选重建A的矩阵，复算输出报告中的有理原始/对偶证书。"""
import sys
sys.dont_write_bytecode=True
import json,hashlib,argparse
from pathlib import Path
from fractions import Fraction as Q
from schema import read_bytes,validate
from geometry import Geometry
from check_full import Report,implementation_hash
from flow import Flow,Linear

def verify(raw,report):
 if report['candidate_sha256']!=hashlib.sha256(raw).hexdigest():raise ValueError('候选SHA不匹配')
 if report['implementation_sha256']!=implementation_hash():raise ValueError('检查器版本字节不匹配，须重跑产生新报告')
 d=validate(read_bytes(raw));g=Geometry(d,Report()).build()
 if any(c is None for c in g.cd):raise ValueError('通道声明不完整')
 f=Flow(g).build();f.add_delta();fr=report['flow']
 if fr['status']=='checked':
  x=f.from_witness(fr['witness']);bad=f.m.exact(x)
  if bad or x[f.delta]<=0:raise ValueError('正见证未通过精确核验')
  return {'verified':True,'kind':'rational_primal','delta':str(x[f.delta]),'rows':len(f.m.rows)}
 cert=fr.get('certificate')
 if not cert:raise ValueError('报告没有可复算证书')
 m=f.m;c=[0]*len(m.keys)
 if 'base'in fr:
  m.le([(f.delta,1)],0,'基础可行性 delta=0')
 else:c[f.delta]=-1
 y=[Q()for _ in m.rows];seen=set()
 for v in cert['multipliers']:
  j=v['row']
  if type(j)is not int or not 0<=j<len(y)or j in seen:raise ValueError('乘子行号非法或重复')
  seen.add(j);y[j]=Q(v['value'])
 bound=m.dual(y,c)
 if bound is None or str(bound)!=cert['bound']or('base'in fr and bound<=0)or('base'not in fr and bound<0):raise ValueError('对偶符号、列不等式或右端证书失败')
 return {'verified':True,'kind':'Farkas'if 'base'in fr else'delta_upper_bound','exact_bound':str(bound),'rows':len(m.rows),'variables':len(m.keys),'nonzero_multipliers':len(seen)}
if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('candidate',type=Path);ap.add_argument('report',type=Path);args=ap.parse_args();print(json.dumps(verify(args.candidate.read_bytes(),json.loads(args.report.read_text())),ensure_ascii=False,indent=2))
