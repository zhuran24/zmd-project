//! Decode and validate finite tables, then discard the wire representation.
use crate::{
    Res,
    json::{array, decode, keys},
    model::*,
    state::*,
    topology::Tables,
};
use serde::{Serialize, de::DeserializeOwned};
use serde_json::{Map, Value as V, json};
use std::collections::{BTreeMap, BTreeSet};

const FIELDS: [&str; 12] = [
    "货",
    "已停",
    "来处",
    "分流器上次",
    "进货上次",
    "出货已移动",
    "制造中",
    "准入口",
    "储存箱",
    "开关",
    "取货指向",
    "仓库",
];
type Rows<K> = BTreeMap<K, V>;

fn rows<K: Ord>(s: &V, field: &str, read: impl Fn(&V) -> Res<K>) -> Res<Rows<K>> {
    let mut rows = BTreeMap::new();
    if let Some(entries) = s.get(field) {
        for entry in array(entries)? {
            let [k, v] = array(entry)? else {
                return Err(format!("{field} 需要键值对"));
            };
            let k = read(k)?;
            if rows.last_key_value().is_some_and(|(last, _)| last >= &k) {
                return Err(format!("{field} 表键乱序或重复"));
            }
            rows.insert(k, v.clone());
        }
    }
    Ok(rows)
}

