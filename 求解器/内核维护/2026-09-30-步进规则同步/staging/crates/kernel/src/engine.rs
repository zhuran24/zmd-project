//! 整数步边界状态、严格装载及库存事务。
use crate::{config::Axis, input::*, model::*, value::*, graph::*};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
#[derive(Clone, Debug)]
pub(crate) struct Route { pub source: String, pub target: String, pub item: String }
#[derive(Clone, Debug)]
pub(crate) struct Deposit { pub slot: String, pub item: String, pub count: i64, pub create: bool }
#[derive(Debug)]
pub struct Engine {
    pub input: Input, pub state: State, pub completed_batches: i64, pub ledger: Value,
    pub production_abstraction: bool, pub delivery: BTreeMap<String,i64>, pub supplied: BTreeMap<String,i64>,
    pub(crate) inv: BTreeMap<String,usize>, pub(crate) progress: BTreeMap<String,usize>,
    pub(crate) warehouse: BTreeMap<String,usize>, pub(crate) caps: BTreeMap<String,Option<i64>>,
    pub(crate) gate_index: BTreeMap<String,usize>, pub(crate) slot_groups: BTreeMap<(String,String),Vec<String>>,
    pub(crate) unit_inventory: BTreeMap<String,Vec<usize>>, pub(crate) t:i64,
    pub(crate) judged: Vec<bool>, pub(crate) cursor_index: BTreeMap<String,usize>, pub(crate) recency_index: BTreeMap<String,usize>,
    pub(crate) events: Vec<Event>, pub(crate) current_subject: String, pub(crate) halted: Option<Stop>,
}
impl Engine {
    pub fn new(input:Input)->Result<Self>{Self::construct(input,false)}
    pub fn new_production(input:Input)->Result<Self>{Self::construct(input,true)}
    pub fn time(&self)->i64{self.t}
    pub fn graph(&self)->&StepGraph{&self.input.graph}
    fn construct(input:Input,production:bool)->Result<Self>{
        let d:Decision=decode(input.raw["initial_state"]["nonwarehouse"].clone(),"initial_state.nonwarehouse")?;
        let mut state:State=decode(d.resolved("initial_state.nonwarehouse",false)?.clone(),"StateSeed")?;
        state.inventory.sort_by(|a,b|a.slot.cmp(&b.slot));
        state.progress.sort_by(|a,b|a.unit.cmp(&b.unit));
        state.warehouse.slots.sort_by(|a,b|a.slot.cmp(&b.slot));
        state.logistics.gate_counters.sort_by(|a,b|a.unit.cmp(&b.unit));
        let t=state.environment.time.integer("seed.time")?;
        let caps=input.catalog.slots(&input.geometry.units,input.parameters.value(Axis::BridgeCapacity)?.as_i64().ok_or_else(||Stop::invalid("bridge.capacity","须为整数"))?)?;
        permutation(&state.inventory.iter().map(|r|r.slot.clone()).collect::<Vec<_>>(),caps.keys().cloned(),"inventory")?;
        permutation(&state.progress.iter().map(|r|r.unit.clone()).collect::<Vec<_>>(),input.geometry.units.iter().filter(|(_,u)|!input.catalog.kinds[&u.kind].functions.is_empty()).map(|(u,_)|u.clone()),"progress")?;
        permutation(&state.logistics.gate_counters.iter().map(|r|r.unit.clone()).collect::<Vec<_>>(),input.gate_settings.keys().cloned(),"gate_counters")?;
        let inv:BTreeMap<_,_>=state.inventory.iter().enumerate().map(|(i,r)|(r.slot.clone(),i)).collect();
        let progress=state.progress.iter().enumerate().map(|(i,r)|(r.unit.clone(),i)).collect();
        let warehouse:BTreeMap<_,_>=state.warehouse.slots.iter().enumerate().map(|(i,r)|(r.slot.clone(),i)).collect();
        if warehouse.len()!=state.warehouse.slots.len(){return Err(Stop::invalid("warehouse","重复格"));}
        for slot in input.assignments.values(){if !warehouse.contains_key(slot){return Err(Stop::invalid(slot,"仓库指派格不存在"));}}
        let gate_index=state.logistics.gate_counters.iter().enumerate().map(|(i,r)|(r.unit.clone(),i)).collect();
        let mut slot_groups=BTreeMap::<(String,String),Vec<String>>::new();
        let mut unit_inventory:BTreeMap<String,Vec<usize>>=input.geometry.units.keys().map(|u|(u.clone(),vec![])).collect();
        for (s,i) in &inv {let p:Vec<_>=s.split(':').collect();slot_groups.entry((p[0].into(),p[1].into())).or_default().push(s.clone());unit_inventory.get_mut(p[0]).unwrap().push(*i);}
        for ((_,role),slots) in &mut slot_groups {if role=="input" {slots.sort_by_key(|s|input.slot_order.iter().position(|p|p==s).unwrap());} else {slots.sort_by_key(|s|s.rsplit(':').next().unwrap().parse::<usize>().unwrap());}}
        let judged=vec![false;input.graph.components.len()];
        let cursor_index=state.logistics.poll_state.cursors.iter().enumerate().map(|(i,r)|(r.side.clone(),i)).collect();
        let recency_index=state.logistics.poll_state.recency.iter().enumerate().map(|(i,r)|(r.unit.clone(),i)).collect();
        let engine=Self{input,state,completed_batches:0,ledger:crate::ledger::empty_ledger(),production_abstraction:production,delivery:BTreeMap::new(),supplied:BTreeMap::new(),inv,progress,warehouse,caps,gate_index,slot_groups,unit_inventory,t,judged,cursor_index,recency_index,events:vec![],current_subject:String::new(),halted:None};
        engine.validate_seed()?;Ok(engine)
    }
    fn validate_seed(&self)->Result<()> {
        if self.state.layout_snapshot != self.input.raw["layout"]["id"]
            || self.state.settings_anchor != self.input.raw["settings"]["anchor"]
        {
            return Err(Stop::invalid("StateSeed", "布局或设定锚点不符"));
        }
        let timeline = self.input.raw["timeline"]["events"]
            .as_array()
            .ok_or_else(|| Stop::invalid("timeline.events", "须为数组"))?;
        let event_time = |id: &str| -> Result<i64> {
            let event = timeline
                .iter()
                .find(|e| e["id"] == id)
                .ok_or_else(|| Stop::invalid(id, "状态锚点引用未知事件"))?;
            instant(&event["time"], id)
        };
        for moment in self.input.raw["construction"]["moments"]
            .as_array()
            .unwrap()
        {
            let id = moment["event"].as_str().unwrap();
            if event_time(id)? > self.t {
                return Err(Stop::invalid(
                    "StateSeed.environment.time",
                    format!("种子早于单位建成：{id}"),
                ));
            }
        }
        for anchor in [
            &self.input.raw["layout"]["anchor"],
            &self.state.settings_anchor,
        ] {
            if event_time(anchor["event"].as_str().unwrap())? > self.t {
                return Err(Stop::invalid(
                    "StateSeed.environment.time",
                    "种子早于布局/设定锚点",
                ));
            }
        }
        if self.state.environment.stage == "zero_intervention"
            && event_time(
                self.input.raw["environment"]["debug_end_event"]
                    .as_str()
                    .unwrap_or(""),
            )? > self.t
        {
            return Err(Stop::invalid(
                "StateSeed.environment.stage",
                "零干预种子早于调试结束",
            ));
        }
        let withdrawal = self
            .state
            .environment
            .withdrawal_memory
            .resolved("withdrawal_memory", false)?;
        fields(withdrawal, "once_fired pending_rules", "withdrawal_memory")?;
        if !withdrawal["once_fired"].is_array() || !withdrawal["pending_rules"].is_array() {
            return Err(Stop::invalid("withdrawal_memory", "策略记忆须为数组"));
        }
        if withdrawal["pending_rules"] != json!([]) {
            return Err(Stop::unsupported(
                "warehouse.withdrawal_policy",
                "withdrawal_memory.pending_rules",
                "待响应拿取策略不在支持域",
            ));
        }
        if !self.state.environment.online {
            return Err(Stop::unsupported(
                "offline.events",
                "seed.environment.online",
                "离线种子未支持",
            ));
        }
        if !["building", "debug", "zero_intervention"]
            .contains(&self.state.environment.stage.as_str())
        {
            return Err(Stop::invalid("environment.stage", "非法阶段"));
        }
        self.validate_inventory()?;self.warehouse_targets()?;
        for p in &self.state.progress {
            let kind=&self.input.geometry.units[&p.unit].kind;
            if kind=="协议储存箱" {
                let n=p.cooldown.as_ref().ok_or_else(||Stop::invalid(&p.unit,"箱缺冷却"))?.integer(&p.unit)?;
                if p.phase!="idle" || p.recipe.is_some() || p.remaining.is_some() || !(0..=self.input.catalog.kinds[kind].cooldown).contains(&n){return Err(Stop::invalid(&p.unit,"箱进度非法"));}
                continue;
            }
            if p.cooldown.is_some(){return Err(Stop::invalid(&p.unit,"制造不带冷却"));}
            let buffer=format!("{}:buffer:0",p.unit);let rows=&self.state.inventory[self.inv[&buffer]].contents;
            if p.phase=="idle" {if p.recipe.is_some() || p.remaining.is_some() || !rows.is_empty(){return Err(Stop::invalid(&p.unit,"idle 不得带配方、剩余或缓存"));}continue;}
            if !["working","completed"].contains(&p.phase.as_str()){return Err(Stop::invalid(&p.unit,"非法制造阶段"));}
            let r=p.recipe.as_ref().and_then(|r|self.input.catalog.recipes.get(r)).ok_or_else(||Stop::invalid(&p.unit,"缺配方"))?;
            if r.kind!=*kind{return Err(Stop::invalid(&p.unit,"配方机型不符"));}
            if p.phase=="working" {let n=p.remaining.as_ref().ok_or_else(||Stop::invalid(&p.unit,"缺剩余"))?.integer(&p.unit)?;if n<1 || n>r.duration{return Err(Stop::invalid(&p.unit,"制造剩余越界"));}}
            else if p.remaining.is_some(){return Err(Stop::invalid(&p.unit,"完成批不带剩余"));}
            let got:BTreeMap<_,_>=rows.iter().map(|c|Ok((c.item.clone(),c.quantity.integer(&buffer)?))).collect::<Result<_>>()?;
            let expected=if p.phase=="working"{&r.inputs}else{&r.outputs};
            if &got!=expected{return Err(Stop::invalid(&p.unit,"缓存不是恰好一批原料或产物"));}
        }
        for g in &self.state.logistics.gate_counters {
            let total=g.total_received.integer(&g.unit)?;let window=g.window_received.integer(&g.unit)?;let settings=&self.input.gate_settings[&g.unit];
            if total<0 || window<0 || window>total || (!settings["window_limit"].is_null() && window>num(&settings["window_limit"],"window_limit")?){return Err(Stop::invalid(&g.unit,"计数与设定不相容"));}
            if let Some(t)=&g.window_started_at {let w=t.integer(&g.unit)?;if w>self.t || self.t>=add(w,self.input.catalog.kinds["物品准入口"].window,&g.unit)? || window==0{return Err(Stop::invalid(&g.unit,"窗口未规范化或起点非法"));}}
            else if window!=0{return Err(Stop::invalid(&g.unit,"未开窗有计数"));}
        }
        let poll=&self.state.logistics.poll_state;
        if poll.schema!="poll-state-v1"{return Err(Stop::invalid("poll_state","未知版本"));}
        let sides=self.input.graph.cursor_sides();
        let labels:Vec<_>=poll.cursors.iter().map(|c|c.side.clone()).collect();
        if labels!=sides.keys().cloned().collect::<Vec<_>>(){return Err(Stop::invalid("poll_state.cursors","侧集合须不重不漏按标签排序"));}
        for c in &poll.cursors {if c.last_success.as_ref().is_some_and(|ch|!sides[&c.side].contains(ch)){return Err(Stop::invalid(&c.side,"成功通道不属于侧"));}}
        let expected:Vec<_>=self.input.graph.outputs_nt.iter().filter(|(_,c)|c.len()>1).map(|(u,_)|u.clone()).collect();
        if poll.recency.iter().map(|r|r.unit.clone()).collect::<Vec<_>>()!=expected{return Err(Stop::invalid("poll_state.recency","单位集合须不重不漏按标签排序"));}
        for r in &poll.recency {let set:BTreeSet<_>=r.order.iter().collect();if set.len()!=r.order.len() || r.order.iter().any(|c|!self.input.graph.outputs_nt[&r.unit].contains(c)){return Err(Stop::invalid(&r.unit,"recency 含重复或异属通道"));}}
        self.check_ore_availability()?;
        Ok(())
    }
    pub fn validate_inventory(&self) -> Result<()> {
        let mut occupied = BTreeSet::new();
        for row in &self.state.inventory {
            let mut sum = 0;
            let mut items = BTreeSet::new();
            let mut parts = row.slot.split(':');
            let uid = parts.next().unwrap_or("");
            let role = parts.next().unwrap_or("");
            let unit = self
                .input
                .geometry
                .units
                .get(uid)
                .ok_or_else(|| Stop::invalid(&row.slot, "未知单位格"))?;
            let kind = &self.input.catalog.kinds[&unit.kind];
            for c in &row.contents {
                let n = c.quantity.integer(&row.slot)?;
                if n <= 0 || c.item.is_empty() {
                    return Err(Stop::invalid(&row.slot, "库存数量/物种非法"));
                }
                if let Some(previous) = &c.last_unit {
                    let connected = self.input.geometry.channels.values().any(|channel| {
                        let from = &self.input.geometry.ports[&channel.source_port];
                        let to = &self.input.geometry.ports[&channel.target_port];
                        from.unit == *previous && to.unit == uid && to.axis.as_deref() == Some(role)
                    });
                    if unit.kind != "桥接器" || !connected {
                        return Err(Stop::invalid(&row.slot, "桥物品来路不是本轴相邻单位"));
                    }
                }
                if kind.family != "transport" && c.entered_at.is_some() {return Err(Stop::invalid(&row.slot,"非运输物品不带入格时刻"));}
                if !items.insert(c.item.as_str()) {return Err(Stop::invalid(&row.slot,"同物种须合并"));}
                sum = add(sum, n, &row.slot)?;
                if let Some(t) = &c.entered_at {
                    if t.integer(&row.slot)? > self.t {
                        return Err(Stop::invalid(&row.slot, "入格时刻在未来"));
                    }
                } else if kind.family == "transport" {
                    return Err(Stop::invalid(&row.slot, "运输格缺滞留起点"));
                }
            }
            if role != "buffer" && items.len() > 1 {
                return Err(Stop::invalid(&row.slot, "普通格不能混种"));
            }
            for item in items {
                if role != "buffer" && kind.same_item_unique && !occupied.insert((uid, item)) {
                    return Err(Stop::invalid(&row.slot, "同单位同种跨普通格"));
                }
            }
            if let Some(cap) = self.caps.get(&row.slot).and_then(|c| *c) {
                if sum > cap {
                    return Err(Stop::invalid(&row.slot, "超格容量"));
                }
            }
        }
        Ok(())
    }
    /// 受限转移§2.1、§4.2–§4.3：供电几何与输入开关的合取。
    pub(crate) fn enabled(&self, unit: &str, function: &str) -> bool {
        self.input.geometry.powered.contains(unit)
            && self.input.switches.get(&(unit.into(), function.into())) == Some(&true)
    }
    /// 受限转移§4.1：端口源选择；箱取最小编号非空格，不跳过拒收物种。
    pub(crate) fn source(&self, port: &str) -> Result<Option<(String, Content)>> {
        let p = &self.input.geometry.ports[port];
        let u = &self.input.geometry.units[&p.unit];
        let family = &self.input.catalog.kinds[&u.kind].family;
        if let Some(slot) = self.input.assignments.get(port) {
            let r = &self.state.warehouse.slots[self.warehouse[slot]];
            return Ok(r.item.as_ref().map(|item| {
                (
                    slot.clone(),
                    Content {
                        item: item.clone(),
                        quantity: r.quantity.clone(),
                        entered_at: None,
                        last_unit: None,
                    },
                )
            }));
        }
        let role = if u.kind == "桥接器" {
            p.axis
                .as_deref()
                .ok_or_else(|| Stop::invalid(port, "桥口缺轴"))?
        } else if family == "transport" {
            "transport"
        } else if u.kind == "协议储存箱" {
            "storage"
        } else {
            "output"
        };
        let slots = self
            .slot_groups
            .get(&(p.unit.clone(), role.into()))
            .map(Vec::as_slice)
            .unwrap_or(&[]);
        for slot in slots {
            if let Some(c) = self.state.inventory[self.inv[slot]].contents.first() {
                return Ok(Some((slot.clone(), c.clone())));
            }
        }
        Ok(None)
    }
    /// 受限转移§4.1：查同种普通格，再按显式制造顺序/箱编号选合法目标。
    pub(crate) fn target(&self, port: &str, item: &str) -> Result<Option<String>> {
        let p = &self.input.geometry.ports[port];
        let u = &self.input.geometry.units[&p.unit];
        let kind = &self.input.catalog.kinds[&u.kind];
        if kind.family == "core" {
            return Ok(self
                .plan_deposit(&BTreeMap::from([(item.into(), 1)]), false)?
                .map(|p| p[0].slot.clone()));
        }
        let role = if u.kind == "桥接器" {
            p.axis
                .as_deref()
                .ok_or_else(|| Stop::invalid(port, "桥口缺轴"))?
        } else if kind.family == "transport" {
            "transport"
        } else if u.kind == "协议储存箱" {
            "storage"
        } else {
            "input"
        };
        let slots = self
            .slot_groups
            .get(&(p.unit.clone(), role.into()))
            .cloned()
            .unwrap_or_default();
        if kind.same_item_unique {
            let same = self.unit_inventory[&p.unit]
                .iter()
                .map(|i| &self.state.inventory[*i])
                .find(|s| {
                    !s.slot.contains(":buffer:") && s.contents.iter().any(|c| c.item == item)
                });
            if let Some(s) = same {
                if !slots.contains(&s.slot) {
                    return Ok(None);
                }
                return Ok(Some(s.slot.clone()));
            }
        }
        if role == "storage" {
            for slot in slots {
                let rows = &self.state.inventory[self.inv[&slot]].contents;
                let n = rows
                    .iter()
                    .try_fold(0, |n, c| add(n, c.quantity.integer(&slot)?, &slot))?;
                if rows.is_empty() || (rows[0].item == item && n < self.caps[&slot].unwrap()) {
                    return Ok(Some(slot));
                }
            }
            return Ok(None);
        }
        if kind.family == "transport" {
            return Ok(slots.first().cloned());
        }
        Ok(slots
            .into_iter()
            .find(|s| self.state.inventory[self.inv[s]].contents.is_empty()))
    }
    pub(crate) fn remove(&mut self, slot: &str, item: &str, count: i64) -> Result<()> {
        if let Some(i) = self.warehouse.get(slot).copied() {
            let r = &mut self.state.warehouse.slots[i];
            let n = r.quantity.integer(slot)?;
            if r.item.as_deref() != Some(item) || n < count {
                return Err(Stop::invalid(slot, "源库存不足"));
            }
            r.quantity = Quantity::calc(n - count);
            if n == count {
                r.item = None;
                r.empty_identity =
                    Decision::specified(json!(item), "受限转移定义 §4.1：清空保留历史身份");
            }
            return Ok(());
        }
        let i = self.inv[slot];
        let rows = &mut self.state.inventory[i].contents;
        let n = rows
            .iter()
            .filter(|c| c.item == item)
            .try_fold(0, |n, c| add(n, c.quantity.integer(slot)?, slot))?;
        if n < count {
            return Err(Stop::invalid(slot, "源库存不足"));
        }
        // 转移§4.2：整批可跨年龄组扣料；同种非运输货按规范记录序扣减，不引入物种优先级。
        let mut left = count;
        for c in rows.iter_mut().filter(|c| c.item == item) {
            if left == 0 {
                break;
            }
            let n = c.quantity.integer(slot)?;
            let taken = n.min(left);
            c.quantity = Quantity::calc(n - taken);
            left -= taken;
        }
        rows.retain(|c| c.quantity.value != "0");
        Ok(())
    }
    /// 受限转移§4.1–§4.2：缓存允许多物种；put提交前再次核普通格单物种及目录容量，失败不写入。
    pub(crate) fn put(&mut self, slot: &str, item: &str, count: i64) -> Result<()> {
        let index = *self
            .inv
            .get(slot)
            .ok_or_else(|| Stop::invalid(slot, "put目标不是已登记本地格"))?;
        let contents = &self.state.inventory[index].contents;
        if count <= 0 {
            return Err(Stop::invalid(slot, "put数量须正"));
        }
        let buffer = slot.split(':').nth(1) == Some("buffer");
        if !buffer && contents.iter().any(|c| c.item != item) {
            return Err(Stop::invalid(
                slot,
                format!("put违反同格单物种：拟存{item}"),
            ));
        }
        if self.caps[slot].is_some_and(|capacity| count > capacity) {
            return Err(Stop::invalid(slot, "put单次入量已经超过目录容量"));
        }
        let total = contents
            .iter()
            .try_fold(count, |n, c| add(n, c.quantity.integer(slot)?, slot))?;
        if self.caps[slot].is_some_and(|capacity| total > capacity) {
            return Err(Stop::invalid(
                slot,
                format!("put超过格容量：拟提交总量{total}"),
            ));
        }
        let uid=slot.split(':').next().unwrap();
        let transport=self.input.catalog.kinds[&self.input.geometry.units[uid].kind].family=="transport";
        let rows=&mut self.state.inventory[index].contents;
        if let Some(c)=rows.iter_mut().find(|c|c.item==item) {c.quantity=Quantity::calc(add(c.quantity.integer(slot)?,count,slot)?);}
        else {rows.push(Content{item:item.into(),quantity:Quantity::calc(count),entered_at:transport.then(||Time::at(self.t)),last_unit:None});rows.sort_by(|a,b|a.item.cmp(&b.item));}
        Ok(())
    }
    pub fn observe(&self,report:&StepReport)->Value {
        let mut transport=serde_json::Map::new();let mut stock=serde_json::Map::new();
        for row in &self.state.inventory {if row.contents.is_empty(){continue;}if self.input.graph.slot_component.contains_key(&row.slot){let c=&row.contents[0];let age=i128::from(report.step)+1-i128::from(c.entered_at.as_ref().unwrap().integer(&row.slot).unwrap());transport.insert(row.slot.clone(),json!([c.item,age]));}else{let items:BTreeMap<_,_>=row.contents.iter().map(|c|(c.item.clone(),c.quantity.integer(&row.slot).unwrap())).collect();stock.insert(row.slot.clone(),json!(items));}}
        let mut machines=serde_json::Map::new();let mut boxes=serde_json::Map::new();
        for p in &self.state.progress {if let Some(c)=&p.cooldown{boxes.insert(p.unit.clone(),json!(c.integer(&p.unit).unwrap()));}else{machines.insert(p.unit.clone(),json!([p.phase,p.remaining.as_ref().map(|t|t.integer(&p.unit).unwrap())]));}}
        let warehouse:BTreeMap<_,_>=self.state.warehouse.slots.iter().filter_map(|r|r.item.as_ref().map(|i|(i.clone(),r.quantity.integer(&r.slot).unwrap()))).collect();
        let moves:Vec<_>=report.events.iter().flat_map(|e|&e.moves).map(|m|json!([self.input.graph.label(&self.input.graph.sender[&m.channel]),self.input.graph.label(&self.input.graph.receiver[&m.channel]),m.item])).collect();
        json!({"step":report.step,"moves":moves,"transport":transport,"stock":stock,"machines":machines,"boxes":boxes,"warehouse":warehouse})
    }
}
