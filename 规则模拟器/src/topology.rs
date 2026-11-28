//! 历史、拓扑与级别、历史.立表。两类组分别进入各自的轮询阶段。
use crate::{Res, model::*};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone)]
pub(crate) struct Layout {
    pub built: Vec<(Id, Kind)>,
    pub channels: Vec<Channel>,
}
#[derive(Clone, PartialEq, Eq, Debug)]
pub(crate) enum ElementGroup {
    Split(Id),
    Into(Id),
}
#[derive(Clone, PartialEq, Eq, Debug)]
pub(crate) enum ExitGroup {
    Outputs(Id),
    Merger(Channel),
}
#[derive(Clone, PartialEq, Eq, Debug)]
enum Group {
    Element(ElementGroup),
    Exit(ExitGroup),
}

impl Layout {
    fn empty() -> Self {
        Self {
            built: vec![],
            channels: vec![],
        }
    }
    fn lookup(&self, u: &Id) -> Option<Kind> {
        self.built.iter().find(|(id, _)| id == u).map(|(_, k)| *k)
    }
    pub fn kind(&self, u: &Id) -> Kind {
        self.lookup(u).expect("unit in layout")
    }
    fn apply(&mut self, event: &Event) -> Res<()> {
        match event {
            Event::Build(u, k) => {
                if self.lookup(u).is_some()
                    || (*k == Kind::协议核心 && self.built.iter().any(|(_, v)| v == k))
                {
                    return Err("编号已占用或协议核心重复".into());
                }
                self.built.push((*u, *k));
            }
            Event::Connect(c) => {
                let a = self.lookup(&c.0).ok_or("起点不存在")?;
                let b = self.lookup(&c.1).ok_or("终点不存在")?;
                if c.0 == c.1 || !(a.transport() || b.transport()) || self.channels.contains(c) {
                    return Err("通道不可接通".into());
                }
                self.channels.push(*c);
            }
            Event::Reconnect(c) => {
                if !self.channels.contains(c) {
                    return Err("重接的通道不存在".into());
                }
                self.channels.retain(|ch| ch != c);
                self.channels.push(*c);
            }
            Event::Remove(u) => {
                let index = self
                    .built
                    .iter()
                    .position(|(id, _)| id == u)
                    .ok_or("拆除的单位不存在")?;
                self.built.remove(index);
                self.channels.retain(|c| &c.0 != u && &c.1 != u);
            }
        }
        Ok(())
    }
    pub fn incoming(&self, u: &Id) -> Vec<&Channel> {
        self.channels.iter().filter(|c| &c.1 == u).collect()
    }
    pub fn outgoing(&self, u: &Id) -> Vec<&Channel> {
        self.channels.iter().filter(|c| &c.0 == u).collect()
    }
    pub fn component(&self, mut fuel: usize, u: &Id) -> Option<Id> {
        let mut at = u;
        while fuel > 0 {
            let k = self.kind(at);
            if !k.transport() {
                return None;
            }
            if k == Kind::传送带
                && let Some(c) = self
                    .outgoing(at)
                    .into_iter()
                    .find(|c| self.kind(&c.1) == Kind::传送带)
            {
                at = &c.1;
                fuel -= 1;
            } else {
                return Some(*at);
            }
        }
        None
    }
    pub fn downstream(&self, e: &Id) -> Vec<Id> {
        self.outgoing(e)
            .iter()
            .filter_map(|c| self.component(self.built.len() + 1, &c.1))
            .collect()
    }
    fn terminal(&self, e: &Id) -> bool {
        if self.component(1, e).as_ref() != Some(e) {
            return false;
        }
        let out = self.outgoing(e);
        let to_facility = |c: &&Channel| !self.kind(&c.1).transport();
        out.iter().any(to_facility) && (self.kind(e) == Kind::分流器 || out.iter().all(to_facility))
    }
    fn endpoint(&self, e: &Id) -> Option<Id> {
        if !self.terminal(e) {
            return None;
        }
        if self.kind(e) == Kind::分流器 {
            return Some(*e);
        }
        match self.outgoing(e).as_slice() {
            [c] => Some(c.1),
            _ => None,
        }
    }
    // Visit exactly the paths of 运输带从, including its finite fuel on cycles.
    fn paths(&self, e: &Id, fuel: usize, length: usize, visit: &mut impl FnMut(&Id, usize)) {
        if fuel == 0 {
            return;
        }
        if self.terminal(e) {
            visit(e, length);
            return;
        }
        for next in self.downstream(e) {
            self.paths(&next, fuel - 1, length + 1, visit)
        }
    }
    fn group(&self, c: &Channel) -> Option<Group> {
        let a = self.kind(&c.0);
        let b = self.kind(&c.1);
        if a == Kind::分流器 {
            Some(Group::Element(ElementGroup::Split(c.0)))
        } else if a == Kind::传送带 && b == Kind::传送带 {
            None
        } else if a.transport() {
            Some(Group::Element(ElementGroup::Into(c.1)))
        } else if b == Kind::汇流器 {
            Some(Group::Exit(ExitGroup::Merger(*c)))
        } else {
            Some(Group::Exit(ExitGroup::Outputs(c.0)))
        }
    }
    pub fn inputs(&self, u: &Id) -> Vec<Channel> {
        self.incoming(u)
            .into_iter()
            .filter(|c| {
                if self.kind(u) == Kind::汇流器 {
                    self.kind(&c.0) != Kind::分流器
                } else {
                    matches!(self.group(c), Some(Group::Element(ElementGroup::Into(_))))
                }
            })
            .copied()
            .collect()
    }
    pub fn same_network(&self, b: &Self) -> bool {
        self.built.len() == b.built.len()
            && self.built.iter().all(|unit| b.built.contains(unit))
            && self.channels.len() == b.channels.len()
            && self.channels.iter().all(|c| b.channels.contains(c))
    }
    fn within_ports(&self) -> bool {
        self.built.iter().all(|(u, k)| {
            let (a, b) = k.ports();
            self.incoming(u).len() <= a && self.outgoing(u).len() <= b
        })
    }
    fn connected_belts_reach_terminal(&self) -> bool {
        self.built.iter().all(|(u, k)| {
            if !k.transport() || (self.incoming(u).is_empty() && self.outgoing(u).is_empty()) {
                return true;
            }
            let fuel = self.built.len() + 1;
            let Some(e) = self.component(fuel, u) else {
                return false;
            };
            let mut found = false;
            self.paths(&e, fuel, 1, &mut |_, _| found = true);
            found
        })
    }
}

