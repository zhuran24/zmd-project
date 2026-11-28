use crate::{model::*, state::*, topology::Tables};

#[derive(Clone, Copy)]
pub(crate) enum Place {
    Belt,
    Box(usize),
    Stock(usize),
    Output,
    Warehouse,
}
impl Place {
    fn cell(self, u: &Id) -> Option<Cell> {
        let slot = match self {
            Self::Belt => Slot::Grid(0),
            Self::Box(i) => Slot::Grid(i),
            Self::Stock(i) => Slot::Stock(i),
            Self::Output => Slot::Output,
            Self::Warehouse => return None,
        };
        Some(Cell(*u, slot))
    }
}
impl State {
    pub fn source(&self, c: &Channel, p: &Parameters) -> Option<(Item, Place)> {
        match &self.units[&c.0].body {
            Body::Transport { load, .. } => load
                .as_ref()
                .filter(|l| l.stopped == 8)
                .map(|l| (l.item, Place::Belt)),
            Body::Facility { device, .. } => match device {
                Facility::Box(b) => b
                    .slots
                    .iter()
                    .enumerate()
                    .find_map(|(i, s)| s.map(|(x, _)| (x, Place::Box(i)))),
                Facility::Machine(m) => m.output.map(|(x, _)| (x, Place::Output)),
                Facility::Core(ports) => {
                    let (_, i) = p
                        .ports
                        .iter()
                        .find(|(ch, _)| ch == c)
                        .expect("complete outlet map");
                    ports[*i]
                        .filter(|x| self.warehouse[*x as usize] > 0)
                        .map(|x| (x, Place::Warehouse))
                }
                Facility::Pickup(port) => port
                    .filter(|x| self.warehouse[*x as usize] > 0)
                    .map(|x| (x, Place::Warehouse)),
            },
        }
    }
    pub fn destination(&self, u: &Id, x: Item) -> Option<Place> {
        match &self.units[u].body {
            Body::Transport { load, device } => {
                if load.is_some() {
                    return None;
                }
                if let Transport::Gate(g) = device
                    && !g.accepts(x)
                {
                    return None;
                }
                Some(Place::Belt)
            }
            Body::Facility { device, .. } => match device {
                Facility::Box(b) => b
                    .slots
                    .iter()
                    .position(|s| s.is_none_or(|(item, n)| item == x && n < 50))
                    .map(Place::Box),
                Facility::Machine(m) => {
                    if let Some((i, (_, n))) = m
                        .stock
                        .iter()
                        .enumerate()
                        .find_map(|(i, s)| s.filter(|(y, _)| *y == x).map(|p| (i, p)))
                    {
                        (n < 50).then_some(Place::Stock(i))
                    } else {
                        m.stock.iter().position(Option::is_none).map(Place::Stock)
                    }
                }
                Facility::Pickup(_) => None,
                Facility::Core(_) => {
                    (self.warehouse[x as usize] < WAREHOUSE_CAP).then_some(Place::Warehouse)
                }
            },
        }
    }
    pub fn deposit(&mut self, u: &Id, dst: Place, item: Item, from: Option<Cell>) {
        if matches!(dst, Place::Warehouse) {
            self.warehouse[item as usize] += 1;
            return;
        }
        match (dst, &mut self.unit_mut(u).body) {
            (Place::Belt, Body::Transport { load, device }) => {
                assert!(load.is_none());
                *load = Some(Load {
                    item,
                    stopped: 0,
                    from,
                });
                if let Transport::Gate(g) = device {
                    g.received()
                }
            }
            (
                Place::Box(i),
                Body::Facility {
                    device: Facility::Box(b),
                    ..
                },
            ) => add(&mut b.slots[i], item, 1),
            (
                Place::Stock(i),
                Body::Facility {
                    device: Facility::Machine(m),
                    ..
                },
            ) => add(&mut m.stock[i], item, 1),
            _ => unreachable!("destination must have been selected for this unit"),
        }
    }
    fn withdraw(&mut self, u: &Id, src: Place, item: Item) {
        if matches!(src, Place::Warehouse) {
            let stored = &mut self.warehouse[item as usize];
            *stored = stored.checked_sub(1).expect("仓库里有这件货才会被取走");
            return;
        }
        match (src, &mut self.unit_mut(u).body) {
            (Place::Belt, Body::Transport { load, .. }) => *load = None,
            (
                Place::Box(i),
                Body::Facility {
                    device: Facility::Box(b),
                    ..
                },
            ) => take(&mut b.slots[i], 1),
            (
                Place::Output,
                Body::Facility {
                    device: Facility::Machine(m),
                    ..
                },
            ) => take(&mut m.output, 1),
            _ => unreachable!("source must have been selected for this unit"),
        }
    }
    pub fn move_one(&mut self, t: &Tables, p: &Parameters, c: &Channel) -> bool {
        let Some((item, src)) = self.source(c, p) else {
            return false;
        };
        let Some(dst) = self.destination(&c.1, item) else {
            return false;
        };
        if let Body::Transport { load: Some(l), .. } = &self.units[&c.0].body
            && let Some(from) = &l.from
            && dst.cell(&c.1).as_ref() == Some(from)
        {
            return false;
        }
        self.withdraw(&c.0, src, item);
        self.deposit(&c.1, dst, item, src.cell(&c.0));
        match &mut self.unit_mut(&c.0).body {
            Body::Transport {
                device: Transport::Split(last),
                ..
            } => *last = Some(*c),
            Body::Transport {
                device: Transport::Plain | Transport::Gate(_),
                ..
            } => {}
            Body::Facility { moved, .. } => {
                if t.layout.kind(&c.1) != Kind::汇流器 {
                    moved.retain(|ch| ch != c);
                    moved.push(*c);
                }
            }
        }
        if let Some(i) = t.inputs[&c.1].iter().position(|ch| ch == c) {
            self.unit_mut(&c.1).last_index = i
        }
        true
    }
    pub fn settle(&mut self, t: &Tables, p: &Parameters) {
        loop {
            let mut moved = false;
            for c in &t.belts {
                if self.move_one(t, p, c) {
                    moved = true
                }
            }
            if !moved {
                return;
            }
        }
    }
}
