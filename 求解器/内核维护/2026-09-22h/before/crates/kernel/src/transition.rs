//! 受限转移§2、§4.2、§5：边界、原子模板与精确闭包键。
use crate::{engine::Engine, model::*, value::*};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
impl Engine {
    /// 受限转移§4.2：制造固定子动作链，整批输出后方能归集下一批。
    fn manufacture(&mut self, uid: &str, event: &str) -> Result<String> {
        let i = self.progress[uid];
        let output = format!("{uid}:output:0");
        let buffer = format!("{uid}:buffer:0");
        let mut success = false;
        if self.state.progress[i].phase == "completed" {
            let rows = &self.state.inventory[self.inv[&buffer]].contents;
            let out = &self.state.inventory[self.inv[&output]].contents;
            let input_conflict = self.unit_inventory[uid]
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
                && !input_conflict
                && rows.iter().chain(out).all(|c| c.item == rows[0].item)
                && self.caps[&output].is_some_and(|cap| sum <= cap)
            {
                let batch = rows.clone();
                for c in batch {
                    self.put(&output, &c.item, c.quantity.integer(&buffer)?)?
                }
                self.state.inventory[self.inv[&buffer]].contents.clear();
                let p = &mut self.state.progress[i];
                p.phase = "idle".into();
                p.recipe = None;
                p.locked_recipe = None;
                p.candidate_recipes.clear();
                p.remaining = None;
                success = true;
                {
                    self.passages.push(json!({"event":event,"batch":format!("{uid}|{}|output",self.t),"channel":format!("BC|{buffer}|{output}")}));
                }
            }
        }
        if self.state.progress[i].phase == "idle" {
            let mut available = BTreeMap::new();
            for slot in self
                .slot_groups
                .get(&(uid.into(), "input".into()))
                .into_iter()
                .flatten()
            {
                {
                    for c in &self.state.inventory[self.inv[slot]].contents {
                        let entry = available.entry(c.item.clone()).or_insert((slot.clone(), 0));
                        entry.1 = add(entry.1, c.quantity.integer(slot)?, slot)?;
                    }
                }
            }
            let matched = self
                .input
                .recipe_order
                .iter()
                .find(|id| {
                    let r = &self.input.catalog.recipes[*id];
                    r.kind == self.input.geometry.units[uid].kind
                        && r.inputs
                            .iter()
                            .all(|(item, n)| available.get(item).is_some_and(|(_, q)| q >= n))
                })
                .cloned();
            if let Some(rid) = matched {
                let r = self.input.catalog.recipes[&rid].clone();
                if self.enabled(uid, "manufacture") {
                    self.precheck_new_event(&format!("C|{}|{uid}", add(self.t, r.duration, uid)?))?;
                }
                for (item, n) in &r.inputs {
                    let src = &available[item].0;
                    self.remove(src, item, *n)?;
                    self.put(&buffer, item, *n)?;
                    {
                        self.passages.push(json!({"event":event,"batch":format!("{uid}|{}|input",self.t),"channel":format!("BC|{src}|{buffer}")}));
                    }
                }
                let p = &mut self.state.progress[i];
                p.phase = "intake".into();
                p.recipe = Some(rid.clone());
                p.locked_recipe = Some(rid.clone());
                p.candidate_recipes = vec![rid];
                p.remaining = None;
                success = true;
            }
        }
        if self.state.progress[i].phase == "intake" && self.enabled(uid, "manufacture") {
            let duration = self.input.catalog.recipes
                [self.state.progress[i].recipe.as_ref().unwrap()]
            .duration;
            let deadline = add(self.t, duration, uid)?;
            let eid = format!("C|{deadline}|{uid}");
            self.allocate(&eid)?;
            let p = &mut self.state.progress[i];
            p.phase = "working".into();
            p.remaining = Some(Time::at(duration));
            self.pending.push(Pending {
                event: eid,
                operation: "manufacture_complete".into(),
                target: uid.into(),
                trigger: json!({"kind":"at_time","value":tv(deadline)}),
                predecessors: vec![],
                status: "waiting".into(),
            });
            success = true;
        }
        Ok(if success { "success" } else { "guard_false" }.into())
    }
    /// 内核输入§3.1、受限转移§4：事务开始前拒绝新事件别名。
    fn precheck_new_event(&self, id: &str) -> Result<()> {
        if self.allocated.contains(id) {
            Err(Stop::invalid(id, "新日程与注册事件冲突"))
        } else {
            Ok(())
        }
    }
    /// 受限转移§3.3：PC 一次访问，授权前快照决定成功及两侧失败后效。
    fn move_channel(&mut self, cid: &str, event: &str) -> Result<(String, String, Vec<String>)> {
        self.refresh()?;
        let c = self.input.geometry.channels[cid].clone();
        let source_unit = self.input.geometry.ports[&c.source_port].unit.clone();
        let target_unit = self.input.geometry.ports[&c.target_port].unit.clone();
        let a = self.side_index[&(source_unit, "output".into())];
        let b = self.side_index[&(target_unit.clone(), "input".into())];
        let (ga, gb) = if self.active.contains(cid) {
            (self.grant(a, cid)?, self.grant(b, cid)?)
        } else {
            (false, false)
        };
        let (route, reason) = self.physical(cid)?;
        let mut outcome = "failure";
        let mut detail = if route.is_some() {
            "dual_permission"
        } else {
            reason
        };
        if !ga && !gb {
            outcome = "no_request";
            detail = "neither_authorized";
        } else if ga && gb && route.is_some() {
            let route = route.unwrap();
            // 任务L7、受限转移§2.1：最后一件矿的出库会打破持续可得，事务前停止。
            if let Some(index) = self.warehouse.get(&route.source) {
                if !self.sufficient()
                    && ["源矿", "蓝铁矿"].contains(&route.item.as_str())
                    && self.state.warehouse.slots[*index]
                        .quantity
                        .integer(&route.source)?
                        <= 1
                {
                    return Err(Stop::new(
                        "invalid_input",
                        "warehouse.external_supply",
                        format!("instant={}", self.t),
                        format!("{event}：{}将耗尽，显式补给史不满足持续可得", route.item),
                    ));
                }
            }
            if let Some(i) = self.gate_index.get(&target_unit) {
                let g = &self.state.logistics.gate_counters[*i];
                add(g.total_received.integer(&target_unit)?, 1, &target_unit)?;
                add(g.window_received.integer(&target_unit)?, 1, &target_unit)?;
                let setting = &self.input.gate_settings[&target_unit];
                let mut cuts = false;
                for (field, count) in [
                    ("total_limit", g.total_received.integer(&target_unit)?),
                    ("window_limit", g.window_received.integer(&target_unit)?),
                ] {
                    if !setting[field].is_null()
                        && add(count, 1, field)? >= num(&setting[field], field)?
                    {
                        cuts = true;
                    }
                }
                if cuts {
                    let mut active = self.active.clone();
                    active.remove(cid);
                    self.check_branch_graph(&active)?;
                }
                if g.window_started_at.is_none() {
                    self.precheck_new_event(&format!(
                        "W|{}|{}",
                        add(
                            self.t,
                            self.input.catalog.kinds["物品准入口"].window,
                            &target_unit
                        )?,
                        target_unit
                    ))?;
                }
            }
            let warehouse = self.input.catalog.kinds[&self.input.geometry.units[&target_unit].kind]
                .family
                == "core";
            let plan = if warehouse {
                Some(
                    self.plan_deposit(&BTreeMap::from([(route.item.clone(), 1)]), false)?
                        .ok_or_else(|| Stop::invalid(cid, "拟提交容量变化"))?,
                )
            } else {
                None
            };
            if let Some(plan) = plan {
                if self.production_abstraction && crate::ledger::ORES.contains(&route.item.as_str())
                {
                    return Err(Stop::unsupported(
                        "cycle.domain.D2",
                        event,
                        "生产抽象不允许矿石回仓",
                    ));
                }
                self.commit_deposit(&plan, false)?;
                self.book("core_inbound",json!({"event":event,"channel":cid,"port":c.target_port,"item":route.item,"quantity":q(1)}));
            } else {
                self.put(&route.target, &route.item, 1)?;
            }
            if self.warehouse.contains_key(&route.source) {
                self.book("port_outbound",json!({"event":event,"channel":cid,"port":c.source_port,"slot":route.source,"item":route.item,"quantity":q(1)}));
                if self.sufficient() && crate::ledger::ORES.contains(&route.item.as_str()) {
                    let n = add(
                        self.supplied.get(&route.item).copied().unwrap_or(0),
                        1,
                        "supply",
                    )?;
                    self.supplied.insert(route.item.clone(), n);
                    self.book("external_supply",json!({"event":event,"mode":"sufficient","item":route.item,"quantity":q(1)}));
                } else {
                    self.remove(&route.source, &route.item, 1)?;
                }
            } else {
                self.remove(&route.source, &route.item, 1)?;
            }
            self.usage.insert(c.source_port.clone(), 1);
            self.usage.insert(c.target_port.clone(), 1);
            {
                self.movements
                    .push(json!({"event":event,"channel":cid,"item":route.item,"quantity":q(1)}));
            }
            outcome = "success";
            detail = "";
        }
        if ga {
            self.advance(a, cid)?;
        }
        if gb {
            self.advance(b, cid)?;
        }
        let ties = self.tie_sides.clone();
        if outcome == "success" {
            if let Some(i) = self.gate_index.get(&target_unit).copied() {
                let window = self.input.catalog.kinds["物品准入口"].window;
                let g = &mut self.state.logistics.gate_counters[i];
                g.total_received = Quantity::calc(add(
                    g.total_received.integer(&target_unit)?,
                    1,
                    &target_unit,
                )?);
                g.window_received = Quantity::calc(add(
                    g.window_received.integer(&target_unit)?,
                    1,
                    &target_unit,
                )?);
                let opened = g.window_started_at.is_none();
                if opened {
                    g.window_started_at = Some(Time::at(self.t));
                }
                let setting = &self.input.gate_settings[&target_unit];
                for (field, reason, count) in [
                    (
                        "total_limit",
                        "total_exhausted",
                        g.total_received.integer(&target_unit)?,
                    ),
                    (
                        "window_limit",
                        "window_exhausted",
                        g.window_received.integer(&target_unit)?,
                    ),
                ] {
                    if !setting[field].is_null()
                        && count >= num(&setting[field], field)?
                        && !g.blocked_reasons.iter().any(|r| r == reason)
                    {
                        g.blocked_reasons.push(reason.into());
                    }
                }
                if opened {
                    let deadline = add(self.t, window, &target_unit)?;
                    let id = format!("W|{deadline}|{target_unit}");
                    self.allocate(&id)?;
                    self.pending.push(Pending {
                        event: id,
                        operation: "gate_window_expiry".into(),
                        target: target_unit,
                        trigger: json!({"kind":"at_time","value":tv(deadline)}),
                        predecessors: vec![],
                        status: "waiting".into(),
                    });
                }
                self.rebuild_graph()?;
            }
        }
        let mut basis = vec![
            "规则 L13、L15–17、L23–25、L29–32".into(),
            "约束端口速率".into(),
            "受限模型声明 polling.both_failure".into(),
            "内核输入 §5.2、§6.3".into(),
        ];
        if !ties.is_empty() {
            basis.push(format!(
                "polling.level_tie=fixed_arbitration:{}",
                ties.join(",")
            ));
        }
        if !self.damping_used.borrow().is_empty() {
            basis.push(format!(
                "damping.evaluated:{}",
                self.damping_used
                    .borrow()
                    .iter()
                    .cloned()
                    .collect::<Vec<_>>()
                    .join(";")
            ));
        }
        Ok((outcome.into(), detail.into(), basis))
    }
    /// 受限转移§1、§2.1：未实现外部动作在对应时刻、变更任何物理量之前停止。
    fn check_external_stops(&self, t: i64) -> Result<()> {
        let supply = self
            .input
            .parameters
            .value(crate::config::Axis::WarehouseExternalSupply)?;
        if supply["kind"] == "explicit_ore_history"
            && t > instant(&supply["through"], "warehouse.external_supply.through")?
        {
            return Err(Stop::unsupported(
                "warehouse.external_supply",
                format!("instant={t}"),
                "请求超出显式外部历史覆盖区间",
            ));
        }
        let history = &self.input.raw;
        let events = history["timeline"]["events"].as_array().unwrap();
        for row in events {
            let Some(kind) = row["kind"].as_str() else {
                continue;
            };
            if [
                "runtime",
                "connection_open",
                "blueprint_complete",
                "debug_end",
            ]
            .contains(&kind)
            {
                continue;
            }
            let axis = match kind {
                "offline" => "offline.events",
                "withdraw_product" => "warehouse.withdrawal_timing",
                "debug_operation" => "initialization.debug_actions",
                "unit_removed" | "unit_rebuilt" => "initialization.rebuild_inventory",
                "build" => "initialization.build_timing",
                _ => continue,
            };
            let at = if row["time"].is_null() {
                return Err(Stop::unsupported(
                    axis,
                    row["id"].as_str().unwrap_or("timeline"),
                    "事件时刻未解释",
                ));
            } else {
                instant(&row["time"], "timeline.event.time")?
            };
            // 初刻建成事件已由种子历史消费；后续结构变化必须停止。
            if at == t && !(kind == "build" && self.first) {
                return Err(Stop::unsupported(
                    axis,
                    row["id"].as_str().unwrap_or("timeline"),
                    "运行区间触及未实现后效",
                ));
            }
        }
        let policy = &history["environment"]["product_withdrawal"]["policy"];
        if policy["status"] == "specified"
            && policy["value"]["rules"]
                .as_array()
                .is_some_and(|r| !r.is_empty())
        {
            return Err(Stop::unsupported(
                "warehouse.withdrawal_policy",
                format!("instant={t}"),
                "拿取策略求值不在本版",
            ));
        }
        Ok(())
    }
    /// 受限转移§2.1：旧功能推进工作/冷却，完成按输入制造模板序，窗口原子批到期。
    fn boundary(&mut self, advance: bool) -> Result<()> {
        if advance {
            for i in 0..self.state.progress.len() {
                let uid = self.state.progress[i].unit.clone();
                if self.state.progress[i].phase == "working" && self.enabled(&uid, "manufacture") {
                    let p = &mut self.state.progress[i];
                    let n = p.remaining.as_ref().unwrap().integer(&uid)?;
                    p.remaining = Some(Time::at(n - 1));
                }
                if !self.state.progress[i].cooldowns.is_empty() && self.enabled(&uid, "transfer") {
                    let c = &mut self.state.progress[i].cooldowns[0];
                    c.remaining = Time::at((c.remaining.integer(&uid)? - 1).max(0));
                }
            }
            self.t = add(self.t, 1, "time")?;
        }
        self.state.environment.time = Time::at(self.t);
        self.usage.clear();
        let units: Vec<_> = self
            .input
            .templates
            .iter()
            .filter(|t| t.operation == "manufacture")
            .map(|t| t.target.clone())
            .collect();
        for uid in units {
            let i = self.progress[&uid];
            if self.state.progress[i].phase == "working"
                && self.state.progress[i]
                    .remaining
                    .as_ref()
                    .unwrap()
                    .integer(&uid)?
                    == 0
            {
                let p = self
                    .pending
                    .iter()
                    .position(|p| p.operation == "manufacture_complete" && p.target == uid)
                    .ok_or_else(|| Stop::invalid(&uid, "完成日程缺失"))?;
                let pending = self.pending.remove(p);
                self.execute(&pending.event)?;
                let recipe = self.input.catalog.recipes
                    [self.state.progress[i].recipe.as_ref().unwrap()]
                .clone();
                let buffer = format!("{uid}:buffer:0");
                self.state.inventory[self.inv[&buffer]].contents.clear();
                for (item, n) in recipe.outputs {
                    self.put(&buffer, &item, n)?;
                }
                self.state.progress[i].phase = "completed".into();
                self.state.progress[i].remaining = Some(Time::at(0));
                self.completed_batches = add(self.completed_batches, 1, "completed_batches")?;
                self.record(Event {
                    event: pending.event,
                    operation: "manufacture_complete".into(),
                    target: uid,
                    outcome: "success".into(),
                    detail: None,
                    basis: vec![
                        "规则 L35".into(),
                        "运行语义 §4.1".into(),
                        "受限模型声明 time.manufacture_events".into(),
                    ],
                });
            }
        }
        self.ore_supply()?;
        self.check_ore_availability()?;
        let mut expired: Vec<_> = self
            .pending
            .iter()
            .filter(|p| p.operation == "gate_window_expiry")
            .filter_map(|p| match instant(&p.trigger["value"], &p.event) {
                Ok(t) if t <= self.t => Some(Ok((p.target.clone(), p.event.clone()))),
                Ok(_) => None,
                Err(e) => Some(Err(e)),
            })
            .collect::<Result<_>>()?;
        expired.sort();
        if !expired.is_empty() {
            for (uid, _) in &expired {
                let g = &mut self.state.logistics.gate_counters[self.gate_index[uid]];
                g.window_received = Quantity::calc(0);
                g.window_started_at = None;
                g.blocked_reasons.retain(|r| r != "window_exhausted");
            }
            self.rebuild_graph()?;
            let names = expired
                .iter()
                .map(|(u, _)| u.as_str())
                .collect::<Vec<_>>()
                .join(",");
            for (uid, id) in expired {
                self.execute(&id)?;
                self.pending.retain(|p| p.event != id);
                self.record(Event {
                    event: id,
                    operation: "gate_window_expiry".into(),
                    target: uid,
                    outcome: "success".into(),
                    detail: Some(format!("atomic_batch:{names}")),
                    basis: vec![
                        "规则 L64".into(),
                        "受限转移定义 §2.1、§3.4".into(),
                        "gate.concurrent_expiry=atomic_batch".into(),
                    ],
                });
            }
        }
        Ok(())
    }
    /// 任务L7、输入§5.4、转移§2.1：sufficient装载及边界补给后核两矿正库存。
    pub(crate) fn check_ore_availability(&self) -> Result<()> {
        for item in ["源矿", "蓝铁矿"] {
            let available = self
                .state
                .warehouse
                .slots
                .iter()
                .find(|row| row.item.as_deref() == Some(item))
                .map(|row| row.quantity.integer(&row.slot))
                .transpose()?
                .unwrap_or(0)
                > 0;
            if !available {
                return Err(Stop::new(
                    "invalid_input",
                    "warehouse.external_supply",
                    format!("instant={}", self.t),
                    format!("{item}无正库存，不满足两矿持续可得"),
                ));
            }
        }
        Ok(())
    }
    /// 受限转移§2.1、§4.1：显式两矿补给按输入数组顺序原子入库，绝不自动补满。
    fn ore_supply(&mut self) -> Result<()> {
        let supply = self
            .input
            .parameters
            .value(crate::config::Axis::WarehouseExternalSupply)?
            .clone();
        if supply["kind"] == "sufficient" {
            return Ok(());
        }
        if supply["kind"] != "explicit_ore_history" {
            return Err(Stop::unsupported(
                "warehouse.external_supply",
                "parameters.warehouse.external_supply",
                "缺显式矿石历史",
            ));
        }
        let rows: Vec<Value> = decode(supply["events"].clone(), "ore_supply.events")?;
        for row in rows {
            fields(&row, "event time item quantity", "ore_supply.events[]")?;
            if instant(&row["time"], "ore_supply.time")? != self.t {
                continue;
            }
            let item = row["item"].as_str().unwrap_or("");
            if !["源矿", "蓝铁矿"].contains(&item) {
                return Err(Stop::invalid(
                    "warehouse.external_supply",
                    "外部过程只能补两矿",
                ));
            }
            let n = num(&row["quantity"], "ore_supply.quantity")?;
            if n <= 0 {
                return Err(Stop::invalid("ore_supply.quantity", "补给须正数"));
            }
            let id = row["event"]
                .as_str()
                .ok_or_else(|| Stop::invalid("ore_supply.event", "缺事件身份"))?;
            if self.executed.contains(id) {
                return Err(Stop::invalid(id, "补给事件重复"));
            }
            let plan = self
                .plan_deposit(&BTreeMap::from([(item.into(), n)]), false)?
                .ok_or_else(|| Stop::invalid(id, "外部补给超仓库容量"))?;
            if !self.allocated.contains(id) {
                self.allocate(id)?;
            }
            self.commit_deposit(&plan, true)?;
            self.book(
                "external_supply",
                json!({"event":id,"mode":"explicit_ore_history","item":item,"quantity":q(n)}),
            );
            self.execute(id)?;
            self.record(Event {
                event: id.into(),
                operation: "ore_supply".into(),
                target: "warehouse".into(),
                outcome: "success".into(),
                detail: Some(
                    serde_json::to_string(&row).map_err(|e| Stop::invalid(id, e.to_string()))?,
                ),
                basis: vec!["受限转移定义 §2.1、§4.1；任务外部过程".into()],
            });
        }
        Ok(())
    }
    /// 受限转移§5.1：完整可影响后继的动态投影按内容判等，排除轮号/日志。
    fn closure_key(&self) -> Result<Vec<u8>> {
        serde_json::to_vec(&(
            &self.state.warehouse,
            &self.state.inventory,
            &self.state.progress,
            &self.memory,
            &self.state.logistics.active_channels,
            &self.state.logistics.blocked_channels,
            &self.state.logistics.gate_counters,
            &self.state.logistics.connection_order,
            &self.state.semantic_context.arbitration,
            &self.pending,
            &self.usage,
        ))
        .map_err(|e| Stop::invalid("closure_key", e.to_string()))
    }
    /// 受限转移§1：处理当前整数时刻的边界前锚点，不重复处理已经闭包的时刻。
    pub fn step_instant(&mut self, capture: bool) -> Result<Option<Value>> {
        if !self.first
            || self.state.semantic_context.judgment_context.value["phase"] != "before_boundary"
        {
            return Err(Stop::invalid("step_instant", "需要 before_boundary 锚点"));
        }
        self.step(capture)
    }
    /// 受限转移§1：从已闭包时刻推进到下一整数时刻并完成闭包。
    pub fn step_tick(&mut self, capture: bool) -> Result<Option<Value>> {
        if self.state.semantic_context.judgment_context.value["phase"] != "after_closure" {
            return Err(Stop::invalid("step_tick", "需要 after_closure 锚点"));
        }
        self.step(capture)
    }
    /// 受限转移§2–§5：一个整数时刻至首次完整边界重复，资源上限只回 inconclusive。
    pub fn step(&mut self, capture: bool) -> Result<Option<Value>> {
        self.step_with_snapshot(capture, true)
    }
    /// 第六轮：保留本刻审计事件及台账，不序列化完整输出快照。
    pub fn step_compact(&mut self) -> Result<()> {
        self.step_with_snapshot(true, false).map(|_| ())
    }
    fn step_with_snapshot(&mut self, capture: bool, snapshot: bool) -> Result<Option<Value>> {
        if let Some(stop) = &self.halted {
            return Err(stop.clone());
        }
        self.active_event = None;
        let result = self.step_inner(capture, snapshot);
        match result {
            Ok(value) => {
                self.active_event = None;
                Ok(value)
            }
            Err(mut stop) => {
                if let Some(id) = &self.active_event {
                    stop.location = format!("{id}: {}", stop.location);
                }
                self.halted = Some(stop.clone());
                Err(stop)
            }
        }
    }
    /// 受限转移§2–§5：内部推进；失败后实例封存，不可把部分阶段当新种子续跑。
    fn step_inner(&mut self, capture: bool, snapshot: bool) -> Result<Option<Value>> {
        self.invalidate_all();
        self.damping_used.borrow_mut().clear();
        self.level_keys.borrow_mut().clear();
        self.capture = capture;
        self.records.clear();
        self.ledger = crate::ledger::empty_ledger();
        self.movements.clear();
        self.passages.clear();
        let advance = !self.first
            || self.state.semantic_context.judgment_context.value["phase"] == "after_closure";
        let next = if advance {
            add(self.t, 1, "time")?
        } else {
            self.t
        };
        self.check_external_stops(next)?;
        if self.production_abstraction {
            self.represent_products()?;
        }
        self.boundary(advance)?;
        self.first = false;
        self.refresh()?;
        let mut seen = BTreeSet::new();
        seen.insert(self.closure_key()?);
        let mut rounds = 0;
        loop {
            if rounds >= self.max_sweeps {
                return Err(Stop::new(
                    "inconclusive",
                    "resource.sweeps",
                    format!("instant={} sweep={rounds}", self.t),
                    "未见完整状态重复，不能推进时刻",
                ));
            }
            for i in 0..self.input.templates.len() {
                let maintenance = self.maintain_identity()?;
                if let Some(detail) = maintenance {
                    let id = format!("I|{}|{rounds}|{i}", self.t);
                    self.allocate(&id)?;
                    self.execute(&id)?;
                    self.record(Event {
                        event: id,
                        operation: "gate_identity_maintenance".into(),
                        target: "gates".into(),
                        outcome: "success".into(),
                        detail: Some(detail),
                        basis: vec!["受限转移定义§2.2；KQ-05".into()],
                    });
                }
                let template = self.input.templates[i].clone();
                let id = format!("J|{}|{rounds}|{i}", self.t);
                self.active_event = Some(id.clone());
                self.allocate(&id)?;
                self.execute(&id)?;
                let (outcome, detail, basis) = match template.operation.as_str() {
                    "move" => self.move_channel(&template.target, &id)?,
                    "manufacture" => (
                        self.manufacture(&template.target, &id)?,
                        String::new(),
                        vec![
                            "规则 L18、L35".into(),
                            "受限转移定义 §4.2".into(),
                            "受限模型声明 manufacture_subactions、atomic_batch、same_instant"
                                .into(),
                        ],
                    ),
                    "transfer" => {
                        let (a, b) = self.transfer(&template.target, &id)?;
                        (
                            a,
                            b,
                            vec!["规则 L20–21、L36".into(), "受限转移定义 §4.3".into()],
                        )
                    }
                    _ => return Err(Stop::unsupported("judgment.order", &id, "未知模板")),
                };
                self.record(Event {
                    event: id,
                    operation: template.operation,
                    target: template.target,
                    outcome,
                    detail: Some(detail),
                    basis,
                });
            }
            rounds += 1;
            self.refresh()?;
            if !seen.insert(self.closure_key()?) {
                break;
            }
        }
        self.state.logistics.poll_memory.value = json!(self.memory);
        self.state.semantic_context.judgment_context = Decision::specified(
            json!({"instant":tv(self.t),"phase":"after_closure","order_scope":"global","round":rounds,"next_template":0,"ordered_events":[],"next_event":null}),
            "完整扫描边界重复，保留轮询状态",
        );
        // 内核输出§2：完成队列先于窗口队列；同类按创建顺序保留事件身份。
        let pending: Vec<_> = self
            .pending
            .iter()
            .filter(|p| p.operation == "manufacture_complete")
            .chain(
                self.pending
                    .iter()
                    .filter(|p| p.operation == "gate_window_expiry"),
            )
            .collect();
        self.state.semantic_context.pending_events = Decision::specified(
            json!(pending),
            if self.gate_index.is_empty() {
                "制造耗时生成的非判定到期事件"
            } else {
                "制造完成及准入口窗口的非判定到期事件"
            },
        );
        self.state.semantic_context.tick_context = Decision::specified(
            json!({"window_start":tv(self.t),"window_end":tv(add(self.t,1,"time")?),"movements":self.movements,"port_usage":self.usage.iter().map(|(p,n)|json!({"port":p,"quantity":q(*n)})).collect::<Vec<_>>(),"internal_passages":self.passages}),
            "本时刻实际成功记录",
        );
        self.ledger["totals"] = crate::ledger::totals(&self.ledger)?;
        if capture && snapshot {
            Ok(Some(
                json!({"time":tv(self.t),"events":self.records,"state":self.state,"warehouse_ledger":self.ledger,"summary":self.summary()?,"closure":{"kind":"no_success_state_repeat","scan_rounds":rounds,"basis":["受限模型声明 time.instant_end","内核输入 §5.2","工程出口保留首次重复的完整扫描边界成员；一般真实唤醒对应为PC-06未完成义务"]}}),
            ))
        } else {
            Ok(None)
        }
    }
    /// 内核输出§2：样例摘要只是完整状态的投影，不影响任何转移守卫。
    pub fn summary(&self) -> Result<Value> {
        let mut nonempty = serde_json::Map::new();
        for s in &self.state.inventory {
            if !s.contents.is_empty() {
                nonempty.insert(s.slot.clone(),json!(s.contents.iter().map(|c|json!({"item":c.item,"quantity":c.quantity.value,"entered_at":c.entered_at.as_ref().map(|t|t.value.value.clone())})).collect::<Vec<_>>()));
            }
        }
        let ore = self
            .state
            .warehouse
            .slots
            .iter()
            .find(|r| r.item.as_deref() == Some("源矿"))
            .map(|r| r.quantity.value.clone())
            .unwrap_or_else(|| "0".into());
        let cursor = |uid: &str| -> Option<String> {
            self.side_index
                .get(&(uid.into(), "output".into()))
                .and_then(|i| self.memory.sides[*i].levels.first())
                .map(|l| l.next_channel.clone())
        };
        if self.input.raw["scenario"]["name"] == "混做粉碎机两下游"
            && self.progress.contains_key("crusher")
        {
            let p = &self.state.progress[self.progress["crusher"]];
            return Ok(
                json!({"tick":self.t.to_string(),"warehouse_ore":ore,"nonempty":nonempty,"crusher_phase":p.phase,"crusher_remaining":p.remaining.as_ref().map(|r|r.value.value.clone()),"crusher_next_output":cursor("crusher"),"completed_batches":self.completed_batches.to_string()}),
            );
        }
        if self.input.raw["scenario"]["name"] == "分流器三路轮询" {
            let mut boxes = BTreeMap::new();
            for uid in ["north_box", "east_box", "west_box"] {
                let n = self
                    .state
                    .inventory
                    .iter()
                    .filter(|s| s.slot.starts_with(&format!("{uid}:")))
                    .flat_map(|s| &s.contents)
                    .try_fold(0, |n, c| add(n, c.quantity.integer(uid)?, uid))?;
                boxes.insert(uid, n.to_string());
            }
            return Ok(
                json!({"tick":self.t.to_string(),"warehouse_ore":ore,"nonempty":nonempty,"splitter_next_output":cursor("splitter"),"delivered_to_boxes":boxes}),
            );
        }
        Ok(
            json!({"tick":self.t.to_string(),"nonempty":nonempty,"completed_batches":self.completed_batches.to_string(),"actual_inbound":self.delivery,"external_supply":self.supplied}),
        )
    }
    /// 第四轮§4.8：关闭逐刻快照与日志，仍执行全部转移及精确闭包检查。
    pub fn run_without_output(&mut self, ticks: usize) -> Result<()> {
        for _ in 0..ticks {
            self.step(false)?;
        }
        Ok(())
    }
}