// Defaults apply exclusively to absent rows/fields. A present malformed value
// always propagates its decoding error, including a null in a non-nullable field.
fn row<K: Ord, T: DeserializeOwned + Serialize>(rows: &mut Rows<K>, key: &K, absent: T) -> Res<T> {
    match rows.remove(key) {
        Some(v) => decode(&v),
        None => Ok(absent),
    }
}
fn part<T: DeserializeOwned + Serialize>(v: &V, k: &str, absent: T) -> Res<T> {
    match v.get(k) {
        Some(v) => decode(v),
        None => Ok(absent),
    }
}
fn gate(v: Option<V>) -> Res<Gate> {
    let v = match v {
        Some(v) => v,
        None => json!({}),
    };
    keys(
        &v,
        &["放行", "累计上限", "每5tick上限", "累计已收", "名额", "拍"],
    )?;
    let filter = Filter::new(
        part(&v, "放行", None)?,
        part(&v, "累计上限", None)?,
        part(&v, "每5tick上限", None)?,
    )?;
    let phase = part(&v, "拍", 0)?;
    if phase >= 4 {
        return Err("准入口拍超过 3".into());
    }
    Ok(Gate {
        filter,
        phase,
        count: part(&v, "累计已收", 0)?,
        quotas: part(&v, "名额", vec![])?,
    })
}
struct Cells {
    cargo: Rows<Cell>,
    stopped: Rows<Cell>,
    from: Rows<Cell>,
}
impl Cells {
    fn read(
        &mut self,
        u: &Id,
        slot: Slot,
        transport: bool,
    ) -> Res<(Vec<Stack>, usize, Option<Cell>)> {
        let key = Cell(*u, slot);
        let stacks: Vec<Stack> = row(&mut self.cargo, &key, vec![])?;
        let t = row(&mut self.stopped, &key, 0usize)?;
        let from = match self.from.remove(&key) {
            None | Some(V::Null) => None,
            Some(v) => Some(Cell::read(&v)?),
        };
        if t > 8 || ((!transport || stacks.is_empty()) && (t != 0 || from.is_some())) {
            return Err(format!("已停或来处不合规矩 {}", key.json()));
        }
        Ok((stacks, t, from))
    }
    fn transport(&mut self, u: &Id, device: Transport) -> Res<Body> {
        let (stacks, stopped, from) = self.read(u, Slot::Grid(0), true)?;
        let load = match stacks.as_slice() {
            [] => None,
            [(item, 1)] => Some(Load {
                item: *item,
                stopped,
                from,
            }),
            _ => return Err("运输格容量为一件".into()),
        };
        Ok(Body::Transport { load, device })
    }
    fn stock(&mut self, u: &Id, slot: Slot) -> Res<Option<Stack>> {
        let (stacks, _, _) = self.read(u, slot, false)?;
        match stacks.as_slice() {
            [] => Ok(None),
            [p] if (1..=50).contains(&p.1) => Ok(Some(*p)),
            _ => Err("货格只能有一堆 1–50 件的货".into()),
        }
    }
}
fn batch(kind: Kind, cargo: Vec<Stack>, job: Option<V>) -> Res<Batch> {
    match job {
        None | Some(V::Null) => match cargo.as_slice() {
            [] => Ok(Batch::Idle),
            [p] if RECIPES.iter().any(|r| r.kind == kind && r.output == *p) => {
                Ok(Batch::Finished(*p))
            }
            _ => Err("闲置制造单位的缓存不是一批产物".into()),
        },
        Some(v) => {
            let [r, t] = array(&v)? else {
                return Err("制造中需要配方与步数".into());
            };
            let recipe = RECIPES
                .iter()
                .find(|p| p.kind == kind && json!(p) == *r)
                .ok_or("制造中配方错误")?;
            if recipe.inputs != cargo {
                return Err("缓存与配方用料不符".into());
            }
            Ok(Batch::Running(recipe, decode(t)?))
        }
    }
}
impl State {
    pub fn load(v: &V, t: &Tables) -> Res<Self> {
        keys(v, &FIELDS)?;
        let mut cells = Cells {
            cargo: rows(v, "货", Cell::read)?,
            stopped: rows(v, "已停", Cell::read)?,
            from: rows(v, "来处", Cell::read)?,
        };
        let mut split = rows(v, "分流器上次", decode)?;
        let mut input = rows(v, "进货上次", decode)?;
        let mut moved = rows(v, "出货已移动", decode)?;
        let mut jobs = rows(v, "制造中", decode::<Id>)?;
        let mut gates = rows(v, "准入口", decode::<Id>)?;
        let mut boxes = rows(v, "储存箱", decode::<Id>)?;
        let mut enabled = rows(v, "开关", decode)?;
        let mut ports = rows(v, "取货指向", decode)?;
        let mut inventory = rows(v, "仓库", decode)?;
        let mut units = BTreeMap::new();
        for (u, kind) in &t.layout.built {
            let kind = *kind;
            let last_index = row(&mut input, u, 0usize)?;
            if last_index >= t.inputs[u].len().max(1) {
                return Err("进货上次下标越界".into());
            }
            let mut facility = |device| {
                Ok::<_, String>(Body::Facility {
                    device,
                    moved: row(&mut moved, u, vec![])?,
                })
            };
            use Kind::*;
            let body = match kind {
                传送带 | 汇流器 | 桥接器格 => cells.transport(u, Transport::Plain)?,
                分流器 => cells.transport(u, Transport::Split(row(&mut split, u, None)?))?,
                物品准入口 => cells.transport(u, Transport::Gate(gate(gates.remove(u))?))?,
                协议储存箱 => {
                    let v = match boxes.remove(u) {
                        Some(v) => v,
                        None => json!({}),
                    };
                    keys(&v, &["仓储模式", "冷却还剩"])?;
                    let mut slots = [None; 6];
                    for (i, s) in slots.iter_mut().enumerate() {
                        *s = cells.stock(u, Slot::Grid(i))?
                    }
                    facility(Facility::Box(BoxState {
                        slots,
                        enabled: row(&mut enabled, u, true)?,
                        storage: part(&v, "仓储模式", false)?,
                        cooldown: part(&v, "冷却还剩", 0)?,
                    }))?
                }
                协议核心 => {
                    let mut targets = [None; CORE_OUTLETS];
                    for (i, target) in targets.iter_mut().enumerate() {
                        *target = row(&mut ports, &(*u, i), None)?;
                    }
                    facility(Facility::Core(targets))?
                }
                仓库取货口 => {
                    facility(Facility::Pickup(row(&mut ports, &(*u, 0usize), None)?))?
                }
                粉碎机 | 精炼炉 | 研磨机 | 塑形机 | 配件机 | 种植机 | 采种机 | 封装机 | 灌装机 =>
                {
                    let mut stock = vec![];
                    let mut seen = BTreeSet::new();
                    for i in 0..kind.stock_slots() {
                        let p = cells.stock(u, Slot::Stock(i))?;
                        if p.is_some_and(|(item, _)| !seen.insert(item)) {
                            return Err("存货格有重复物品".into());
                        }
                        stock.push(p)
                    }
                    let output = cells.stock(u, Slot::Output)?;
                    let (cache, _, _) = cells.read(u, Slot::Cache, false)?;
                    facility(Facility::Machine(Machine {
                        kind,
                        enabled: row(&mut enabled, u, true)?,
                        stock,
                        output,
                        batch: batch(kind, cache, jobs.remove(u))?,
                    }))?
                }
            };
            units.insert(*u, Unit { last_index, body });
        }
        let mut warehouse = [0; ITEMS.len()];
        for x in ITEMS {
            let n = row(&mut inventory, &x, 0usize)?;
            if n > WAREHOUSE_CAP {
                return Err("仓库超容量".into());
            }
            warehouse[x as usize] = n
        }
        let remaining = [
            cells.cargo.len(),
            cells.stopped.len(),
            cells.from.len(),
            split.len(),
            input.len(),
            moved.len(),
            jobs.len(),
            gates.len(),
            boxes.len(),
            enabled.len(),
            ports.len(),
            inventory.len(),
        ];
        for (name, count) in FIELDS.iter().zip(remaining) {
            if count > 0 {
                return Err(format!("{name} 含域外键"));
            }
        }
        Ok(State { units, warehouse })
    }

