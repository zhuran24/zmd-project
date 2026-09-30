//! 规则 L27—L31：固定元件图、数层依赖与每步判定次序。
use crate::{
    catalog::{Catalog, Geometry, Port},
    config::Axis,
    input::{permutation, Input},
    value::*,
};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ComponentKind {
    BeltChain,
    BeltRing,
    Splitter,
    Merger,
    Gate,
    BridgeAxis,
}
#[derive(Clone, Debug)]
pub struct Component {
    pub id: String,
    pub kind: ComponentKind,
    pub unit: Option<String>,
    pub axis: Option<String>,
    pub cells: Vec<String>,
    pub inputs: Vec<String>,
    pub outputs: Vec<String>,
}
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum Receiver {
    Unit(String),
    Component(usize),
}
pub type Sender = Receiver;
pub type Subject = Receiver;
#[derive(Clone, Debug, Default)]
pub struct StepGraph {
    pub components: Vec<Component>,
    pub index: BTreeMap<String, usize>,
    pub slot_component: BTreeMap<String, usize>,
    pub rank: BTreeMap<String, usize>,
    pub receiver: BTreeMap<String, Receiver>,
    pub sender: BTreeMap<String, Sender>,
    pub groups: BTreeMap<Receiver, Vec<String>>,
    pub layers: Vec<i64>,
    pub order: Vec<Subject>,
    pub nontransport: Vec<String>,
    pub inputs_nt: BTreeMap<String, Vec<String>>,
    pub outputs_nt: BTreeMap<String, Vec<String>>,
}
fn invalid(at: &str, reason: &str) -> Stop {
    Stop::new("invalid_input", "step.order", at, reason)
}
fn unresolved(at: &str, reason: &str) -> Stop {
    Stop::new("unresolved", "step.order", at, reason)
}
impl StepGraph {
    pub fn build(input: &Input) -> Result<Self> {
        let mut graph = Self::structure(
            &input.geometry,
            &input.catalog,
            &input.connection_times,
            &input.tie_order,
        )?;
        graph.resolve(input.parameters.value(Axis::StepOrder)?)?;
        Ok(graph)
    }
    pub fn structure(
        g: &Geometry,
        cat: &Catalog,
        times: &BTreeMap<String, i64>,
        tie: &[String],
    ) -> Result<Self> {
        permutation(tie, g.channels.keys().cloned(), "connection.tie")?;
        let mut graph = Self::default();
        let mut channels = tie.to_vec();
        channels.sort_by_key(|c| times[c]); // stable: equal times retain explicit tie order
        graph.rank = channels
            .iter()
            .enumerate()
            .map(|(i, c)| (c.clone(), i))
            .collect();
        let belts: BTreeSet<_> = g
            .units
            .iter()
            .filter(|(_, u)| u.kind == "传送带")
            .map(|(u, _)| u.clone())
            .collect();
        let mut next = BTreeMap::new();
        let mut prev = BTreeMap::new();
        for c in g.channels.values() {
            let a = &g.ports[&c.source_port].unit;
            let b = &g.ports[&c.target_port].unit;
            if belts.contains(a)
                && belts.contains(b)
                && (next.insert(a.clone(), b.clone()).is_some()
                    || prev.insert(b.clone(), a.clone()).is_some())
            {
                return Err(invalid(&c.id, "带链分叉"));
            }
        }
        let mut seen = BTreeSet::new();
        let starts: Vec<_> = belts
            .iter()
            .filter(|b| !prev.contains_key(*b))
            .chain(belts.iter())
            .cloned()
            .collect();
        for start in starts {
            if seen.contains(&start) {
                continue;
            }
            let mut cells = Vec::new();
            let mut current = start.clone();
            let ring = loop {
                if !seen.insert(current.clone()) {
                    break current == start;
                }
                cells.push(format!("{current}:transport:0"));
                match next.get(&current) {
                    Some(n) => current = n.clone(),
                    None => break false,
                }
            };
            let head = cells.last().unwrap().split(':').next().unwrap();
            graph.components.push(Component {
                id: if ring {
                    format!("C|ring|{start}")
                } else {
                    format!("C|{head}")
                },
                kind: if ring {
                    ComponentKind::BeltRing
                } else {
                    ComponentKind::BeltChain
                },
                unit: None,
                axis: None,
                cells,
                inputs: vec![],
                outputs: vec![],
            });
        }
        for (id, u) in &g.units {
            if cat.kinds[&u.kind].family != "transport" {
                if cat.kinds[&u.kind].family != "power" {
                    graph.nontransport.push(id.clone());
                    graph.inputs_nt.insert(id.clone(), vec![]);
                    graph.outputs_nt.insert(id.clone(), vec![]);
                }
                continue;
            }
            if u.kind == "传送带" {
                continue;
            }
            let axes: Vec<Option<&str>> = if u.kind == "桥接器" {
                vec![Some("horizontal"), Some("vertical")]
            } else {
                vec![None]
            };
            for axis in axes {
                graph.components.push(Component {
                    id: axis.map_or_else(|| format!("C|{id}"), |a| format!("C|{id}|{a}")),
                    kind: match u.kind.as_str() {
                        "分流器" => ComponentKind::Splitter,
                        "汇流器" => ComponentKind::Merger,
                        "物品准入口" => ComponentKind::Gate,
                        _ => ComponentKind::BridgeAxis,
                    },
                    unit: Some(id.clone()),
                    axis: axis.map(str::to_string),
                    cells: vec![format!("{id}:{}:0", axis.unwrap_or("transport"))],
                    inputs: vec![],
                    outputs: vec![],
                });
            }
        }
        graph.components.sort_by(|a, b| a.id.cmp(&b.id));
        for pair in graph.components.windows(2) {
            if pair[0].id == pair[1].id {
                return Err(invalid(&pair[0].id, "元件身份重复"));
            }
        }
        for (i, c) in graph.components.iter().enumerate() {
            graph.index.insert(c.id.clone(), i);
            for s in &c.cells {
                graph.slot_component.insert(s.clone(), i);
            }
        }
        let owner = |p: &Port| {
            let slot = format!("{}:{}:0", p.unit, p.axis.as_deref().unwrap_or("transport"));
            graph.slot_component.get(&slot).map_or_else(
                || Receiver::Unit(p.unit.clone()),
                |i| Receiver::Component(*i),
            )
        };
        let edges: Vec<_> = channels
            .iter()
            .map(|c| {
                let ch = &g.channels[c];
                (
                    c.clone(),
                    owner(&g.ports[&ch.source_port]),
                    owner(&g.ports[&ch.target_port]),
                )
            })
            .collect();
        for (ch, a, b) in edges {
            if a == b
                && matches!(a,Receiver::Component(i) if matches!(graph.components[i].kind,ComponentKind::BeltChain|ComponentKind::BeltRing))
            {
                continue;
            }
            if let Receiver::Component(i) = a {
                let c = &mut graph.components[i];
                if c.kind == ComponentKind::BeltChain
                    && c.cells.last().unwrap()
                        != &format!("{}:transport:0", g.ports[&g.channels[&ch].source_port].unit)
                {
                    return Err(invalid(&ch, "外送不从头带出"));
                }
                c.outputs.push(ch.clone());
                if c.kind != ComponentKind::Splitter {
                    graph.groups.entry(b.clone()).or_default().push(ch.clone());
                }
            } else if let Receiver::Unit(u) = &a {
                graph.outputs_nt.get_mut(u).unwrap().push(ch.clone());
            }
            if let Receiver::Component(i) = b {
                let c = &mut graph.components[i];
                if c.kind == ComponentKind::BeltChain
                    && c.cells.first().unwrap()
                        != &format!("{}:transport:0", g.ports[&g.channels[&ch].target_port].unit)
                {
                    return Err(invalid(&ch, "外收不从入口带入"));
                }
                c.inputs.push(ch.clone());
            } else if let Receiver::Unit(u) = &b {
                graph.inputs_nt.get_mut(u).unwrap().push(ch.clone());
            }
            graph.sender.insert(ch.clone(), a);
            graph.receiver.insert(ch, b);
        }
        Ok(graph)
    }
    pub fn candidates(&self) -> Vec<Vec<usize>> {
        self.components
            .iter()
            .map(|c| {
                c.outputs
                    .iter()
                    .filter_map(|ch| match self.receiver[ch] {
                        Receiver::Component(d) if !self.components[d].outputs.is_empty() => Some(d),
                        _ => None,
                    })
                    .collect::<BTreeSet<_>>()
                    .into_iter()
                    .collect()
            })
            .collect()
    }
    fn cycles(edges: &[Option<usize>]) -> Vec<Vec<usize>> {
        let mut done = BTreeSet::new();
        let mut result = vec![];
        for start in 0..edges.len() {
            let mut path = Vec::new();
            let mut positions = BTreeMap::new();
            let mut node = Some(start);
            while let Some(i) = node {
                if done.contains(&i) {
                    break;
                }
                if let Some(&p) = positions.get(&i) {
                    result.push(path[p..].to_vec());
                    break;
                }
                positions.insert(i, path.len());
                path.push(i);
                node = edges[i];
            }
            done.extend(path);
        }
        result
    }
    /// 布局工具的代表值；不是全称域约减或引擎隐式缺省。
    pub fn default_order(&self) -> Value {
        let candidates = self.candidates();
        let n = candidates.len();
        let mut distance = vec![usize::MAX; n];
        for (i, ds) in candidates.iter().enumerate() {
            if ds.is_empty() {
                distance[i] = 1;
            }
        }
        for _ in 0..n {
            for (i, ds) in candidates.iter().enumerate() {
                for &d in ds {
                    if distance[d] != usize::MAX {
                        distance[i] = distance[i].min(distance[d] + 1);
                    }
                }
            }
        }
        let edges: Vec<_> = candidates
            .iter()
            .map(|ds| {
                ds.iter()
                    .copied()
                    .min_by_key(|d| (distance[*d], &self.components[*d].id))
            })
            .collect();
        let choices:Vec<_>=edges.iter().enumerate().filter(|(i,_)|candidates[*i].len()>1).map(|(i,d)|json!({"component":self.components[i].id,"downstream":self.components[d.unwrap()].id})).collect();
        let cycles: Vec<_> = Self::cycles(&edges)
            .iter()
            .map(|cycle| {
                let i = *cycle.iter().min().unwrap();
                json!({"component":self.components[i].id,"layer":q(1)})
            })
            .collect();
        let mut nt = self.nontransport.clone();
        nt.sort_by_key(|u| {
            (
                self.outputs_nt[u]
                    .first()
                    .map(|c| self.rank[c])
                    .unwrap_or(usize::MAX),
                u.clone(),
            )
        });
        json!({"schema":"step-order-v1","layer_choices":choices,"cycle_layers":cycles,"nontransport_order":nt})
    }
    pub fn resolve(&mut self, order: &Value) -> Result<()> {
        fields(
            order,
            "schema layer_choices cycle_layers nontransport_order",
            "step.order",
        )
        .map_err(|e| invalid(&e.location, &e.reason))?;
        if order["schema"] != "step-order-v1" {
            return Err(invalid("step.order", "未知版本"));
        }
        let candidates = self.candidates();
        let mut choices = BTreeMap::new();
        for r in order["layer_choices"]
            .as_array()
            .ok_or_else(|| invalid("layer_choices", "须为数组"))?
        {
            fields(r, "component downstream", "layer_choices[]")
                .map_err(|e| invalid(&e.location, &e.reason))?;
            let c = r["component"]
                .as_str()
                .and_then(|s| self.index.get(s))
                .copied()
                .ok_or_else(|| invalid("layer_choices", "未知元件"))?;
            let d = r["downstream"]
                .as_str()
                .and_then(|s| self.index.get(s))
                .copied()
                .ok_or_else(|| invalid("layer_choices", "未知下游"))?;
            if candidates[c].len() < 2
                || !candidates[c].contains(&d)
                || choices.insert(c, d).is_some()
            {
                return Err(invalid("layer_choices", "多余、重复或非候选选支"));
            }
        }
        let mut edges = Vec::new();
        for (i, ds) in candidates.iter().enumerate() {
            edges.push(match ds.len() {
                0 => None,
                1 => Some(ds[0]),
                _ => Some(
                    *choices
                        .get(&i)
                        .ok_or_else(|| unresolved(&self.components[i].id, "缺选支"))?,
                ),
            });
        }
        let cycles = Self::cycles(&edges);
        let on_cycle: BTreeSet<_> = cycles.iter().flatten().copied().collect();
        let mut anchors = BTreeMap::new();
        for r in order["cycle_layers"]
            .as_array()
            .ok_or_else(|| invalid("cycle_layers", "须为数组"))?
        {
            fields(r, "component layer", "cycle_layers[]")
                .map_err(|e| invalid(&e.location, &e.reason))?;
            let c = r["component"]
                .as_str()
                .and_then(|s| self.index.get(s))
                .copied()
                .ok_or_else(|| invalid("cycle_layers", "未知元件"))?;
            let layer = num(&r["layer"], "cycle_layers.layer")?;
            if layer < 1 || !on_cycle.contains(&c) || anchors.insert(c, layer).is_some() {
                return Err(invalid("cycle_layers", "非环上、重复或非正层数"));
            }
        }
        for cycle in cycles {
            if !cycle.iter().any(|i| anchors.contains_key(i)) {
                return Err(unresolved(&self.components[cycle[0]].id, "环缺显式层数"));
            }
        }
        self.layers = vec![0; edges.len()];
        for (i, n) in anchors {
            self.layers[i] = n;
        }
        for start in 0..edges.len() {
            let mut path = vec![];
            let mut current = start;
            while self.layers[current] == 0 {
                path.push(current);
                if let Some(d) = edges[current] {
                    current = d;
                } else {
                    self.layers[current] = 1;
                    break;
                }
            }
            for i in path.into_iter().rev() {
                if self.layers[i] == 0 {
                    self.layers[i] = add(self.layers[edges[i].unwrap()], 1, "step.order.layer")?;
                }
            }
        }
        let mut components: Vec<_> = (0..self.components.len()).collect();
        components.sort_by_key(|i| {
            (
                self.layers[*i],
                self.components[*i]
                    .outputs
                    .first()
                    .map(|c| self.rank[c])
                    .unwrap_or(usize::MAX),
                self.components[*i].id.clone(),
            )
        });
        let nt: Vec<String> = decode(order["nontransport_order"].clone(), "nontransport_order")?;
        permutation(&nt, self.nontransport.clone(), "nontransport_order")
            .map_err(|e| invalid(&e.location, &e.reason))?;
        let ranks: Vec<_> = nt
            .iter()
            .filter_map(|u| self.outputs_nt[u].first().map(|c| self.rank[c]))
            .collect();
        if ranks.windows(2).any(|w| w[0] >= w[1]) {
            return Err(invalid("nontransport_order", "违反最早送货通道次序"));
        }
        self.order = components
            .into_iter()
            .map(Subject::Component)
            .chain(nt.into_iter().map(Subject::Unit))
            .collect();
        Ok(())
    }
    pub fn label(&self, s: &Subject) -> String {
        match s {
            Subject::Unit(u) => u.clone(),
            Subject::Component(i) => self.components[*i].id.clone(),
        }
    }
    pub fn inputs(&self, s: &Receiver) -> &[String] {
        match s {
            Receiver::Unit(u) => &self.inputs_nt[u],
            Receiver::Component(i) => &self.components[*i].inputs,
        }
    }
    pub fn outputs(&self, s: &Sender) -> &[String] {
        match s {
            Sender::Unit(u) => &self.outputs_nt[u],
            Sender::Component(i) => &self.components[*i].outputs,
        }
    }
    pub fn cursor_sides(&self) -> BTreeMap<String, Vec<String>> {
        let mut result = BTreeMap::new();
        for c in &self.components {
            for (side, channels) in [("input", &c.inputs), ("output", &c.outputs)] {
                if channels.len() > 1 {
                    result.insert(format!("{}:{side}", c.id), channels.clone());
                }
            }
        }
        for (u, channels) in &self.inputs_nt {
            if channels.len() > 1 {
                result.insert(format!("{u}:input"), channels.clone());
            }
        }
        result
    }
}
