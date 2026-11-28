use crate::{
    model::*,
    state::*,
    topology::{ElementGroup, ExitGroup, Tables},
};
use std::collections::BTreeMap;

pub(crate) trait MergerRule {
    type Decision;
    fn record(&self, order: &[Channel], chosen: Option<Channel>) -> Self::Decision;
    fn accepts(&self, c: &Channel, initial: &Self::Decision, current: &Self::Decision) -> bool;
}
pub(crate) struct Twice;
impl MergerRule for Twice {
    type Decision = Option<Channel>;
    fn record(&self, _: &[Channel], chosen: Option<Channel>) -> Self::Decision {
        chosen
    }
    fn accepts(&self, c: &Channel, _: &Self::Decision, current: &Self::Decision) -> bool {
        current.as_ref() == Some(c)
    }
}
fn rotate(cs: &[Channel], last: Option<&Channel>) -> Vec<Channel> {
    let mut order = cs.to_vec();
    if !cs.is_empty() {
        let offset = match last.and_then(|c| cs.iter().position(|ch| ch == c)) {
            Some(i) => i + 1,
            None => 1,
        };
        order.rotate_left(offset % cs.len());
    }
    order
}

impl State {
    fn selections<R: MergerRule>(
        &self,
        t: &Tables,
        p: &Parameters,
        rule: &R,
    ) -> BTreeMap<Id, R::Decision> {
        let mut result = BTreeMap::new();
        for (u, k) in &t.layout.built {
            if *k == Kind::汇流器 {
                let inputs = &t.inputs[u];
                let order = rotate(inputs, inputs.get(self.units[u].last_index));
                let chosen = order.iter().find(|c| self.source(c, p).is_some()).copied();
                result.insert(*u, rule.record(&order, chosen));
            }
        }
        result
    }
    fn judge(
        &mut self,
        t: &Tables,
        p: &Parameters,
        order: &[Channel],
        accept: &impl Fn(&Channel) -> bool,
    ) {
        for c in order {
            if t.layout.kind(&c.1) == Kind::汇流器
                && t.layout.kind(&c.0) != Kind::分流器
                && !accept(c)
            {
                continue;
            }
            if self.move_one(t, p, c) {
                self.settle(t, p)
            }
        }
    }
    fn element_moves(&mut self, t: &Tables, p: &Parameters, accept: &impl Fn(&Channel) -> bool) {
        for (g, cs) in &t.elements {
            let last = match g {
                ElementGroup::Split(u) => {
                    let Body::Transport {
                        device: Transport::Split(last),
                        ..
                    } = &self.units[u].body
                    else {
                        unreachable!("split group")
                    };
                    last.as_ref()
                }
                ElementGroup::Into(u) => t.inputs[u].get(self.units[u].last_index),
            };
            self.judge(t, p, &rotate(cs, last), accept)
        }
    }
    fn facility_groups(
        &mut self,
        t: &Tables,
        p: &Parameters,
        u: &Id,
        groups: &[(ExitGroup, Vec<Channel>)],
        accept: &impl Fn(&Channel) -> bool,
    ) {
        for (g, cs) in groups {
            match g {
                ExitGroup::Merger(_) => self.judge(t, p, cs, accept),
                ExitGroup::Outputs(_) => {
                    let Body::Facility { device, moved } = &self.units[u].body else {
                        unreachable!("exit group")
                    };
                    let mut order: Vec<_> =
                        cs.iter().filter(|c| !moved.contains(c)).copied().collect();
                    if matches!(device, Facility::Machine(_))
                        && !order.is_empty()
                        && order.first() == cs.first()
                    {
                        order.rotate_left(1)
                    }
                    order.extend(moved.iter().filter(|c| cs.contains(c)).copied());
                    self.judge(t, p, &order, accept)
                }
            }
        }
    }
    fn transfer(&mut self, u: &Id, p: &Parameters) {
        let State { units, warehouse } = self;
        let unit = units.get_mut(u).expect("box in layout");
        let Body::Facility {
            device: Facility::Box(b),
            ..
        } = &mut unit.body
        else {
            unreachable!("transfer for a box")
        };
        if b.storage || !b.enabled || !p.powered.contains(u) || b.cooldown != 0 {
            return;
        }
        for s in &mut b.slots {
            if let Some((x, n)) = *s {
                let stored = &mut warehouse[x as usize];
                let room = WAREHOUSE_CAP
                    .checked_sub(*stored)
                    .expect("仓库件数不超过上限");
                let amount = n.min(room);
                *stored += amount;
                take(s, amount);
            }
        }
        b.cooldown = 40;
    }
    fn facility_moves(&mut self, t: &Tables, p: &Parameters, accept: &impl Fn(&Channel) -> bool) {
        for (u, gs) in &t.facilities {
            if t.layout.kind(u) == Kind::协议储存箱 {
                let (_, k) = p
                    .transfer_after
                    .iter()
                    .find(|(id, _)| id == u)
                    .expect("complete box policy");
                let (before, after) = gs.split_at((*k).min(gs.len()));
                self.facility_groups(t, p, u, before, accept);
                self.transfer(u, p);
                self.facility_groups(t, p, u, after, accept)
            } else {
                self.facility_groups(t, p, u, gs, accept)
            }
        }
    }
    fn timers(&mut self, p: &Parameters) {
        for (u, unit) in &mut self.units {
            match &mut unit.body {
                Body::Transport { load, device } => {
                    if let Some(l) = load {
                        l.stopped = (l.stopped + 1).min(8)
                    }
                    if let Transport::Gate(g) = device {
                        for n in &mut g.quotas {
                            *n = n.saturating_sub(1)
                        }
                        g.quotas.retain(|n| *n != 0);
                        g.phase = (g.phase + 1) % 4;
                    }
                }
                Body::Facility { device, .. } => match device {
                    Facility::Box(b) => {
                        if p.powered.contains(u) && b.enabled && !b.storage {
                            b.cooldown = b.cooldown.saturating_sub(1)
                        }
                    }
                    Facility::Machine(m) => {
                        if p.powered.contains(u)
                            && m.enabled
                            && let Batch::Running(_, n) = &mut m.batch
                        {
                            *n = n.saturating_sub(1)
                        }
                    }
                    Facility::Core(_) | Facility::Pickup(_) => {}
                },
            }
        }
    }
    pub fn step(&mut self, t: &Tables, p: &Parameters, rule: &impl MergerRule) {
        self.settle(t, p);
        let initial = self.selections(t, p, rule);
        self.element_moves(t, p, &|c| rule.accepts(c, &initial[&c.1], &initial[&c.1]));
        let current = self.selections(t, p, rule);
        self.facility_moves(t, p, &|c| rule.accepts(c, &initial[&c.1], &current[&c.1]));
        for (u, _) in &t.facilities {
            if let Body::Facility {
                device: Facility::Machine(m),
                ..
            } = &mut self.unit_mut(u).body
            {
                m.finish(p.powered.contains(u))
            }
        }
        for (u, _) in &t.facilities {
            if let Body::Facility {
                device: Facility::Machine(m),
                ..
            } = &mut self.unit_mut(u).body
            {
                m.start(p.powered.contains(u))
            }
        }
        self.timers(p);
    }
}