pub(crate) struct History(Vec<Layout>);
impl History {
    pub fn read(events: &[Event]) -> Res<Self> {
        let mut all = vec![Layout::empty()];
        for (i, e) in events.iter().enumerate() {
            let mut next = all.last().expect("empty prefix exists").clone();
            next.apply(e)
                .map_err(|s| format!("历史第 {} 件事 {s}", i + 1))?;
            all.push(next);
        }
        Ok(Self(all))
    }
    pub fn now(&self) -> &Layout {
        self.0.last().expect("empty prefix exists")
    }
    pub fn legal(&self) -> bool {
        self.0.iter().all(Layout::within_ports) && self.now().connected_belts_reach_terminal()
    }
    fn since(&self, mut test: impl FnMut(&Layout) -> bool) -> Option<usize> {
        let mut first = None;
        for (t, l) in self.0.iter().enumerate().rev() {
            if !test(l) {
                break;
            }
            first = Some(t)
        }
        first
    }
    fn endpoint_time(&self, x: &Id) -> Option<usize> {
        let split = self.now().kind(x) == Kind::分流器;
        self.since(|l| {
            if split {
                l.outgoing(x).iter().any(|c| !l.kind(&c.1).transport())
            } else {
                l.built
                    .iter()
                    .any(|(e, _)| l.endpoint(e).as_ref() == Some(x))
            }
        })
    }
    fn rank(&self, e: &Id, missing: &impl Fn(&Layout, &Id) -> Option<usize>) -> Option<usize> {
        let l = self.now();
        let mut best = None;
        l.paths(e, l.built.len() + 1, 1, &mut |end, n| {
            if let Some(t) = l.endpoint(end).and_then(|x| self.endpoint_time(&x)) {
                let candidate = (t, n);
                if best.is_none_or(|b| candidate < b) {
                    best = Some(candidate)
                }
            }
        });
        match best {
            Some((_, n)) => Some(n),
            None => missing(l, e),
        }
    }
    fn level(
        &self,
        g: &Group,
        cs: &[Channel],
        missing: &impl Fn(&Layout, &Id) -> Option<usize>,
    ) -> Option<(usize, usize)> {
        let l = self.now();
        let mut ranks = Vec::new();
        for c in cs {
            ranks.push(match g {
                Group::Element(_) => self.rank(&c.0, missing)?,
                Group::Exit(_) => self.rank(&l.component(l.built.len() + 1, &c.1)?, missing)?,
            });
        }
        let n = match g {
            Group::Element(_) => {
                let first = *ranks.first()?;
                if !ranks.iter().all(|n| *n == first) {
                    return None;
                }
                first
            }
            Group::Exit(_) => *ranks.iter().max()?,
        };
        let t = self.since(|l| l.channels.iter().any(|c| l.group(c).as_ref() == Some(g)))?;
        Some((n, t))
    }
}

