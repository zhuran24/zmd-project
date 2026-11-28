//! Canonical, resident state. The twelve wire tables exist only at the boundary.
use crate::{Res, model::*};
use std::collections::BTreeMap;

#[derive(Clone, PartialEq, Eq)]
pub(crate) enum Filter {
    Open,
    Item(Item, Option<usize>, Option<usize>),
}
impl Filter {
    pub fn new(item: Option<Item>, total: Option<usize>, rate: Option<usize>) -> Res<Self> {
        if total.is_some_and(|n| !(1..=5000).contains(&n)) || rate.is_some_and(|n| n > 5) {
            return Err("准入口上限越界".into());
        }
        match item {
            Some(i) => Ok(Self::Item(i, total, rate)),
            None if total.is_none() && rate.is_none() => Ok(Self::Open),
            None => Err("未设放行物品不能设上限".into()),
        }
    }
    pub fn fields(&self) -> (Option<Item>, Option<usize>, Option<usize>) {
        match self {
            Self::Open => (None, None, None),
            Self::Item(i, a, b) => (Some(*i), *a, *b),
        }
    }
}
pub(crate) struct Gate {
    pub filter: Filter,
    pub count: usize,
    pub quotas: Vec<u32>,
    pub phase: u32,
}
impl Gate {
    pub fn accepts(&self, item: Item) -> bool {
        match self.filter {
            Filter::Open => true,
            Filter::Item(x, total, rate) => {
                item == x
                    && total.is_none_or(|n| self.count < n)
                    && rate.is_none_or(|n| self.quotas.len() < n)
            }
        }
    }
    pub fn received(&mut self) {
        let (_, a, b) = self.filter.fields();
        if let Some(limit) = a {
            assert!(self.count < limit);
            self.count += 1;
        }
        if b.is_some() {
            self.quotas.push(37 + (6 - self.phase) % 4)
        }
    }
}

pub(crate) struct Load {
    pub item: Item,
    pub stopped: usize,
    pub from: Option<Cell>,
}
pub(crate) enum Transport {
    Plain,
    Split(Option<Channel>),
    Gate(Gate),
}
pub(crate) enum Batch {
    Idle,
    Running(&'static Recipe, u32), // cache is exactly this recipe's ordered materials
    Finished(Stack),               // cache holds an entire batch waiting for the output
}
pub(crate) struct Machine {
    pub kind: Kind,
    pub enabled: bool,
    pub stock: Vec<Option<Stack>>,
    pub output: Option<Stack>,
    pub batch: Batch,
}
pub(crate) struct BoxState {
    pub slots: [Option<Stack>; 6],
    pub enabled: bool,
    pub storage: bool,
    pub cooldown: u32,
}
pub(crate) enum Facility {
    Machine(Machine),
    Box(BoxState),
    Core([Option<Item>; CORE_OUTLETS]),
    Pickup(Option<Item>),
}
pub(crate) enum Body {
    Transport {
        load: Option<Load>,
        device: Transport,
    },
    Facility {
        device: Facility,
        moved: Vec<Channel>,
    },
}
pub(crate) struct Unit {
    pub last_index: usize,
    pub body: Body,
}
pub(crate) struct State {
    pub units: BTreeMap<Id, Unit>,
    pub warehouse: [usize; ITEMS.len()],
}

impl State {
    pub fn unit_mut(&mut self, u: &Id) -> &mut Unit {
        self.units.get_mut(u).expect("unit in validated layout")
    }
}
impl Unit {
    pub fn gate(&mut self) -> Res<&mut Gate> {
        if let Body::Transport {
            device: Transport::Gate(g),
            ..
        } = &mut self.body
        {
            Ok(g)
        } else {
            Err("需要物品准入口".into())
        }
    }
    pub fn switch(&mut self) -> Res<&mut bool> {
        match &mut self.body {
            Body::Facility {
                device: Facility::Machine(m),
                ..
            } => Ok(&mut m.enabled),
            Body::Facility {
                device: Facility::Box(b),
                ..
            } => Ok(&mut b.enabled),
            Body::Transport { .. }
            | Body::Facility {
                device: Facility::Core(_) | Facility::Pickup(_),
                ..
            } => Err("该单位没有开关".into()),
        }
    }
}

pub(crate) fn take(stack: &mut Option<Stack>, n: usize) {
    let (_, count) = stack.as_mut().expect("cargo selected before taking");
    *count = count.checked_sub(n).expect("取走的件数不超过格内件数");
    if *count == 0 {
        *stack = None
    }
}
pub(crate) fn add(stack: &mut Option<Stack>, item: Item, n: usize) {
    match stack {
        None => *stack = Some((item, n)),
        Some((x, count)) => {
            assert_eq!(*x, item);
            *count += n
        }
    }
}
impl Machine {
    pub fn finish(&mut self, power: bool) {
        if let Batch::Running(r, t) = &self.batch
            && *t == 0
            && power
            && self.enabled
        {
            self.batch = Batch::Finished(r.output)
        }
        if let Batch::Finished((x, n)) = self.batch
            && self.output.is_none_or(|(y, m)| x == y && n + m <= 50)
        {
            add(&mut self.output, x, n);
            self.batch = Batch::Idle;
        }
    }
    pub fn start(&mut self, power: bool) {
        if !power || !self.enabled || !matches!(self.batch, Batch::Idle) {
            return;
        }
        let mut fits = RECIPES.iter().filter(|r| {
            r.kind == self.kind
                && r.inputs
                    .iter()
                    .all(|(x, n)| self.stock.iter().flatten().any(|(y, m)| x == y && m >= n))
        });
        if let Some(r) = fits.next() {
            assert!(
                fits.next().is_none(),
                "validated stock fits at most one recipe"
            );
            for (x, n) in r.inputs {
                let slot = self
                    .stock
                    .iter_mut()
                    .find(|s| s.is_some_and(|(y, _)| y == *x))
                    .expect("checked materials");
                take(slot, *n);
            }
            self.batch = Batch::Running(r, r.ticks * 8)
        }
    }
}
