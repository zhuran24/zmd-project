//! 受限转移§4.1、§4.3：仓库身份、批量计划与原子提交。
use crate::{
    engine::{Deposit, Engine},
    model::WarehouseSlot,
    value::*,
};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
impl Engine {
    /// 受限模型声明§2的两条接收域轴：逐边界分开报告容量和物理入库接口，不作移动守卫。
    pub fn acceptance_report(&self) -> Result<Value> {
        let channels: Vec<_> = self
            .active
            .iter()
            .filter(|id| {
                let channel = &self.input.geometry.channels[*id];
                let target = &self.input.geometry.ports[&channel.target_port];
                self.input.catalog.kinds[&self.input.geometry.units[&target.unit].kind].family
                    == "core"
            })
            .cloned()
            .collect();
        let boxes: Vec<_> = self
            .input
            .geometry
            .units
            .iter()
            .filter(|(uid, u)| u.kind == "协议储存箱" && self.enabled(uid, "transfer"))
            .map(|(uid, _)| uid.clone())
            .collect();
        let path_available = !channels.is_empty() || !boxes.is_empty();
        let mut products = Vec::new();
        for item in ["高容谷地电池", "精选荞愈胶囊"] {
            let stored = self
                .state
                .warehouse
                .slots
                .iter()
                .find(|r| r.item.as_deref() == Some(item))
                .map(|r| r.quantity.integer(&r.slot))
                .transpose()?
                .unwrap_or(0);
            let free = self.input.catalog.warehouse_capacity - stored;
            products.push(json!({"item":item,"free_capacity":q(free),"capacity_available":free>0,
                "physical_path_exists":path_available,"capacity_and_path":free>0 && path_available}));
        }
        Ok(
            json!({"time":tv(self.t),"phase":"after_closure","products":products,
            "core_input_channels":channels,"enabled_transfer_units":boxes,
            "path_scope":"入库途径仅指当前现存核心存货PC或有电且开关开的箱体传输接口；不承诺成品已到达、端口本刻余量、冷却就绪或全程送料可达。",
            "both_products_capacity_and_path":products.iter().all(|p| p["capacity_and_path"]==true)}),
        )
    }
    /// 受限转移§4.1：身份唯一性与 E/O 全序每次拟提交前核验。
    pub(crate) fn warehouse_targets(&self) -> Result<BTreeMap<String, String>> {
        if self.state.warehouse.unlisted != "empty" {
            return Err(Stop::invalid("warehouse.unlisted", "未列库存必须为空"));
        }
        let mut result = BTreeMap::new();
        let mut empty = Vec::new();
        for row in &self.state.warehouse.slots {
            let id = &row.slot;
            let n = row.quantity.integer(id)?;
            if id.is_empty() || self.inv.contains_key(id) || reserved_slot(id) {
                return Err(Stop::invalid(id, "仓库标签占用单位格命名域"));
            }
            if n < 0 || n > self.input.catalog.warehouse_capacity || (n == 0) != row.item.is_none()
            {
                return Err(Stop::invalid(id, "仓库数量/物种/容量不符"));
            }
            let identity = if let Some(item) = &row.item {
                if row.empty_identity.status != "not_applicable"
                    || !row.empty_identity.value.is_null()
                {
                    return Err(Stop::invalid(id, "非空格 empty_identity 必须不适用"));
                }
                Some(item.as_str())
            } else {
                let v = row.empty_identity.resolved(id, true)?;
                if !v.is_null() && !v.is_string() {
                    return Err(Stop::invalid(id, "空格身份不是物种或 null"));
                }
                v.as_str()
            };
            if let Some(item) = identity {
                if item.is_empty() || result.insert(item.into(), id.clone()).is_some() {
                    return Err(Stop::invalid(id, "非空/历史物种目标冲突，输入须消歧"));
                }
            } else {
                empty.push(id.clone())
            }
        }
        crate::input::permutation(
            &self
                .state
                .semantic_context
                .arbitration
                .warehouse_empty_slot_order,
            empty,
            "arbitration.warehouse_empty_slot_order",
        )?;
        Ok(result)
    }
    /// 受限转移§4.3 第1–3步：竞争先停，再按有据的规范命名拟定完整批目标。
    pub(crate) fn plan_deposit(
        &self,
        items: &BTreeMap<String, i64>,
        batch: bool,
    ) -> Result<Option<Vec<Deposit>>> {
        self.plan_receipt(items, batch, false)
    }
    /// 规则L36只令无线传输尽量送入；核心单件与显式补矿继续完整事务。
    fn plan_receipt(
        &self,
        items: &BTreeMap<String, i64>,
        batch: bool,
        partial: bool,
    ) -> Result<Option<Vec<Deposit>>> {
        let identities = self.warehouse_targets()?;
        let empty = &self
            .state
            .semantic_context
            .arbitration
            .warehouse_empty_slot_order;
        let unknown: Vec<_> = items
            .keys()
            .filter(|k| !identities.contains_key(*k))
            .collect();
        if batch
            && unknown.len() >= 2
            && empty
                .iter()
                .any(|slot| self.input.assignments.values().any(|s| s == slot))
        {
            return Err(Stop::unsupported(
                "warehouse.empty_slot_identity",
                format!("instant={} warehouse", self.t),
                "competing_new_species：至少两种新物种且 E 有被端口指派格",
            ));
        }
        let mut next = 0;
        let mut plan = Vec::new();
        let mut rejected = false;
        for (item, count) in items {
            if *count <= 0 {
                return Err(Stop::invalid("warehouse.deposit", "批物料量须为正"));
            }
            let (slot, create) = if let Some(slot) = identities.get(item) {
                (slot.clone(), false)
            } else if next < empty.len() {
                let s = empty[next].clone();
                next += 1;
                (s, false)
            } else {
                let s = format!(
                    "W_new_{}",
                    item.as_bytes()
                        .iter()
                        .map(|b| format!("{b:02x}"))
                        .collect::<String>()
                );
                if self.warehouse.contains_key(&s) || self.inv.contains_key(&s) {
                    return Err(Stop::invalid(&s, "规范新标签冲突；输入没有替代标签接口"));
                }
                (s, true)
            };
            let old = if create {
                0
            } else {
                self.state.warehouse.slots[self.warehouse[&slot]]
                    .quantity
                    .integer(&slot)?
            };
            let count = if partial {
                (*count).min(self.input.catalog.warehouse_capacity - old)
            } else {
                *count
            };
            if count == 0 {
                continue;
            }
            let total = add(old, count, &slot)?;
            if total > self.input.catalog.warehouse_capacity {
                rejected = true;
            }
            plan.push(Deposit {
                slot,
                item: item.clone(),
                count,
                create,
            });
        }
        Ok(if rejected { None } else { Some(plan) })
    }
    /// 受限转移§4.1：全批容量已核，提交身份、库存与 O 的稳定子序。
    pub(crate) fn commit_deposit(&mut self, plan: &[Deposit], external: bool) -> Result<()> {
        self.invalidate_unit("@warehouse");
        // 先计算所有可能溢出的账量，确保提交过程中没有可失败算术。
        let ledger = if external {
            &self.supplied
        } else {
            &self.delivery
        };
        let mut counts = Vec::new();
        for p in plan {
            counts.push(add(
                ledger.get(&p.item).copied().unwrap_or(0),
                p.count,
                &p.slot,
            )?)
        }
        let used: BTreeSet<_> = plan.iter().map(|p| p.slot.clone()).collect();
        for (p, count) in plan.iter().zip(counts) {
            let identity = Decision {
                status: "not_applicable".into(),
                value: serde_json::Value::Null,
                basis: vec!["受限转移定义 §4.1：非空身份由 item 承载".into()],
            };
            if p.create {
                let index = self.state.warehouse.slots.len();
                self.state.warehouse.slots.push(WarehouseSlot {
                    slot: p.slot.clone(),
                    item: Some(p.item.clone()),
                    quantity: Quantity::calc(p.count),
                    empty_identity: identity,
                });
                self.warehouse.insert(p.slot.clone(), index);
            } else {
                let r = &mut self.state.warehouse.slots[self.warehouse[&p.slot]];
                let old = r.quantity.integer(&p.slot)?;
                r.quantity = Quantity::calc(old + p.count);
                if r.item.is_none() {
                    r.empty_identity = identity;
                }
                r.item = Some(p.item.clone());
            }
            if external {
                self.supplied.insert(p.item.clone(), count);
            } else {
                self.delivery.insert(p.item.clone(), count);
            }
        }
        self.state
            .semantic_context
            .arbitration
            .warehouse_empty_slot_order
            .retain(|s| !used.contains(s));
        Ok(())
    }
    /// 受限转移§4.3：逐物种部分接收，未定义跨编号格残留在提交前停止。
    pub(crate) fn transfer(&mut self, uid: &str, event: &str) -> Result<(String, String)> {
        if !self.enabled(uid, "transfer") {
            return Ok(("guard_false".into(), "function_disabled".into()));
        }
        let i = self.progress[uid];
        if self.state.progress[i].cooldowns[0].remaining.integer(uid)? != 0 {
            return Ok(("guard_false".into(), "cooldown".into()));
        }
        let mut items = BTreeMap::new();
        let mut slots = Vec::new();
        for slot in self
            .slot_groups
            .get(&(uid.into(), "storage".into()))
            .into_iter()
            .flatten()
        {
            {
                let index = self.inv[slot];
                slots.push(index);
                for c in &self.state.inventory[index].contents {
                    let n = items.entry(c.item.clone()).or_insert(0);
                    *n = add(*n, c.quantity.integer(slot)?, slot)?
                }
            }
        }
        if self.production_abstraction
            && items
                .keys()
                .any(|s| crate::ledger::ORES.contains(&s.as_str()))
        {
            return Err(Stop::unsupported(
                "cycle.domain.D2",
                event,
                "生产抽象不允许矿石回仓",
            ));
        }
        let plan = self.plan_receipt(&items, true, true)?
            .ok_or_else(|| Stop::invalid(event, "部分接收规划意外拒收"))?;
        let mut removals = Vec::new();
        for p in &plan {
            let sources: Vec<_> = slots.iter().copied().filter(|index| {
                self.state.inventory[*index].contents.iter().any(|c| c.item == p.item)
            }).collect();
            if p.count < items[&p.item] && sources.len() > 1 {
                return Err(Stop::unsupported(
                    "transfer.partial_acceptance", event,
                    format!("{}部分送出且分占多个编号格；规则L72只定端口顺序，无线残留分配待推导", p.item),
                ));
            }
            for index in sources {
                let row = &self.state.inventory[index];
                let n = row.contents.iter().try_fold(0, |n, c| {
                    add(n, c.quantity.integer(&row.slot)?, &row.slot)
                })?;
                removals.push((row.slot.clone(), p.item.clone(), n.min(p.count)));
            }
        }
        // 全部容量、落格竞争和残留后态均核完之后，才提交物品与台账。
        self.commit_deposit(&plan, false)?;
        for (slot, item, count) in removals {
            self.remove(&slot, &item, count)?;
        }
        for p in &plan {
            self.book("wireless_inbound", json!({
                "event":event,"unit":uid,"item":p.item,"quantity":q(p.count)
            }));
        }
        let sent: BTreeMap<_, _> = plan.iter().map(|p| (p.item.clone(), p.count)).collect();
        let retained: BTreeMap<_, _> = items.iter().map(|(item, n)| {
            (item.clone(), n - sent.get(item).copied().unwrap_or(0))
        }).filter(|(_, n)| *n > 0).collect();
        let outcome = if !items.is_empty() && plan.is_empty() { "failure" } else { "success" };
        let detail = json!({"sent":sent,"retained":retained,"cooldown_restarted":true}).to_string();
        self.state.progress[i].cooldowns[0].remaining =
            Time::at(self.input.catalog.kinds[&self.input.geometry.units[uid].kind].cooldown);
        Ok((outcome.into(), detail))
    }
    /// 第四轮§4.7：逐物种完整库存账，缓存原料在完成之前仍在账上。
    pub fn inventory_totals(&self) -> Result<BTreeMap<String, i64>> {
        let mut totals = BTreeMap::new();
        for r in &self.state.warehouse.slots {
            if let Some(item) = &r.item {
                let n = totals.entry(item.clone()).or_insert(0);
                *n = add(*n, r.quantity.integer(&r.slot)?, &r.slot)?
            }
        }
        for s in &self.state.inventory {
            for c in &s.contents {
                let n = totals.entry(c.item.clone()).or_insert(0);
                *n = add(*n, c.quantity.integer(&s.slot)?, &s.slot)?
            }
        }
        Ok(totals)
    }
    /// 受限转移§4.1：无身份空格集合，用于单调性测试及检查点验收。
    pub fn empty_slots(&self) -> BTreeSet<String> {
        self.state
            .warehouse
            .slots
            .iter()
            .filter(|r| r.item.is_none() && r.empty_identity.value.is_null())
            .map(|r| r.slot.clone())
            .collect()
    }
    /// 受限转移§4.1：测试及复验用的显式整批入库入口，沿用真实计划/提交守卫。
    pub fn deposit(&mut self, items: BTreeMap<String, i64>) -> Result<bool> {
        if let Some(p) = self.plan_deposit(&items, true)? {
            self.commit_deposit(&p, false)?;
            Ok(true)
        } else {
            Ok(false)
        }
    }
}
/// 内核输入§2.3：仓库自由标签避开本地格保留语法。
pub(crate) fn reserved_slot(id: &str) -> bool {
    let p: Vec<_> = id.split(':').collect();
    p.len() == 3
        && !p[0].is_empty()
        && p[0].as_bytes()[0].is_ascii_alphabetic()
        && p[0].bytes().all(|b| b.is_ascii_alphanumeric() || b == b'_')
        && !p[1].is_empty()
        && p[1].bytes().all(|b| b.is_ascii_lowercase() || b == b'_')
        && !p[2].is_empty()
        && p[2].bytes().all(|b| b.is_ascii_digit())
}