type Channels<G> = Vec<(G, Vec<Channel>)>;
pub(crate) struct Tables {
    pub layout: Layout,
    pub belts: Vec<Channel>,
    pub elements: Channels<ElementGroup>,
    pub facilities: Vec<(Id, Channels<ExitGroup>)>,
    pub inputs: BTreeMap<Id, Vec<Channel>>,
}
impl Tables {
    pub fn build(
        h: &History,
        missing: impl Fn(&Layout, &Id) -> Option<usize>,
        unranked: impl Fn(&[Channel]) -> Res<()>,
    ) -> Res<Self> {
        let l = h.now();
        let mut groups: Channels<Group> = vec![];
        let mut belts = vec![];
        for c in &l.channels {
            match l.group(c) {
                None => belts.push(*c),
                Some(g) => {
                    if let Some((_, cs)) = groups.iter_mut().find(|(k, _)| k == &g) {
                        cs.push(*c)
                    } else {
                        groups.push((g, vec![*c]))
                    }
                }
            }
        }
        let mut ranked = Vec::new();
        for (g, cs) in groups {
            match h.level(&g, &cs, &missing) {
                Some(lv) => ranked.push((lv, g, cs)),
                None => unranked(&cs)?,
            }
        }
        ranked.sort_by_key(|p| p.0);
        let mut elements = vec![];
        let mut facilities: Vec<(_, Channels<ExitGroup>)> = l
            .built
            .iter()
            .filter(|(_, k)| !k.transport())
            .map(|(u, _)| (*u, vec![]))
            .collect();
        for (_, g, cs) in ranked {
            match g {
                Group::Element(eg) => elements.push((eg, cs)),
                Group::Exit(fg) => {
                    let src = match &fg {
                        ExitGroup::Outputs(u) => u,
                        ExitGroup::Merger(c) => &c.0,
                    };
                    facilities
                        .iter_mut()
                        .find(|p| &p.0 == src)
                        .expect("group has a source")
                        .1
                        .push((fg, cs));
                }
            }
        }
        let inputs = l.built.iter().map(|(u, _)| (*u, l.inputs(u))).collect();
        Ok(Self {
            layout: l.clone(),
            belts,
            elements,
            facilities,
            inputs,
        })
    }
}

impl Parameters {
    pub(crate) fn check(&self, l: &Layout) -> Res<()> {
        if !self.powered.windows(2).all(|p| p[0] < p[1])
            || !self.powered.iter().all(|u| l.lookup(u).is_some())
        {
            return Err("供电含未知、重复或乱序单位".into());
        }
        let boxes = l
            .built
            .iter()
            .filter(|(_, k)| *k == Kind::协议储存箱)
            .map(|(u, _)| u)
            .collect::<BTreeSet<_>>();
        if !boxes
            .into_iter()
            .eq(self.transfer_after.iter().map(|p| &p.0))
        {
            return Err("须按序列全箱的传输位置".into());
        }
        let outlets: BTreeSet<_> = l
            .channels
            .iter()
            .filter(|c| l.kind(&c.0).outlets() > 0)
            .collect();
        if !outlets.into_iter().eq(self.ports.iter().map(|(c, _)| c)) {
            return Err("须按序列全取货通道".into());
        }
        if self.ports.iter().any(|(c, i)| *i >= l.kind(&c.0).outlets()) {
            return Err("取货口号越界".into());
        }
        Ok(())
    }
}
