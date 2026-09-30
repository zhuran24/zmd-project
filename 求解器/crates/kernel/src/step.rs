//! 规则 L18、L23—L37、L65：每步结束制造、逐个判定、开始制造。
use crate::{
    config::Axis,
    engine::{Engine, Route},
    graph::*,
    model::*,
    value::*,
};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet, VecDeque};
impl Engine {
    pub fn step(&mut self) -> Result<StepReport> {
        if let Some(stop) = &self.halted {
            return Err(stop.clone());
        }
        match self.step_inner() {
            Ok(report) => Ok(report),
            Err(stop) => {
                self.halted = Some(stop.clone());
                Err(stop)
            }
        }
    }
    fn step_inner(&mut self) -> Result<StepReport> {
        self.check_external_stops()?;
        let next = add(self.t, 1, "step.time")?;
        let before = json!(self.state);
        self.events.clear();
        self.ledger = crate::ledger::empty_ledger();
        if self.production_abstraction {
            self.represent_products()?;
        }
        self.ore_supply()?;
        self.check_ore_availability()?;
        let units: Vec<_> = self.progress.keys().cloned().collect();
        for u in &units {
            let i = self.progress[u];
            if self.input.geometry.units[u].kind == "协议储存箱" {
                if self.enabled(u, "transfer") {
                    let p = &mut self.state.progress[i];
                    let n = p.cooldown.as_ref().unwrap().integer(u)?;
                    p.cooldown = Some(Time::at(n.saturating_sub(1).max(0)));
                }
            } else if self.enabled(u, "manufacture") && self.state.progress[i].phase == "working" {
                let n = self.state.progress[i]
                    .remaining
                    .as_ref()
                    .unwrap()
                    .integer(u)?
                    - 1;
                if n == 0 {
                    let recipe = self.input.catalog.recipes
                        [self.state.progress[i].recipe.as_ref().unwrap()]
                    .clone();
                    let buffer = format!("{u}:buffer:0");
                    self.state.inventory[self.inv[&buffer]].contents.clear();
                    for (item, n) in recipe.outputs {
                        self.put(&buffer, &item, n)?;
                    }
                    let p = &mut self.state.progress[i];
                    p.phase = "completed".into();
                    p.remaining = None;
                    self.completed_batches = add(self.completed_batches, 1, "completed_batches")?;
                    self.event("complete", u, Some(json!({"recipe":recipe.id})));
                } else {
                    self.state.progress[i].remaining = Some(Time::at(n));
                }
            }
        }
        for u in &units {
            self.flush(u)?;
        }
        for i in 0..self.input.graph.components.len() {
            self.settle(i)?;
        }
        self.judged.fill(false);
        for subject in self.input.graph.order.clone() {
            self.current_subject = self.input.graph.label(&subject);
            match subject {
                Subject::Component(c) if !self.judged[c] => {
                    if self.input.graph.components[c].kind == ComponentKind::Splitter {
                        self.judged[c] = true;
                        let e = self.event("judge", &self.current_subject.clone(), None);
                        for ch in self.cyclic_order(&Subject::Component(c), "output") {
                            if self.send(&ch, e)? {
                                break;
                            }
                        }
                        self.prune_event(e);
                    } else {
                        self.fire(c)?;
                    }
                }
                Subject::Unit(u) => self.judge_nontransport(&u)?,
                _ => (),
            }
        }
        for u in &units {
            self.try_start(u)?;
        }
        for g in &mut self.state.logistics.gate_counters {
            if let Some(w) = &g.window_started_at {
                if add(
                    w.integer(&g.unit)?,
                    self.input.catalog.kinds["物品准入口"].window,
                    &g.unit,
                )? <= next
                {
                    g.window_started_at = None;
                    g.window_received = Quantity::calc(0);
                }
            }
        }
        self.t = next;
        self.state.environment.time = Time::at(next);
        self.ledger["totals"] = crate::ledger::totals(&self.ledger)?;
        crate::ledger::verify_tick(
            &before,
            &json!({"state":self.state,"warehouse_ledger":self.ledger}),
        )?;
        Ok(StepReport {
            step: next - 1,
            events: self.events.clone(),
            ledger: self.ledger.clone(),
        })
    }
    pub(crate) fn event(&mut self, phase: &str, subject: &str, detail: Option<Value>) -> usize {
        let i = self.events.len();
        self.events.push(Event {
            event: format!("E|{}|{i}", self.t),
            phase: phase.into(),
            subject: subject.into(),
            moves: vec![],
            detail,
        });
        i
    }
    fn prune_event(&mut self, i: usize) {
        if self.events[i].moves.is_empty()
            && self.events[i]
                .detail
                .as_ref()
                .is_none_or(|v| v.get("transfer").is_none())
        {
            assert_eq!(self.events.len(), i + 1);
            self.events.pop();
        }
    }
    pub(crate) fn flush(&mut self, u: &str) -> Result<()> {
        let i = self.progress[u];
        if self.state.progress[i].phase != "completed" {
            return Ok(());
        }
        let buffer = format!("{u}:buffer:0");
        let output = format!("{u}:output:0");
        let rows = &self.state.inventory[self.inv[&buffer]].contents;
        let out = &self.state.inventory[self.inv[&output]].contents;
        let conflict = self.unit_inventory[u]
            .iter()
            .map(|i| &self.state.inventory[*i])
            .filter(|s| s.slot.contains(":input:"))
            .any(|s| {
                s.contents
                    .iter()
                    .any(|c| rows.iter().any(|r| r.item == c.item))
            });
        let sum = rows
            .iter()
            .chain(out)
            .try_fold(0, |n, c| add(n, c.quantity.integer(&output)?, &output))?;
        if !rows.is_empty()
            && !conflict
            && rows.iter().chain(out).all(|c| c.item == rows[0].item)
            && self.caps[&output].is_some_and(|cap| sum <= cap)
        {
            for c in rows.clone() {
                self.put(&output, &c.item, c.quantity.integer(&buffer)?)?;
            }
            self.state.inventory[self.inv[&buffer]].contents.clear();
            let p = &mut self.state.progress[i];
            p.phase = "idle".into();
            p.recipe = None;
            p.remaining = None;
            self.event("flush", u, None);
        }
        Ok(())
    }
    fn try_start(&mut self, u: &str) -> Result<()> {
        let i = self.progress[u];
        if self.state.progress[i].phase != "idle" || !self.enabled(u, "manufacture") {
            return Ok(());
        }
        let mut available = BTreeMap::<String, (String, i64)>::new();
        for slot in self
            .slot_groups
            .get(&(u.into(), "input".into()))
            .into_iter()
            .flatten()
        {
            for c in &self.state.inventory[self.inv[slot]].contents {
                let entry = available.entry(c.item.clone()).or_insert((slot.clone(), 0));
                entry.1 = add(entry.1, c.quantity.integer(slot)?, slot)?;
            }
        }
        let matched = self
            .input
            .recipe_order
            .iter()
            .find(|id| {
                let r = &self.input.catalog.recipes[*id];
                r.kind == self.input.geometry.units[u].kind
                    && r.inputs
                        .iter()
                        .all(|(item, n)| available.get(item).is_some_and(|(_, q)| q >= n))
            })
            .cloned();
        if let Some(rid) = matched {
            let r = self.input.catalog.recipes[&rid].clone();
            let buffer = format!("{u}:buffer:0");
            for (item, n) in r.inputs {
                self.remove(&available[&item].0, &item, n)?;
                self.put(&buffer, &item, n)?;
            }
            let p = &mut self.state.progress[i];
            p.phase = "working".into();
            p.recipe = Some(rid.clone());
            p.remaining = Some(Time::at(r.duration));
            self.event("start", u, Some(json!({"recipe":rid})));
        }
        Ok(())
    }
    fn mature(&self, c: &Content) -> Result<bool> {
        let entered = c
            .entered_at
            .as_ref()
            .ok_or_else(|| Stop::invalid("transport", "缺入格时刻"))?
            .integer("entered_at")?;
        Ok(i128::from(self.t) - i128::from(entered)
            >= i128::from(self.input.catalog.residence_steps))
    }
    pub(crate) fn settle(&mut self, i: usize) -> Result<()> {
        let c = &self.input.graph.components[i];
        if !matches!(c.kind, ComponentKind::BeltChain | ComponentKind::BeltRing) {
            return Ok(());
        }
        let ring = c.kind == ComponentKind::BeltRing;
        let cells = c.cells.clone();
        // 环沿空格向后传播；每次移动都重记入格步，同一物品不可能在本步连跳。
        for _ in 0..if ring { cells.len() } else { 1 } {
            let mut moved = false;
            for j in (0..cells.len()).rev() {
                let next = (j + 1) % cells.len();
                if !ring && next == 0 {
                    continue;
                }
                if !self.state.inventory[self.inv[&cells[next]]]
                    .contents
                    .is_empty()
                {
                    continue;
                }
                let Some(item) = self.state.inventory[self.inv[&cells[j]]]
                    .contents
                    .first()
                    .cloned()
                else {
                    continue;
                };
                if self.mature(&item)? {
                    self.remove(&cells[j], &item.item, 1)?;
                    self.put(&cells[next], &item.item, 1)?;
                    moved = true;
                }
            }
            if !moved {
                break;
            }
        }
        Ok(())
    }
    fn route(&self, ch: &str) -> Result<Option<Route>> {
        let c = &self.input.geometry.channels[ch];
        let Some((source, content)) = self.source(&c.source_port)? else {
            return Ok(None);
        };
        let target_unit = &self.input.geometry.ports[&c.target_port].unit;
        if content.last_unit.as_ref() == Some(target_unit) {
            return Ok(None);
        }
        if matches!(self.input.graph.sender[ch], Sender::Component(_)) && !self.mature(&content)? {
            return Ok(None);
        }
        if let Some(i) = self.gate_index.get(target_unit) {
            let g = &self.state.logistics.gate_counters[*i];
            let s = &self.input.gate_settings[target_unit];
            if (!s["item"].is_null() && s["item"] != content.item)
                || (!s["total_limit"].is_null()
                    && g.total_received.integer(target_unit)?
                        >= num(&s["total_limit"], target_unit)?)
                || (!s["window_limit"].is_null()
                    && g.window_received.integer(target_unit)?
                        >= num(&s["window_limit"], target_unit)?)
            {
                return Ok(None);
            }
        }
        if self.production_abstraction
            && self.input.geometry.units[target_unit].kind == "协议核心"
            && crate::ledger::ORES.contains(&content.item.as_str())
        {
            return Err(Stop::unsupported(
                "cycle.domain.D2",
                ch,
                "生产抽象不允许矿石回仓",
            ));
        }
        let Some(target) = self.target(&c.target_port, &content.item)? else {
            return Ok(None);
        };
        if let Some(i) = self.inv.get(&target) {
            let rows = &self.state.inventory[*i].contents;
            let n = rows
                .iter()
                .try_fold(0, |n, c| add(n, c.quantity.integer(&target)?, &target))?;
            if rows.first().is_some_and(|c| c.item != content.item)
                || self.caps[&target].is_some_and(|cap| n >= cap)
            {
                return Ok(None);
            }
        }
        Ok(Some(Route {
            source,
            target,
            item: content.item,
        }))
    }
    fn send(&mut self, ch: &str, e: usize) -> Result<bool> {
        let Some(r) = self.route(ch)? else {
            return Ok(false);
        };
        let c = self.input.geometry.channels[ch].clone();
        let src = self.input.geometry.ports[&c.source_port].unit.clone();
        let dst = self.input.geometry.ports[&c.target_port].unit.clone();
        let event = self.events[e].event.clone();
        let warehouse_source = self.warehouse.contains_key(&r.source);
        let ore = crate::ledger::ORES.contains(&r.item.as_str());
        if warehouse_source
            && ore
            && !self.sufficient()
            && self.state.warehouse.slots[self.warehouse[&r.source]]
                .quantity
                .integer(&r.source)?
                <= 1
        {
            return Err(Stop::new(
                "invalid_input",
                "warehouse.external_supply",
                ch,
                "取走最后一件矿石将破坏持续可得",
            ));
        }
        let deposit = if self.input.geometry.units[&dst].kind == "协议核心" {
            self.plan_deposit(&BTreeMap::from([(r.item.clone(), 1)]), false)?
        } else {
            None
        };
        // 所有目标守卫先核完，再提交一件及关联台账。
        self.remove(&r.source, &r.item, 1)?;
        if let Some(plan) = deposit {
            self.commit_deposit(&plan, false)?;
            self.book(
                "core_inbound",
                json!({"event":event,"channel":ch,"unit":dst,"item":r.item,"quantity":q(1)}),
            );
        } else {
            self.put(&r.target, &r.item, 1)?;
            if self.input.geometry.units[&dst].kind == "桥接器" {
                self.state.inventory[self.inv[&r.target]].contents[0].last_unit = Some(src.clone());
            }
        }
        if warehouse_source {
            self.book("port_outbound",json!({"event":event,"channel":ch,"port":c.source_port,"item":r.item,"quantity":q(1)}));
            if ore && self.sufficient() {
                let plan = self
                    .plan_deposit(&BTreeMap::from([(r.item.clone(), 1)]), false)?
                    .ok_or_else(|| Stop::invalid(ch, "矿石原子回补失败"))?;
                self.commit_deposit(&plan, true)?;
                self.book(
                    "external_supply",
                    json!({"event":event,"mode":"sufficient","item":r.item,"quantity":q(1)}),
                );
            }
        }
        if let Some(i) = self.gate_index.get(&dst) {
            let g = &mut self.state.logistics.gate_counters[*i];
            g.total_received = Quantity::calc(add(g.total_received.integer(&dst)?, 1, &dst)?);
            g.window_received = Quantity::calc(add(g.window_received.integer(&dst)?, 1, &dst)?);
            if g.window_started_at.is_none() {
                g.window_started_at = Some(Time::at(self.t));
            }
        }
        self.success(ch)?;
        self.events[e].moves.push(Move {
            channel: ch.into(),
            item: r.item,
        });
        if let Sender::Component(i) = self.input.graph.sender[ch] {
            self.settle(i)?;
        }
        if let Receiver::Component(i) = self.input.graph.receiver[ch] {
            self.settle(i)?;
        }
        if self.progress.contains_key(&src) {
            self.flush(&src)?;
        }
        Ok(true)
    }
    fn fire(&mut self, c: usize) -> Result<()> {
        let mut members = BTreeSet::from([c]);
        let mut queue = VecDeque::from([c]);
        let mut receivers = Vec::new();
        let mut discovered = BTreeSet::new();
        while let Some(i) = queue.pop_front() {
            self.judged[i] = true;
            for ch in self.cyclic_order(&Subject::Component(i), "output") {
                let receiver = self.input.graph.receiver[&ch].clone();
                if !discovered.insert(receiver.clone()) {
                    continue;
                }
                receivers.push(receiver.clone());
                for channel in &self.input.graph.groups[&receiver] {
                    if let Sender::Component(j) = self.input.graph.sender[channel] {
                        if !self.judged[j] && members.insert(j) {
                            queue.push_back(j);
                        }
                    }
                }
            }
        }
        let names: Vec<_> = members
            .iter()
            .map(|i| self.input.graph.components[*i].id.clone())
            .collect();
        let subject = self.input.graph.components[c].id.clone();
        let e = self.event("judge", &subject, Some(json!({"members":names})));
        let mut sent = BTreeSet::new();
        for receiver in receivers {
            for ch in self.cyclic_order(&receiver, "input") {
                if let Sender::Component(i) = self.input.graph.sender[&ch] {
                    if members.contains(&i) && !sent.contains(&i) && self.send(&ch, e)? {
                        sent.insert(i);
                    }
                }
            }
        }
        self.prune_event(e);
        Ok(())
    }
    fn judge_nontransport(&mut self, u: &str) -> Result<()> {
        let e = self.event("judge", u, None);
        let is_box = self.input.geometry.units[u].kind == "协议储存箱";
        if is_box && self.input.transfer_timing[u] == "before_send" {
            self.transfer_event(u, e)?;
        }
        for ch in self.nontransport_order(u) {
            if self.send(&ch, e)? {
                break;
            }
        }
        if is_box && self.input.transfer_timing[u] == "after_send" {
            self.transfer_event(u, e)?;
        }
        self.prune_event(e);
        Ok(())
    }
    fn transfer_event(&mut self, u: &str, e: usize) -> Result<()> {
        let (outcome, detail) = self.transfer(u, &self.events[e].event.clone())?;
        if outcome != "guard_false" {
            self.events[e].detail = Some(
                json!({"transfer":serde_json::from_str::<Value>(&detail).map_err(|err|Stop::invalid(u,err.to_string()))?}),
            );
        }
        Ok(())
    }
    fn check_external_stops(&self) -> Result<()> {
        let supply = self.input.parameters.value(Axis::WarehouseExternalSupply)?;
        if supply["kind"] == "explicit_ore_history"
            && self.t > instant(&supply["through"], "warehouse.external_supply.through")?
        {
            return Err(Stop::unsupported(
                "warehouse.external_supply",
                "through",
                "超出显式补矿覆盖区间",
            ));
        }
        let seed = instant(
            &self.input.raw["initial_state"]["nonwarehouse"]["value"]["environment"]["time"],
            "seed.time",
        )?;
        for e in self.input.raw["timeline"]["events"].as_array().unwrap() {
            let kind = e["kind"].as_str().unwrap();
            let axis = match kind {
                "offline" => "offline.events",
                "withdraw_product" => "warehouse.withdrawal_timing",
                "debug_operation" => "initialization.debug_actions",
                "unit_removed" | "unit_rebuilt" => "initialization.rebuild_inventory",
                "build" => "initialization.build_timing",
                _ => continue,
            };
            let at = instant(&e["time"], "timeline.time")?;
            if at == self.t && !(kind == "build" && at <= seed) {
                return Err(Stop::unsupported(
                    axis,
                    e["id"].as_str().unwrap(),
                    "触及尚未实现的外部动作",
                ));
            }
        }
        if self.input.raw["environment"]["product_withdrawal"]["policy"]["value"]["rules"]
            .as_array()
            .is_some_and(|r| !r.is_empty())
        {
            return Err(Stop::unsupported(
                "warehouse.withdrawal_policy",
                "policy",
                "拿取策略求值未实现",
            ));
        }
        Ok(())
    }
    pub(crate) fn check_ore_availability(&self) -> Result<()> {
        for item in crate::ledger::ORES {
            if !self.state.warehouse.slots.iter().any(|r| {
                r.item.as_deref() == Some(item) && r.quantity.integer(&r.slot).is_ok_and(|n| n > 0)
            }) {
                return Err(Stop::new(
                    "invalid_input",
                    "warehouse.external_supply",
                    "warehouse",
                    format!("{item}无正库存"),
                ));
            }
        }
        Ok(())
    }
    fn ore_supply(&mut self) -> Result<()> {
        let supply = self
            .input
            .parameters
            .value(Axis::WarehouseExternalSupply)?
            .clone();
        for row in supply["events"].as_array().into_iter().flatten() {
            if instant(&row["time"], "ore_supply.time")? != self.t {
                continue;
            }
            let item = row["item"].as_str().unwrap();
            let n = num(&row["quantity"], "ore_supply.quantity")?;
            let plan = self
                .plan_deposit(&BTreeMap::from([(item.into(), n)]), false)?
                .ok_or_else(|| Stop::invalid("ore_supply", "补给超容量"))?;
            let e = self.event("supply", "warehouse", Some(row.clone()));
            self.commit_deposit(&plan, true)?;
            self.book("external_supply",json!({"event":self.events[e].event,"mode":"explicit_ore_history","item":item,"quantity":q(n)}));
        }
        Ok(())
    }
}