    pub fn snapshot(&self) -> V {
        let mut out = BTreeMap::<&str, Vec<V>>::new();
        let mut put =
            |field, key: V, value: V| out.entry(field).or_default().push(json!([key, value]));
        for (u, unit) in &self.units {
            let cell = |s| Cell(*u, s).json();
            if unit.last_index != 0 {
                put("进货上次", json!(u), json!(unit.last_index))
            }
            match &unit.body {
                Body::Transport { load, device } => {
                    if let Some(p) = load {
                        let g = cell(Slot::Grid(0));
                        put("货", g.clone(), json!([[p.item, 1]]));
                        if p.stopped != 0 {
                            put("已停", g.clone(), json!(p.stopped))
                        }
                        if let Some(from) = &p.from {
                            put("来处", g, from.json())
                        }
                    }
                    match device {
                        Transport::Split(Some(c)) => put("分流器上次", json!(u), json!(c)),
                        Transport::Split(None) | Transport::Plain => {}
                        Transport::Gate(g) => {
                            let (item, a, b) = g.filter.fields();
                            if item.is_some()
                                || g.count != 0
                                || !g.quotas.is_empty()
                                || g.phase != 0
                            {
                                put(
                                    "准入口",
                                    json!(u),
                                    json!({"放行":item,"累计上限":a,"每5tick上限":b,"累计已收":g.count,"名额":g.quotas,"拍":g.phase}),
                                )
                            }
                        }
                    }
                }
                Body::Facility { device, moved } => {
                    if !moved.is_empty() {
                        put("出货已移动", json!(u), json!(moved))
                    }
                    match device {
                        Facility::Box(b) => {
                            if !b.enabled {
                                put("开关", json!(u), json!(false))
                            }
                            if b.storage || b.cooldown != 0 {
                                put(
                                    "储存箱",
                                    json!(u),
                                    json!({"仓储模式":b.storage,"冷却还剩":b.cooldown}),
                                )
                            }
                            for (i, p) in b.slots.iter().enumerate() {
                                if let Some(p) = p {
                                    put("货", cell(Slot::Grid(i)), json!([p]))
                                }
                            }
                        }
                        Facility::Machine(m) => {
                            if !m.enabled {
                                put("开关", json!(u), json!(false))
                            }
                            for (i, p) in m.stock.iter().enumerate() {
                                if let Some(p) = p {
                                    put("货", cell(Slot::Stock(i)), json!([p]))
                                }
                            }
                            if let Some(p) = m.output {
                                put("货", cell(Slot::Output), json!([p]))
                            }
                            match &m.batch {
                                Batch::Idle => {}
                                Batch::Running(r, t) => {
                                    put("制造中", json!(u), json!([r, t]));
                                    put("货", cell(Slot::Cache), json!(r.inputs))
                                }
                                Batch::Finished(p) => put("货", cell(Slot::Cache), json!([p])),
                            }
                        }
                        Facility::Pickup(port) => {
                            if let Some(x) = port {
                                put("取货指向", json!([u, 0]), json!(x))
                            }
                        }
                        Facility::Core(ports) => {
                            for (i, x) in ports.iter().enumerate() {
                                if let Some(x) = x {
                                    put("取货指向", json!([u, i]), json!(x))
                                }
                            }
                        }
                    }
                }
            }
        }
        for x in ITEMS {
            let n = self.warehouse[x as usize];
            if n != 0 {
                put("仓库", json!(x), json!(n))
            }
        }
        let mut snapshot = V::Object(
            out.into_iter()
                .map(|(k, v)| (k.to_owned(), V::Array(v)))
                .collect::<Map<_, _>>(),
        );
        snapshot.sort_all_objects();
        snapshot
    }
}
