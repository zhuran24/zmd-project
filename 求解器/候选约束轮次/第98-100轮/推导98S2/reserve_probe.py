#!/usr/bin/env python3
"""Finite stock does not repair the S95 adversarial shared-send service model.

The other endpoints have external service calendars. This is a proof-obligation
counterexample, NOT a factory counterexample or a legal geometric layout.
"""
import json
from fractions import Fraction
from pathlib import Path

HERE=Path(__file__).resolve().parent

def simulate(n, stock0, duration, steps=12000):
    P=7+n
    cells=[None]+[0]*(n-1)
    history=[-1]*n
    stock=stock0
    due=None
    starts=[]; sent=[]; got=[]; refused=0; first_gap=None
    last_start=None
    for t in range(steps):
        if due==t: due=None
        for i,c in enumerate(cells):
            if c is not None and t-c>=8:
                can=(stock<50) if i==0 else (t>=8 and (t-8)%P==0)
                if can:
                    cells[i]=None
                    if i==0: stock+=1; got.append(t)
                elif i==0: refused+=1
        available=[i for i,c in enumerate(cells) if c is None]
        if available:
            i=min(available,key=lambda j:(history[j],j))
            cells[i]=t; history[i]=t
            if i==0: sent.append(t)
        if due is None and stock:
            stock-=1; due=t+duration; starts.append(t)
            if last_start is not None and t-last_start>duration and first_gap is None:
                first_gap=[last_start,t]
            last_start=t
    return {'n':n,'initial_stock':stock0,'duration':duration,'P':P,
            'first_manufacture_gap':first_gap,'target_refusals':refused,
            'first_send_times':sent[:15],'last_send_gaps':[b-a for a,b in zip(sent[-21:],sent[-20:])],
            'last_start_gaps':[b-a for a,b in zip(starts[-21:],starts[-20:])],
            'target_rate':str(Fraction(8,P)),
            'all_send_times':sent,'all_receive_times':got,'all_start_times':starts}

def event_check(n, stock0, duration, steps):
    # Independent closed-form sends from S95's chronological proof. A priority
    # queue of manufacturing completions is unnecessary for a single processor:
    # sorted release times, FIFO service with deterministic processing duration.
    P=7+n
    arrivals=[0]*stock0+[8+j*P for j in range((steps-9)//P+1)]
    previous=-duration
    starts=[]
    for release in arrivals:
        previous=max(release,previous+duration)
        if previous>=steps: break
        starts.append(previous)
    sends=list(range(0,steps,P))
    return sends,[8+j*P for j in range((steps-9)//P+1)],starts

cases=[]
for n in (2,3,6):
    for duration in (8,4):
        a=simulate(n,50,duration)
        b=event_check(n,50,duration,12000)
        assert (a['all_send_times'],a['all_receive_times'],a['all_start_times'])==b
        cases.append({k:v for k,v in a.items() if not k.startswith('all_')})
(HERE/'reserve_probe.json').write_text(json.dumps({'scope':'external_endpoint_service_model_only','two_encodings_equal':True,'cases':cases},ensure_ascii=False,indent=2)+'\n')
print(json.dumps(cases,ensure_ascii=False))
