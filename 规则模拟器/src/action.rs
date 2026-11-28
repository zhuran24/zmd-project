use crate::{
    Res,
    model::*,
    state::*,
    topology::{History, Tables},
};
use serde_json::Value as V;

#[derive(Clone, Debug)]
pub enum Action {
    SetGate(Id, Option<Item>, Option<usize>, Option<usize>),
    ResetCount(Id),
    Storage(Id, bool),
    Target(Id, usize, Option<Item>),
    Switch(Vec<Id>, bool),
    Put(Id, Item, usize),
    Collect(Cell),
    Store(Item, usize),
    Retrieve(Item, usize),
    Offline(Vec<Event>),
}
pub(crate) struct Simulation {
    pub events: Vec<Event>,
    pub state: State,
    pub tables: Tables,
    pub params: Parameters,
}
impl Simulation {
    pub fn new(
        events: Vec<Event>,
        params: Parameters,
        initial: &V,
        build: impl FnOnce(&History) -> Res<Tables>,
    ) -> Res<Self> {
        let history = History::read(&events)?;
        let tables = build(&history)?;
        params.check(&tables.layout)?;
        let state = State::load(initial, &tables)?;
        Ok(Self {
            events,
            state,
            tables,
            params,
        })
    }
    fn unit(&mut self, u: &Id) -> Res<&mut Unit> {
        self.state
            .units
            .get_mut(u)
            .ok_or_else(|| format!("不存在的单位 {u}"))
    }
    pub fn apply(&mut self, op: &Action, rebuild: impl FnOnce(&History) -> Res<Tables>) -> Res<()> {
        use Action::*;
        match op {
            SetGate(u, x, a, b) => {
                let new = Filter::new(*x, *a, *b)?;
                let CounterPolicy { count, quotas } = self.params.on_change;
                let g = self.unit(u)?.gate()?;
                let (old_x, _, old_b) = g.filter.fields();
                if old_x != *x {
                    g.count = 0;
                    if quotas == Counter::清空 {
                        g.quotas.clear()
                    }
                } else if old_b != *b && count == Counter::清空 {
                    g.count = 0
                }
                g.filter = new;
            }
            ResetCount(u) => {
                let g = self.unit(u)?.gate()?;
                if g.filter.fields().1.is_none() {
                    return Err("未设累计上限".into());
                }
                g.count = 0
            }
            Storage(u, b) => {
                let Body::Facility {
                    device: Facility::Box(s),
                    ..
                } = &mut self.unit(u)?.body
                else {
                    return Err("需要协议储存箱".into());
                };
                s.storage = *b;
            }
            Target(u, i, x) => {
                let ports: &mut [Option<Item>] = match &mut self.unit(u)?.body {
                    Body::Facility {
                        device: Facility::Core(ports),
                        ..
                    } => ports,
                    Body::Facility {
                        device: Facility::Pickup(port),
                        ..
                    } => std::slice::from_mut(port),
                    _ => return Err("单位没有取货端口指向".into()),
                };
                *ports.get_mut(*i).ok_or("取货口号越界")? = *x;
            }
            Switch(us, b) => {
                // Validate the entire operation before changing the first switch.
                for u in us {
                    self.unit(u)?.switch()?;
                }
                for u in us {
                    *self.unit(u)?.switch()? = *b
                }
            }
            Put(u, x, n) => {
                if *n == 0
                    || !matches!(
                        self.unit(u)?.body,
                        Body::Facility {
                            device: Facility::Box(_) | Facility::Machine(_),
                            ..
                        }
                    )
                {
                    return Err("放货目标或件数错误".into());
                }
                for _ in 0..*n {
                    let Some(dst) = self.state.destination(u, *x) else {
                        break;
                    };
                    self.state.deposit(u, dst, *x, None);
                }
            }
            Collect(Cell(u, s)) => {
                let slot = match (&mut self.unit(u)?.body, s) {
                    (
                        Body::Facility {
                            device: Facility::Box(b),
                            ..
                        },
                        Slot::Grid(i),
                    ) => b.slots.get_mut(*i),
                    (
                        Body::Facility {
                            device: Facility::Machine(m),
                            ..
                        },
                        Slot::Stock(i),
                    ) => m.stock.get_mut(*i),
                    (
                        Body::Facility {
                            device: Facility::Machine(m),
                            ..
                        },
                        Slot::Output,
                    ) => Some(&mut m.output),
                    _ => return Err("该格不允许收货".into()),
                }
                .ok_or("收货格号越界")?;
                slot.take().ok_or("收货格为空")?;
            }
            Store(x, n) => {
                let stored = &mut self.state.warehouse[*x as usize];
                let room = WAREHOUSE_CAP
                    .checked_sub(*stored)
                    .expect("仓库件数不超过上限");
                if *n > room {
                    return Err("入库超过容量".into());
                }
                *stored += n;
            }
            Retrieve(x, n) => {
                let stored = &mut self.state.warehouse[*x as usize];
                if *n > *stored {
                    return Err("出库库存不足".into());
                }
                *stored -= n;
            }
            Offline(events) => {
                let h = History::read(events)?;
                if !h.now().same_network(&self.tables.layout) {
                    return Err("离线前后单位、种类或通道集合不同".into());
                }
                self.tables = rebuild(&h)?;
                self.events.clone_from(events);
                let CounterPolicy { count, quotas } = self.params.on_offline;
                for unit in self.state.units.values_mut() {
                    if let Body::Transport {
                        device: Transport::Gate(g),
                        ..
                    } = &mut unit.body
                    {
                        if count == Counter::清空 {
                            g.count = 0
                        }
                        if quotas == Counter::清空 {
                            g.quotas.clear()
                        }
                    }
                }
            }
        }
        Ok(())
    }
}
