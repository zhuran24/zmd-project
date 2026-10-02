"""Independent review implementations. No imports from derivation or sim2.
Machine order: C, A, B, K. Routes: CA, AC, CB, BK, then K outlets.
Model A uses residence ages and remaining work; Model B uses tokens/time stamps.
External outlet removals are a superset of legal downstream behavior, not layouts.
"""
from dataclasses import dataclass
from copy import deepcopy

SOURCE = (0, 1, 0, 2)
TARGET = (1, 0, 2, 3)

class AgeModel:
    def __init__(self, config):
        self.t = 0
        self.k = config['k']
        self.q = [2, 1, 1, self.k]
        self.i = list(config['inputs'])
        self.o = list(config['outputs'])
        # -1 empty, 0 finished, 1..8 remaining steps
        self.r = list(config['remaining'])
        self.roads = deepcopy(config['roads'])
        self.last = list(config.get('last', [-100] * (len(self.roads))))
        self.batches = [0] * 4
        self.sends = [0] * len(self.roads)
        self.events = []

    def flush(self, v):
        if self.r[v] == 0 and self.o[v] + self.q[v] <= 50:
            self.o[v] += self.q[v]
            self.r[v] = -1

    def step(self, drain, connection, powered=(True, True, True, True), order=(0,1,2,3)):
        self.t += 1
        self.events = []
        for v in range(4):
            if powered[v] and self.r[v] > 0:
                self.r[v] -= 1
                if self.r[v] == 0:
                    self.batches[v] += 1
            self.flush(v)
        for row in self.roads:
            for j in range(len(row)):
                if row[j] >= 0:
                    row[j] = min(8, row[j] + 1)
        for e, road in enumerate(self.roads):
            for j in reversed(range(len(road))):
                if road[j] < 8:
                    continue
                if j + 1 < len(road):
                    if road[j+1] >= 0:
                        continue
                    road[j+1] = 0
                elif e < 4:
                    v = TARGET[e]
                    if self.i[v] == 50:
                        continue
                    self.i[v] += 1
                else:
                    if not drain[e-4]:
                        continue
                road[j] = -1
        empty_before = [row[0] < 0 for row in self.roads]
        for v in order:
            choices = [e for e in range(len(self.roads)) if (SOURCE[e] if e < 4 else 3) == v]
            choices.sort(key=lambda e:(self.last[e], connection[e]))
            if self.o[v]:
                for e in choices:
                    if self.roads[e][0] < 0:
                        self.o[v] -= 1
                        self.roads[e][0] = 0
                        self.last[e] = self.t
                        self.sends[e] += 1
                        self.events.append(e)
                        self.flush(v)
                        break
        for v in range(4):
            if powered[v] and self.r[v] < 0 and self.i[v]:
                self.i[v] -= 1
                self.r[v] = 8
        return empty_before

    def state(self):
        return {'inputs':self.i[:], 'outputs':self.o[:], 'remaining':self.r[:],
                'roads':deepcopy(self.roads), 'last':self.last[:],
                'batches':self.batches[:], 'sends':self.sends[:]}

    def phi2(self):
        return 2*(sum(x>=0 for x in self.roads[0])+sum(x>=0 for x in self.roads[1])+
                  self.i[1]+self.o[1]+self.i[0]+(self.r[0]>=0)+(self.r[1]>=0))+self.o[0]

@dataclass
class Token:
    entered: int

@dataclass
class Job:
    due: int

class TimestampModel:
    def __init__(self, config):
        self.time = 0
        self.products = (2,1,1,config['k'])
        self.raw = [[1]*n for n in config['inputs']]
        self.finished = [[1]*n for n in config['outputs']]
        self.jobs = [None if r < 0 else Job(r) for r in config['remaining']]
        self.slots = [[None if age < 0 else Token(-age) for age in row] for row in config['roads']]
        self.history = list(config.get('last', [-100]*len(self.slots)))
        self.completed = [0,0,0,0]
        self.sent = [0]*len(self.slots)
        self.events = []

    def release(self, v):
        job = self.jobs[v]
        if job is not None and job.due <= self.time:
            if 50-len(self.finished[v]) >= self.products[v]:
                self.finished[v].extend([1]*self.products[v])
                self.jobs[v] = None

    def step(self, drain, connection, powered=(True,True,True,True), order=(0,1,2,3)):
        self.time += 1
        self.events = []
        for v, job in enumerate(self.jobs):
            if job is not None and job.due >= self.time:
                if not powered[v]:
                    job.due += 1
                elif job.due == self.time:
                    self.completed[v] += 1
            self.release(v)
        # Ordered events of already present tokens; no token can move twice.
        for edge, cells in enumerate(self.slots):
            j = len(cells)-1
            while j >= 0:
                item = cells[j]
                if item is not None and self.time-item.entered >= 8:
                    accepted = False
                    if j == len(cells)-1:
                        if edge >= 4:
                            accepted = bool(drain[edge-4])
                        else:
                            dst = (1,0,2,3)[edge]
                            if len(self.raw[dst]) < 50:
                                self.raw[dst].append(1)
                                accepted = True
                    elif cells[j+1] is None:
                        cells[j+1] = Token(self.time)
                        accepted = True
                    if accepted:
                        cells[j] = None
                j -= 1
        availability = [cells[0] is None for cells in self.slots]
        for machine in order:
            if len(self.finished[machine]) == 0:
                continue
            incident = {0:[0,2],1:[1],2:[3],3:list(range(4,len(self.slots)))}[machine]
            possible = [e for e in incident if self.slots[e][0] is None]
            if possible:
                chosen = min(possible, key=lambda e:(self.history[e],connection[e]))
                self.finished[machine].pop()
                self.slots[chosen][0] = Token(self.time)
                self.history[chosen] = self.time
                self.sent[chosen] += 1
                self.events.append(chosen)
                self.release(machine)
        for v in range(4):
            if powered[v] and self.jobs[v] is None and self.raw[v]:
                self.raw[v].pop()
                self.jobs[v] = Job(self.time+8)
        return availability

    def state(self):
        return {'inputs':list(map(len,self.raw)), 'outputs':list(map(len,self.finished)),
                'remaining':[-1 if job is None else max(0, job.due-self.time) for job in self.jobs],
                'roads':[[(-1 if it is None else min(8,self.time-it.entered)) for it in row] for row in self.slots],
                'last':self.history[:], 'batches':self.completed[:], 'sends':self.sent[:]}

    def phi2(self):
        pieces = (sum(it is not None for it in self.slots[0]) + len(self.raw[1])+
                  len(self.finished[1])+sum(it is not None for it in self.slots[1])+
                  len(self.raw[0]) + (self.jobs[0] is not None)+(self.jobs[1] is not None))
        return pieces*2+len(self.finished[0])
