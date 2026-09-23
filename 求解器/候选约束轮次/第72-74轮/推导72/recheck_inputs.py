#!/usr/bin/env python3
"""Reuse the independent R71 rational checker, redirecting every output here."""
import importlib.util, json, time, hashlib
from pathlib import Path
OUT=Path(__file__).resolve().parent
OLD=OUT.parents[1]/'第69-71轮/复核71/recompute.py'
spec=importlib.util.spec_from_file_location('r71_certificate_checker',OLD); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.OUT=OUT
start=m.manifest(); start[str(OLD.relative_to(m.ROOT))]={'bytes':OLD.stat().st_size,'sha256':hashlib.sha256(OLD.read_bytes()).hexdigest()}
m.save('input_manifest.json',start)
t=time.monotonic();local=m.local_checks();group=m.group_checks();m.edge_checks(local,group);m.accounting_checks();m.point_checks(local,group)
m.save('input_certificate_verification.json',dict(status='PASS',seconds=time.monotonic()-t,local_positions=len(local),group_positions=len(group)))
print('PASS',flush=True)
