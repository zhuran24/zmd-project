#!/usr/bin/env python3
"""Rebuild R66 joint DP with 13-machine active boundary-pole bound."""
from pathlib import Path
import sys,json
OUT=Path(__file__).resolve().parent
OLD=OUT.parents[1]/'第66-68轮'/'推导66'
sys.path.insert(0,str(OLD))
import joint17_j as j
oldloss=j.loss
local="--local" in sys.argv
caps={}
if local:
 for c in json.loads((OUT/"supply_strip_certificates.json").read_text()):
  for xy in c["positions"]:caps[tuple(xy)]=c["integer_upper"]
def loss(rr):
 return max(oldloss(rr),10 if rr[0] in (1,68) or rr[1] in (1,68) else 0,23-caps.get(tuple(rr[:2]),23))
j.loss=loss;j.OUT=OUT
# same exact DP, omitted boundary poles now cost at least 10 rather than 9
source=(OLD/'joint17_j.py').read_text()
source=source[source.index('def run():'):].replace('//9','//10').replace("'joint17_j_certificate.json'","'new_edge_certificate.json'")
if local:source=source.replace("new_edge_certificate.json","new_edge_local_certificate.json")
exec(source,j.__dict__)
j.run()
