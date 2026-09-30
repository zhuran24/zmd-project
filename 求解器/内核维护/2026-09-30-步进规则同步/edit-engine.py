from work import *
S=OUT/'staging/crates/kernel/src'
s=(ROOT/'crates/kernel/src/model.rs').read_text()
base=s[:s.index('#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]\n#[serde(deny_unknown_fields)]\npub struct Cooldown')]
new='''pub struct Progress { pub unit: String, pub phase: String, pub recipe: Option<String>, pub remaining: Option<Time>, pub cooldown: Option<Time> }
---
pub struct Cursor { pub side: String, pub last_success: Option<String> }
---
pub struct Recency { pub unit: String, pub order: Vec<String> }
---
pub struct PollState { pub schema: String, pub cursors: Vec<Cursor>, pub recency: Vec<Recency> }
---
pub struct Gate { pub unit: String, pub total_received: Quantity, pub window_received: Quantity, pub window_started_at: Option<Time> }
---
pub struct Logistics { pub poll_state: PollState, pub gate_counters: Vec<Gate> }
---
pub struct Environment { pub time: Time, pub stage: String, pub online: bool, pub withdrawal_memory: Decision }
---
pub struct SemanticContext { pub warehouse_empty_slot_order: Vec<String> }
---
pub struct State { pub layout_snapshot: String, pub settings_anchor: Value, pub warehouse: Warehouse, pub inventory: Vec<Inventory>, pub progress: Vec<Progress>, pub logistics: Logistics, pub environment: Environment, pub semantic_context: SemanticContext }
---
pub struct Move { pub channel: String, pub item: String }
---
pub struct Event { pub event: String, pub phase: String, pub subject: String, pub moves: Vec<Move>, pub detail: Option<Value> }
---
pub struct StepReport { pub step: i64, pub events: Vec<Event>, pub ledger: Value }
'''
base+=''.join('#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]\n#[serde(deny_unknown_fields)]\n'+r.strip()+'\n' for r in new.split('---'))
(S/'model.rs').write_text(base)
old=(ROOT/'crates/kernel/src/engine.rs').read_text()
base='''//! 整数步边界状态、严格装载及库存事务。
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
'''
a=old.index('        if self.state.layout_snapshot');b=old.index('        for event in timeline {',a);base+=old[a:b]
a=old.index('        let withdrawal =',b);b=old.index('        if self.inv.len()',a);base+=old[a:b]
base+='''        self.validate_inventory()?;self.warehouse_targets()?;
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
'''
a=old.index('    pub fn validate_inventory');b=old.index('    /// 受限转移§3.1：物理可动',a)
methods=old[a:b].replace('                items.insert(c.item.as_str());','''                if kind.family != "transport" && c.entered_at.is_some() {return Err(Stop::invalid(&row.slot,"非运输物品不带入格时刻"));}
                if !items.insert(c.item.as_str()) {return Err(Stop::invalid(&row.slot,"同物种须合并"));}''')
base+=methods
a=old.index('    pub(crate) fn remove');b=old.index('    /// 内核输入§3.1、内核输出§2',a)
methods=old[a:b].replace('        self.invalidate_slot(slot);\n','')
a=methods.index('        let rows = &mut self.state.inventory[index].contents;')
methods=methods[:a]+'''        let uid=slot.split(':').next().unwrap();
        let transport=self.input.catalog.kinds[&self.input.geometry.units[uid].kind].family=="transport";
        let rows=&mut self.state.inventory[index].contents;
        if let Some(c)=rows.iter_mut().find(|c|c.item==item) {c.quantity=Quantity::calc(add(c.quantity.integer(slot)?,count,slot)?);}
        else {rows.push(Content{item:item.into(),quantity:Quantity::calc(count),entered_at:transport.then(||Time::at(self.t)),last_unit:None});rows.sort_by(|a,b|a.item.cmp(&b.item));}
        Ok(())
    }
'''
base+=methods
base+='''    pub fn observe(&self,report:&StepReport)->Value {
        let mut transport=serde_json::Map::new();let mut stock=serde_json::Map::new();
        for row in &self.state.inventory {if row.contents.is_empty(){continue;}if self.input.graph.slot_component.contains_key(&row.slot){let c=&row.contents[0];let age=i128::from(report.step)+1-i128::from(c.entered_at.as_ref().unwrap().integer(&row.slot).unwrap());transport.insert(row.slot.clone(),json!([c.item,age]));}else{let items:BTreeMap<_,_>=row.contents.iter().map(|c|(c.item.clone(),c.quantity.integer(&row.slot).unwrap())).collect();stock.insert(row.slot.clone(),json!(items));}}
        let mut machines=serde_json::Map::new();let mut boxes=serde_json::Map::new();
        for p in &self.state.progress {if let Some(c)=&p.cooldown{boxes.insert(p.unit.clone(),json!(c.integer(&p.unit).unwrap()));}else{machines.insert(p.unit.clone(),json!([p.phase,p.remaining.as_ref().map(|t|t.integer(&p.unit).unwrap())]));}}
        let warehouse:BTreeMap<_,_>=self.state.warehouse.slots.iter().filter_map(|r|r.item.as_ref().map(|i|(i.clone(),r.quantity.integer(&r.slot).unwrap()))).collect();
        let moves:Vec<_>=report.events.iter().flat_map(|e|&e.moves).map(|m|json!([self.input.graph.label(&self.input.graph.sender[&m.channel]),self.input.graph.label(&self.input.graph.receiver[&m.channel]),m.item])).collect();
        json!({"step":report.step,"moves":moves,"transport":transport,"stock":stock,"machines":machines,"boxes":boxes,"warehouse":warehouse})
    }
}
'''
(S/'engine.rs').write_text(base)
s=(ROOT/'crates/kernel/src/warehouse.rs').read_text().replace('            .active\n            .iter()','            .input.geometry.channels\n            .keys()').replace('"phase":"after_closure",','').replace('                .arbitration\n','').replace('            .arbitration\n','').replace('arbitration.warehouse_empty_slot_order','semantic_context.warehouse_empty_slot_order').replace('        self.invalidate_unit("@warehouse");\n','').replace('self.state.progress[i].cooldowns[0].remaining','self.state.progress[i].cooldown.as_ref().unwrap()')
s=s.replace('self.state.progress[i].cooldown.as_ref().unwrap() =\n            Time::at(self.input.catalog.kinds[&self.input.geometry.units[uid].kind].cooldown);','self.state.progress[i].cooldown =\n            Some(Time::at(self.input.catalog.kinds[&self.input.geometry.units[uid].kind].cooldown));')
s=s.replace('规则L36','规则L37').replace('规则L72','规则L73')
(S/'warehouse.rs').write_text(s)
