"""Look for a single witness to each forbidden coincidence, allowing extra placements/flows."""
from geometry import *
from collections import Counter
from functools import lru_cache

stats=Counter()

def has_port(body,p,d,role):
    s,x,y=body
    return (p[0]-x,p[1]-y,d,role) in s.ports

class Case:
    def __init__(self,board,*,trans=(),solid=None,raw=None,extra_heads=None):
        self.board=board
        self.raw=raw             # known positive ore arc (source head, direction)
        self.extra_heads=extra_heads or {}
        self.solid=solid         # fixed ore receiver or fixed core
        self.solidmask=rect(solid[1],solid[2],solid[0].w,solid[0].h) if solid else 0
        self.occupied=board.obstacles|mask(trans)|mask(self.extra_heads)|self.solidmask
        self.tmask=mask(trans)|mask(self.extra_heads)|mask(board.heads)
        assert not self.solidmask & (board.obstacles|self.tmask)
        self.clean_cache={}
    def source_side(self,p): return self.extra_heads.get(p,self.board.heads.get(p))
    def can_flow(self,p,required_clean=None,check_body=None,extra_raw_in=None,orientations=TRANS):
        """Finite support relaxation for one slot. Each mandatory ore inlet needs a legal
        outlet. One demanded clean outlet needs a legal supplier. Hold time + capacity
        forbid a second inlet at a full ordinary cell (on a bridge only in its lane)."""
        if not inside(p) or p in self.board.depots or p==self.board.q: return False
        src=self.source_side(p)
        ores=set()
        if src is not None: ores.add(src)
        if extra_raw_in is not None: ores.add(extra_raw_in)
        rawout=None
        if self.raw:
            root,d=self.raw
            if p==step(root,d): ores.add(opp(d))
            if p==root: rawout=d
        solids=[(self.solid,self.solidmask)] if self.solid else []
        if check_body:
            s,x,y=check_body
            solids.append((check_body,rect(x,y,s.w,s.h)))
        def passable(d,receiving,clean):
            n=step(p,d)
            if not inside(n) or n==self.board.q: return False
            if n in self.board.depots:
                return receiving and not clean and self.board.ports.get(n)==opp(d)
            for body,foot in solids:
                if bit(n)&foot:
                    if not receiving and not clean and body[0].name not in RAW_IN:
                        return False
                    return has_port(body,n,opp(d),not receiving)
            # Missing neighbours left free, even if global conditions would constrain them.
            return True
        rin={d for d in D if passable(d,True,False)}
        rout={d for d in D if passable(d,False,False)}
        cin={d for d in D if passable(d,True,True)}-ores
        for name,orient,routes,bridge in orientations:
            if src is not None and len(ores)>1 and not bridge: continue
            if any(not any(i==a and i in rin and j in rout and
                           (a!=src or rawout is None or j==rawout) for i,j in routes)
                   for a in ores): continue
            if required_clean is None: return True
            if src is not None and not bridge: continue
            if any(i in cin and j==required_clean for i,j in routes): return True
        return False
    def can_feed(self,p,d,body):
        if not inside(p) or p in self.board.depots or p==self.board.q: return False
        if self.source_side(p) is None and not (self.raw and p==step(*self.raw)):
            return True  # unforced one-cell neighbour allowed to supply any clean item
        key=(p,d,body)
        if key not in self.clean_cache:
            self.clean_cache[key]=self.can_flow(p,d,body)
        return self.clean_cache[key]

def check_face(case,f,tag,pole_exempt=False):
    p=f[:2]
    d=f[2]
    n=step(p,d)
    board=case.board
    def verify(condition,reason,detail=()):
        if not condition: raise AssertionError((board.gaps,tag,f,reason,detail))
    stats['checked '+tag]+=1
    verify(inside(p) and p not in board.depots and not (bit(p)&case.solidmask),'tail')
    if not (case.tmask&bit(p)):
        for s,x,y,_,_,r in candidates('cover',p,0,case.occupied):
            verify(pole_exempt and s.name=='供电桩','ineligible origin',(s.name,s.orient,x,y))
    # A 6x6 corner/side tile contains every possible local Q contact, including Q larger
    # than the window. Exclude Q both under the tail and across the directed face.
    verify(min(p)<2 or bool(case.occupied & bit(p)),'tail could lie in Q')
    for x,y,r in q_windows(f):
        verify(r&case.occupied,'Y0 overlap',(x,y))
    verify(not eligible_x(f),'X0 overlap')
    if p!=board.q:
        verify(board.ports.get(n)!=opp(d),'warehouse port')
        if case.solid:
            verify(not any(has_port(case.solid,n,opp(d),role) for role in (0,1)),
                   'fixed body port',case.solid)
        # A solid may not occupy the required transport tail.
        for s,x,y,role,_,r in candidates('interface',p,d,case.occupied|bit(p)):
            verify(False,'nontransport port',(s.name,s.orient,x,y,role))
    for s,x,y,feed,k,r in candidates('weight',p,d,case.occupied):
        other=step(p,d,k)
        if (case.can_feed(p,feed,(s,x,y)) and case.can_feed(other,feed,(s,x,y))):
            verify(False,'weighted face',(s.name,s.orient,x,y,other))
    return f

def check_q(board):
    p=board.q
    # A moving item must have BOTH a possible inlet and a possible outlet in the same
    # inventory. Check even if the sole open face has a bridge on its other side.
    open_sides={d for d in D if inside(step(p,d)) and
                (step(p,d) not in board.depots or board.ports.get(step(p,d))==opp(d))}
    assert len(open_sides)<=1
    for _,_,routes,_ in TRANS:
        assert all(not (i in open_sides and j in open_sides) for i,j in routes)
    return [check_face(Case(board),face(p,d),'q') for d in D]

def branch_options(board,o,normal,tangents,corner=False):
    """One group per ore route. For a direct receiver, enumerate all covering inlets and
    every adjacent gap allowed by that exact position. Signs are alternatives."""
    case0=Case(board)
    z=step(o,normal)
    tag='corner ' if corner else 'ordinary '
    ans={}
    case=Case(board,trans=[z],raw=(o,normal))
    assert case.can_flow(o) and case.can_flow(z)
    ans['forward transport']=[check_face(case,face(o,normal),tag+'forward transport'),
                              check_face(case,face(z,opp(normal)),tag+'forward transport')]
    # Direction of inbound ore uniquely fixes the receiving edge. Wrong-side ports,
    # power poles, core and non-ore recipes are enumerated but cannot absorb ore.
    for s,x,y,_,_,r in candidates('cover',z,0,case0.occupied):
        stats['ore target inspected '+s.name]+=1
        if not has_port((s,x,y),z,opp(normal),True) or s.name not in RAW_IN: continue
        opts=[]
        for t in tangents:
            u=step(o,t)
            if bit(step(u,normal))&r:
                opts.append(t)
                case=Case(board,solid=(s,x,y),raw=(o,normal))
                assert case.can_flow(o)
                ans['body '+str(t)]=[check_face(case,face(u,j),tag+'body') for j in (opp(t),t)]
        assert opts,(o,s,x,y)
    assert any(k.startswith('body') for k in ans)
    for t in tangents:
        u=step(o,t)
        case=Case(board,trans=[u],raw=(o,t))
        assert case.can_flow(o) and case.can_flow(u)
        ans['turn '+str(t)]=[check_face(case,face(u,j),tag+'turn') for j in (opp(t),t)]
    return ans
