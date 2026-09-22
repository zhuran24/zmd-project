//! 受限转移§2–§5：整数时钟、库存、判定模板及闭包归约。
use crate::{config::Axis, input::*, model::*, value::*};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
#[derive(Clone, Debug)]
pub(crate) struct Route {
    pub source: String,
    pub target: String,
    pub item: String,
}
#[derive(Clone, Debug)]
pub(crate) struct Deposit {
    pub slot: String,
    pub item: String,
    pub count: i64,
    pub create: bool,
}
#[derive(Debug)]
pub struct Engine {
    pub(crate) gate_channels: Vec<String>,
    pub(crate) core_inbound_channels: Vec<String>,
    pub(crate) arbitration_rank: BTreeMap<String, usize>,
    pub(crate) level_keys: std::cell::RefCell<BTreeMap<String, (i64, i64)>>,
    pub(crate) damping_used: std::cell::RefCell<BTreeSet<String>>,
    pub(crate) cache_enabled: bool,
    pub(crate) physical_cache: std::cell::RefCell<BTreeMap<String, crate::cache::PhysicalResult>>,
    pub(crate) dirty_sides: std::cell::RefCell<BTreeSet<usize>>,
    pub(crate) dependencies: BTreeMap<String, BTreeSet<String>>,
    pub(crate) slot_groups: BTreeMap<(String, String), Vec<String>>,
    pub(crate) unit_inventory: BTreeMap<String, Vec<usize>>,
    pub input: Input,
    pub state: State,
    pub memory: PollMemory,
    pub completed_batches: i64,
    pub ledger: Value,
    pub production_abstraction: bool,
    pub delivery: BTreeMap<String, i64>,
    pub supplied: BTreeMap<String, i64>,
    pub(crate) inv: BTreeMap<String, usize>,
    pub(crate) progress: BTreeMap<String, usize>,
    pub(crate) warehouse: BTreeMap<String, usize>,
    pub(crate) caps: BTreeMap<String, Option<i64>>,
    pub(crate) active: BTreeSet<String>,
    pub(crate) channel_order: Vec<String>,
    pub(crate) usage: BTreeMap<String, i64>,
    pub(crate) pending: Vec<Pending>,
    pub(crate) allocated: BTreeSet<String>,
    pub(crate) executed: BTreeSet<String>,
    pub(crate) side_index: BTreeMap<(String, String), usize>,
    pub(crate) gate_index: BTreeMap<String, usize>,
    pub(crate) t: i64,
    pub(crate) records: Vec<Event>,
    pub(crate) movements: Vec<Value>,
    pub(crate) passages: Vec<Value>,
    pub(crate) capture: bool,
    pub(crate) tie_sides: Vec<String>,
    pub(crate) first: bool,
    pub max_sweeps: usize,
    pub(crate) halted: Option<Stop>,
    pub(crate) active_event: Option<String>,
}
impl Engine {
    /// 受限转移§1、内核输入§6：完整种子无默认补库存；运行状态校验后才开始扫描。
    pub fn new(input: Input) -> Result<Self> {
        Self::construct(input, false, false)
    }
    /// 转移§6.1 D.2：生产装载在首次派生可动级前启用候选守卫。
    pub fn new_production(input: Input) -> Result<Self> {
        Self::construct(input, false, true)
    }
    /// 第五轮K1：仅种子命令启用派生，普通装载保持严格拒收。
    pub(crate) fn new_derived(input: Input) -> Result<Self> {
        Self::construct(input, true, false)
    }
    fn construct(input: Input, derive: bool, production: bool) -> Result<Self> {
        let mut engine = Self::prepare(input, derive, production)?;
        engine.validate_memory()?;
        Ok(engine)
    }
    /// 输出§5.1.1：候选失败时仍返回五项静态报告，未进行的级校验如实未决。
    pub fn check_cycle_domain(input: Input) -> Result<Value> {
        let mut engine = Self::prepare(input, false, true)?;
        let mut report = engine.domain_report("static");
        if let Err(stop) = engine.validate_memory() {
            report[3] = json!({"condition":"D.4","status":if stop.status=="invalid_input"{"fail"}else{"unresolved"},"scope":"static","locations":[stop.location],"evidence":[format!("轮询级装载未完成：{}",stop.reason)]});
        }
        Ok(report)
    }
    /// 转移§1：只核输入与原始状态；此阶段不计算目标容量或物理可动级。
    fn prepare(input: Input, derive: bool, production: bool) -> Result<Self> {
        let d: Decision = decode(
            input.raw["initial_state"]["nonwarehouse"].clone(),
            "initial_state.nonwarehouse",
        )?;
        let mut state: State = decode(
            d.resolved("initial_state.nonwarehouse", false)?.clone(),
            "StateSeed",
        )?;
        state.inventory.sort_by(|a, b| a.slot.cmp(&b.slot));
        // 转移§6.2：同种不同年龄是不同记录；无物理顺序的内容按物种、入格时刻规范化。
        for row in &mut state.inventory {
            let mut contents = Vec::new();
            for content in row.contents.drain(..) {
                let entered = content
                    .entered_at
                    .as_ref()
                    .map(|t| t.integer(&row.slot))
                    .transpose()?;
                contents.push(((content.item.clone(), entered), content));
            }
            contents.sort_by(|a, b| a.0.cmp(&b.0));
            row.contents = contents.into_iter().map(|(_, content)| content).collect();
        }
        let memory: PollMemory = decode(
            state
                .logistics
                .poll_memory
                .resolved("poll_memory", false)?
                .clone(),
            "poll_memory",
        )?;
        if memory.schema != "poll-memory-v1" {
            return Err(Stop::invalid("poll_memory.schema", "未知轮询记忆版本"));
        }
        let t = state.environment.time.integer("seed.time")?;
        let phase = state
            .semantic_context
            .judgment_context
            .resolved("judgment_context", false)?["phase"]
            .as_str()
            .unwrap_or("");
        if !["before_boundary", "after_closure"].contains(&phase) {
            return Err(Stop::unsupported(
                "initialization.other_inventory",
                "judgment_context.phase",
                "只从完整边界锚点续跑；中途 continuation 未执行",
            ));
        }
        let pending: Vec<Pending> = decode(
            state
                .semantic_context
                .pending_events
                .resolved("pending_events", false)?
                .clone(),
            "pending_events",
        )?;
        // 输入§6、转移§6.2：派生前也核封闭语法，不能先改写坏日程再放行。
        for p in &pending {
            fields(
                &p.trigger,
                "kind value",
                &format!("pending_events.{}.trigger", p.event),
            )?;
        }
        let caps = input.catalog.slots(
            &input.geometry.units,
            input
                .parameters
                .value(Axis::BridgeCapacity)?
                .as_i64()
                .ok_or_else(|| Stop::invalid("bridge.capacity", "须为整数"))?,
        )?;
        // 输入§2.3：先核目录给出的格身份和唯一性，才允许建寻址/分组索引。
        let mut slots = BTreeSet::new();
        for (index, row) in state.inventory.iter().enumerate() {
            if !caps.contains_key(&row.slot) || !slots.insert(row.slot.clone()) {
                return Err(Stop::invalid(
                    format!("StateSeed.inventory[{index}].slot"),
                    format!("未知或重复的目录格身份：{}", row.slot),
                ));
            }
        }
        if slots.len() != caps.len() {
            return Err(Stop::invalid("StateSeed.inventory", "缺少目录格"));
        }
        permutation(
            &state
                .progress
                .iter()
                .map(|p| p.unit.clone())
                .collect::<Vec<_>>(),
            input
                .geometry
                .units
                .iter()
                .filter(|(_, u)| !input.catalog.kinds[&u.kind].functions.is_empty())
                .map(|(id, _)| id.clone()),
            "StateSeed.progress",
        )?;
        permutation(
            &state
                .logistics
                .gate_counters
                .iter()
                .map(|g| g.unit.clone())
                .collect::<Vec<_>>(),
            input.gate_settings.keys().cloned(),
            "StateSeed.logistics.gate_counters",
        )?;
        let warehouse_slots: BTreeSet<_> = state.warehouse.slots.iter().map(|r| &r.slot).collect();
        if warehouse_slots.len() != state.warehouse.slots.len() {
            return Err(Stop::invalid("StateSeed.warehouse.slots", "仓库格标签重复"));
        }
        for slot in input.assignments.values() {
            if !warehouse_slots.contains(slot) {
                return Err(Stop::invalid(slot, "取货指派不存在的格"));
            }
        }
        let inv = state
            .inventory
            .iter()
            .enumerate()
            .map(|(i, r)| (r.slot.clone(), i))
            .collect::<BTreeMap<_, _>>();
        let progress = state
            .progress
            .iter()
            .enumerate()
            .map(|(i, p)| (p.unit.clone(), i))
            .collect::<BTreeMap<_, _>>();
        let warehouse = state
            .warehouse
            .slots
            .iter()
            .enumerate()
            .map(|(i, r)| (r.slot.clone(), i))
            .collect::<BTreeMap<_, _>>();
        let active = state.logistics.active_channels.iter().cloned().collect();
        // 内核输入§6.3：无物理意义的输出排列以种子和显式接通序为稳定标签序。
        let channel_order = input.tie_order.clone();
        let side_index = memory
            .sides
            .iter()
            .enumerate()
            .map(|(i, s)| ((s.unit.clone(), s.side.clone()), i))
            .collect::<BTreeMap<_, _>>();
        let gate_index = state
            .logistics
            .gate_counters
            .iter()
            .enumerate()
            .map(|(i, g)| (g.unit.clone(), i))
            .collect::<BTreeMap<_, _>>();
        let executed = crate::event_identity::seed_executed(&input, &json!(state))?;
        let allocated = input.raw["timeline"]["events"]
            .as_array()
            .unwrap()
            .iter()
            .map(|e| e["id"].as_str().unwrap().to_string())
            .chain(pending.iter().map(|p| p.event.clone()))
            .chain(executed.iter().cloned())
            .collect();
        let mut slot_groups = BTreeMap::<(String, String), Vec<String>>::new();
        let mut unit_inventory = BTreeMap::<String, Vec<usize>>::new();
        for (slot, index) in &inv {
            let parts: Vec<_> = slot.split(':').collect();
            slot_groups
                .entry((parts[0].into(), parts[1].into()))
                .or_default()
                .push(slot.clone());
            unit_inventory
                .entry(parts[0].into())
                .or_default()
                .push(*index);
        }
        for ((_, role), slots) in &mut slot_groups {
            if role == "input" {
                slots.sort_by_key(|s| {
                    input
                        .slot_order
                        .iter()
                        .position(|p| p == s)
                        .unwrap_or(usize::MAX)
                });
            } else {
                slots.sort_by_key(|s| {
                    s.rsplit(':')
                        .next()
                        .unwrap()
                        .parse::<usize>()
                        .unwrap_or(usize::MAX)
                });
            }
        }
        let gate_channels = input
            .geometry
            .channels
            .iter()
            .filter(|(_, c)| {
                input
                    .gate_settings
                    .contains_key(&input.geometry.ports[&c.target_port].unit)
            })
            .map(|(id, _)| id.clone())
            .collect();
        let core_inbound_channels = input
            .geometry
            .channels
            .iter()
            .filter(|(_, c)| {
                input.geometry.units[&input.geometry.ports[&c.target_port].unit].kind == "协议核心"
            })
            .map(|(id, _)| id.clone())
            .collect();
        let arbitration_rank = state
            .semantic_context
            .arbitration
            .level_order
            .iter()
            .enumerate()
            .map(|(i, s)| (s.clone(), i))
            .collect();
        let mut e = Self {
            gate_channels,
            core_inbound_channels,
            arbitration_rank,
            level_keys: Default::default(),
            damping_used: Default::default(),
            cache_enabled: false,
            physical_cache: Default::default(),
            dirty_sides: Default::default(),
            dependencies: Default::default(),
            slot_groups,
            unit_inventory,
            input,
            state,
            memory,
            completed_batches: 0,
            ledger: crate::ledger::empty_ledger(),
            production_abstraction: production,
            delivery: BTreeMap::new(),
            supplied: BTreeMap::new(),
            inv,
            progress,
            warehouse,
            caps,
            active,
            channel_order,
            usage: BTreeMap::new(),
            pending,
            allocated,
            executed,
            side_index,
            gate_index,
            t,
            records: vec![],
            movements: vec![],
            passages: vec![],
            capture: true,
            tie_sides: vec![],
            first: true,
            max_sweeps: 100_000,
            halted: None,
            active_event: None,
        };
        // 种子派生会读取真实库存和仓库；这些原始量必须先于派生图及physical校验。
        e.validate_inventory()?;
        e.warehouse_targets()?;
        if e.sufficient() {
            e.check_ore_availability()?;
        }
        e.build_dependencies();
        if derive {
            e.derive_context()?;
        }
        e.validate_seed()?;
        crate::event_identity::validate_event_identity(&e.input, &json!(e.state), &[])?;
        Ok(e)
    }
    fn validate_memory(&mut self) -> Result<()> {
        let before = self.memory.clone();
        self.rebuild_memory()?;
        if self.memory != before {
            return Err(Stop::invalid(
                "poll_memory",
                "成员、接通环、级或当前可动级不符",
            ));
        }
        Ok(())
    }
    /// 内核输入§6、受限转移§1：容量、批次原料账、参数、锚点与待事件联合核验。
    fn validate_seed(&mut self) -> Result<()> {
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
        for event in timeline {
            let id = event["id"].as_str().unwrap();
            if event["kind"] == "runtime"
                && ["I|", "J|", "C|", "W|"]
                    .iter()
                    .any(|prefix| id.starts_with(prefix))
                && !self.pending.iter().any(|p| p.event == id)
            {
                let at = event_time(id)?;
                if at > self.t
                    || (at == self.t
                        && self.state.semantic_context.judgment_context.value["phase"]
                            == "before_boundary")
                {
                    return Err(Stop::invalid(
                        id,
                        "未来运行身份未由种子待事件登记，不能占用生成式",
                    ));
                }
            }
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
        if self.inv.len() != self.state.inventory.len() || self.caps.keys().ne(self.inv.keys()) {
            return Err(Stop::invalid("inventory", "格标签缺失/重复/多余"));
        }
        if self.progress.len() != self.state.progress.len() {
            return Err(Stop::invalid("progress", "进度重复"));
        }
        let expected: Vec<String> = self
            .input
            .geometry
            .units
            .iter()
            .filter(|(_, u)| !self.input.catalog.kinds[&u.kind].functions.is_empty())
            .map(|(id, _)| id.clone())
            .collect();
        permutation(
            &self.progress.keys().cloned().collect::<Vec<_>>(),
            expected,
            "progress",
        )?;
        if self.warehouse.len() != self.state.warehouse.slots.len() {
            return Err(Stop::invalid("warehouse", "格标签重复"));
        }
        self.validate_inventory()?;
        self.warehouse_targets()?;
        for (slot, _) in self.input.assignments.iter().map(|(p, s)| (s, p)) {
            if !self.warehouse.contains_key(slot) {
                return Err(Stop::invalid(slot, "取货指派不存在的格"));
            }
        }
        let current = self.input.parameters.current();
        let mut actual = BTreeMap::new();
        for p in &self.state.semantic_context.parameter_values {
            if actual
                .insert(p.axis.clone(), (json!(p.value), p.lifetime.clone()))
                .is_some()
            {
                return Err(Stop::invalid(&p.axis, "当前轴重复"));
            }
        }
        if current != actual {
            return Err(Stop::invalid(
                "parameter_values",
                "当前值/生命周期与参数向量不符",
            ));
        }
        self.state
            .logistics
            .connection_order
            .resolved("connection_order", false)?;
        if self.state.logistics.connection_order.value != "timeline_connection_history" {
            return Err(Stop::unsupported(
                "connection.order",
                "logistics.connection_order",
                "未实现的接续历史",
            ));
        }
        if self.gate_index.len() != self.state.logistics.gate_counters.len() {
            return Err(Stop::invalid("gate_counters", "准入口重复"));
        }
        permutation(
            &self.gate_index.keys().cloned().collect::<Vec<_>>(),
            self.input.gate_settings.keys().cloned(),
            "gate_counters",
        )?;
        for g in &self.state.logistics.gate_counters {
            let total = g.total_received.integer(&g.unit)?;
            let window = g.window_received.integer(&g.unit)?;
            let settings = &self.input.gate_settings[&g.unit];
            if total < 0 || window < 0 || window > total {
                return Err(Stop::invalid(&g.unit, "门控计数非法"));
            }
            let reasons: BTreeSet<_> = g.blocked_reasons.iter().map(String::as_str).collect();
            if reasons.len() != g.blocked_reasons.len()
                || reasons.iter().any(|r| {
                    !["identity_mismatch", "total_exhausted", "window_exhausted"].contains(r)
                })
            {
                return Err(Stop::invalid(&g.unit, "阻断原因非法"));
            }
            for (field, reason, count) in [
                ("total_limit", "total_exhausted", total),
                ("window_limit", "window_exhausted", window),
            ] {
                if !settings[field].is_null() {
                    let limit = num(&settings[field], field)?;
                    // 规则L22、L64：调低累计阈值后的真实n可大于C，仍为耗尽。
                    if (field == "window_limit" && count > limit)
                        || (count >= limit) != reasons.contains(reason)
                    {
                        return Err(Stop::invalid(&g.unit, "计数/限额与原因不相容"));
                    }
                } else if reasons.contains(reason) {
                    return Err(Stop::invalid(&g.unit, "未设限额却标耗尽"));
                }
            }
            if let Some(at) = &g.window_started_at {
                if at.integer(&g.unit)? > self.t || window == 0 {
                    return Err(Stop::invalid(&g.unit, "窗口起点/计数非法"));
                }
            } else if window != 0 {
                return Err(Stop::invalid(&g.unit, "未开窗有计数"));
            }
        }
        let blocked: BTreeSet<_> = self
            .input
            .geometry
            .channels
            .values()
            .filter(|c| {
                self.gate_index
                    .get(&self.input.geometry.ports[&c.target_port].unit)
                    .is_some_and(|i| {
                        !self.state.logistics.gate_counters[*i]
                            .blocked_reasons
                            .is_empty()
                    })
            })
            .map(|c| c.id.clone())
            .collect();
        let expected_active: BTreeSet<_> = self
            .input
            .geometry
            .channels
            .keys()
            .filter(|c| !blocked.contains(*c))
            .cloned()
            .collect();
        if self.active != expected_active
            || self.active.len() != self.state.logistics.active_channels.len()
            || blocked
                != self
                    .state
                    .logistics
                    .blocked_channels
                    .iter()
                    .cloned()
                    .collect()
            || blocked.len() != self.state.logistics.blocked_channels.len()
        {
            return Err(Stop::invalid(
                "logistics.active_channels",
                "实际边与门控原因不符",
            ));
        }
        let expected_sides: BTreeSet<_> = self
            .input
            .geometry
            .units
            .iter()
            .filter(|(_, u)| self.input.catalog.kinds[&u.kind].family != "power")
            .flat_map(|(u, _)| [(u.clone(), "input".into()), (u.clone(), "output".into())])
            .collect();
        if expected_sides != self.side_index.keys().cloned().collect()
            || self.memory.sides.len() != expected_sides.len()
        {
            return Err(Stop::invalid("poll_memory.sides", "单位侧缺失/重复"));
        }
        for s in &self.memory.sides {
            for l in &s.levels {
                if !l.members.contains(&l.next_channel) {
                    return Err(Stop::invalid(&l.id, "游标不在本级"));
                }
            }
        }
        let phase = self.state.semantic_context.judgment_context.value["phase"]
            .as_str()
            .unwrap_or("");
        let tc = self
            .state
            .semantic_context
            .tick_context
            .resolved("tick_context", false)?;
        fields(
            tc,
            "window_start window_end movements port_usage internal_passages",
            "tick_context",
        )?;
        if instant(&tc["window_start"], "tick_context")? != self.t
            || instant(&tc["window_end"], "tick_context")? != add(self.t, 1, "time")?
        {
            return Err(Stop::invalid("tick_context", "窗口不等于种子时刻"));
        }
        let mut from_moves = BTreeMap::new();
        for m in tc["movements"]
            .as_array()
            .ok_or_else(|| Stop::invalid("movements", "须为数组"))?
        {
            let c = self
                .input
                .geometry
                .channels
                .get(m["channel"].as_str().unwrap_or(""))
                .ok_or_else(|| Stop::invalid("movements", "未知PC"))?;
            if num(&m["quantity"], "movements")? != 1 {
                return Err(Stop::invalid("movements", "单次移动必须一件"));
            }
            for p in [&c.source_port, &c.target_port] {
                let n = from_moves.entry(p.clone()).or_insert(0);
                *n += 1;
            }
        }
        for r in tc["port_usage"]
            .as_array()
            .ok_or_else(|| Stop::invalid("port_usage", "须为数组"))?
        {
            let p = r["port"].as_str().unwrap_or("");
            let n = num(&r["quantity"], p)?;
            if n < 1 || n > self.input.catalog.port_rate || self.usage.insert(p.into(), n).is_some()
            {
                return Err(Stop::invalid(p, "端口预算非法"));
            }
        }
        if self.usage != from_moves {
            return Err(Stop::invalid("port_usage", "与成功移动账不符"));
        }
        if phase == "before_boundary"
            && (!self.usage.is_empty()
                || tc["movements"] != json!([])
                || tc["internal_passages"] != json!([]))
        {
            return Err(Stop::invalid("tick_context", "边界前不可带本刻已执行记录"));
        }
        let context = self
            .state
            .semantic_context
            .judgment_context
            .resolved("judgment_context", false)?;
        fields(
            context,
            "instant phase order_scope round next_template ordered_events next_event",
            "judgment_context",
        )?;
        if instant(&context["instant"], "judgment_context.instant")? != self.t
            || context["order_scope"] != "global"
            || context["next_template"] != 0
            || context["ordered_events"] != json!([])
            || !context["next_event"].is_null()
        {
            return Err(Stop::invalid("judgment_context", "边界锚点的扫描位置不符"));
        }
        let mut expected_pending = BTreeSet::new();
        for p in &self.state.progress {
            let unit = &self.input.geometry.units[&p.unit];
            let is_box = unit.kind == "协议储存箱";
            if is_box {
                if p.phase != "idle"
                    || p.locked_recipe.is_some()
                    || !p.candidate_recipes.is_empty()
                    || p.recipe.is_some()
                    || p.remaining.is_some()
                    || p.cooldowns.len() != 1
                    || p.cooldowns[0].slot.is_some()
                {
                    return Err(Stop::invalid(&p.unit, "箱体进度结构错误"));
                }
                let n = p.cooldowns[0].remaining.integer(&p.unit)?;
                if n < 0 || n > self.input.catalog.kinds[&unit.kind].cooldown {
                    return Err(Stop::invalid(&p.unit, "箱冷却越界"));
                }
                continue;
            }
            if !p.cooldowns.is_empty() {
                return Err(Stop::invalid(&p.unit, "制造单位不应有传输冷却"));
            }
            let buffer = &self.state.inventory[self.inv[&format!("{}:buffer:0", p.unit)]].contents;
            if p.phase == "idle" {
                if !buffer.is_empty()
                    || p.recipe.is_some()
                    || p.locked_recipe.is_some()
                    || p.remaining.is_some()
                    || !p.candidate_recipes.is_empty()
                {
                    return Err(Stop::unsupported(
                        "initialization.other_inventory",
                        &p.unit,
                        "idle 缓存/批次不是空",
                    ));
                }
                continue;
            }
            if !["intake", "working", "completed"].contains(&p.phase.as_str()) {
                return Err(Stop::invalid(&p.unit, "未知制造阶段"));
            }
            let r = self
                .input
                .catalog
                .recipes
                .get(p.recipe.as_deref().unwrap_or(""))
                .ok_or_else(|| Stop::invalid(&p.unit, "批次配方缺失"))?;
            if r.kind != unit.kind
                || p.locked_recipe != p.recipe
                || p.candidate_recipes != vec![r.id.clone()]
            {
                return Err(Stop::invalid(&p.unit, "配方锁定/机型不符"));
            }
            let mut amounts = BTreeMap::new();
            for c in buffer {
                let total = amounts.entry(c.item.clone()).or_insert(0);
                *total = add(*total, c.quantity.integer(&p.unit)?, &p.unit)?;
            }
            let want = if p.phase == "completed" {
                &r.outputs
            } else {
                &r.inputs
            };
            if amounts != *want {
                return Err(Stop::unsupported(
                    "initialization.other_inventory",
                    &p.unit,
                    "缓存不是恰一批原料/成品",
                ));
            }
            if p.phase == "working" {
                let n = p
                    .remaining
                    .as_ref()
                    .ok_or_else(|| Stop::invalid(&p.unit, "在制缺剩余时长"))?
                    .integer(&p.unit)?;
                if n <= 0 || n > r.duration {
                    return Err(Stop::invalid(&p.unit, "在制时长不符"));
                }
                expected_pending.insert(("manufacture_complete".to_string(), p.unit.clone()));
            }
            if p.phase == "completed"
                && p.remaining
                    .as_ref()
                    .map(|x| x.integer(&p.unit))
                    .transpose()?
                    != Some(0)
            {
                return Err(Stop::invalid(&p.unit, "完成态时长非零"));
            }
            if p.phase == "intake"
                && (self.enabled(&p.unit, "manufacture") || p.remaining.is_some())
            {
                return Err(Stop::invalid(&p.unit, "intake 必须停用且尚未计时"));
            }
        }
        for g in &self.state.logistics.gate_counters {
            if g.window_started_at.is_some() {
                expected_pending.insert(("gate_window_expiry".into(), g.unit.clone()));
            }
        }
        let mut pending_keys = BTreeSet::new();
        let mut pending_ids = BTreeSet::new();
        for p in &self.pending {
            if p.event.is_empty() {
                return Err(Stop::invalid("pending_events.event", "待事件身份不能为空"));
            }
            if let Some(event) = timeline.iter().find(|event| event["id"] == p.event) {
                if event["kind"] != "runtime" || event["time"] != p.trigger["value"] {
                    return Err(Stop::invalid(
                        format!("pending_events.{}", p.event),
                        "待事件与历史类型或时刻冲突",
                    ));
                }
            }
            if !pending_keys.insert((p.operation.clone(), p.target.clone()))
                || !pending_ids.insert(p.event.clone())
                || p.status != "waiting"
                || p.trigger["kind"] != "at_time"
                || !p.predecessors.is_empty()
            {
                return Err(Stop::invalid("pending_events", "重复/未支持的日程"));
            }
            let deadline = instant(&p.trigger["value"], &p.event)?;
            let expected = if p.operation == "manufacture_complete" {
                let pr = &self.state.progress[*self
                    .progress
                    .get(&p.target)
                    .ok_or_else(|| Stop::invalid(&p.event, "未知制造目标"))?];
                let n = pr
                    .remaining
                    .as_ref()
                    .ok_or_else(|| Stop::invalid(&p.event, "无在制时长"))?
                    .integer(&p.event)?;
                add(self.t, n, &p.event)?
            } else if p.operation == "gate_window_expiry" {
                let g = &self.state.logistics.gate_counters[*self
                    .gate_index
                    .get(&p.target)
                    .ok_or_else(|| Stop::invalid(&p.event, "未知准入口"))?];
                add(
                    g.window_started_at
                        .as_ref()
                        .ok_or_else(|| Stop::invalid(&p.event, "无窗口"))?
                        .integer(&p.event)?,
                    self.input.catalog.kinds["物品准入口"].window,
                    &p.event,
                )?
            } else {
                return Err(Stop::invalid(&p.event, "待事件不是完成/窗口"));
            };
            // 规则L20：暂停只推迟完成。旧预计截止不能晚于当前剩余工作量的预计完成。
            // 这也使删审计deadline后，旧C身份不会占用同机后续批次的未来身份。
            if p.operation == "manufacture_complete" && deadline > expected {
                return Err(Stop::invalid(&p.event, "旧制造预计截止晚于当前时间加剩余工作量"));
            }
            if p.operation == "gate_window_expiry"
                && (deadline != expected
                    || deadline < self.t
                    || (deadline == self.t && phase == "after_closure"))
            {
                return Err(Stop::invalid(&p.event, "待事件时刻与进度不符"));
            }
        }
        if pending_keys != expected_pending {
            return Err(Stop::invalid("pending_events", "日程与在制/开窗集合不符"));
        }
        let all = self.group_levels(
            &self.input.geometry.channels.keys().cloned().collect(),
            false,
        )?;
        permutation(
            &self.state.semantic_context.arbitration.level_order,
            all.iter()
                .flat_map(|s| s.levels.iter().map(|l| l.id.clone())),
            "arbitration.level_order",
        )?;
        Ok(())
    }
    /// 运行语义§2.2、受限转移§4.1：普通格单种、同种单格、数量容量与运输时间。
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
                items.insert(c.item.as_str());
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
    /// 受限转移§3.1：物理可动完全不读取轮询游标及当前级。
    pub(crate) fn physical(&self, cid: &str) -> Result<(Option<Route>, &'static str)> {
        self.cached_physical(cid)
    }
    pub(crate) fn compute_physical(&self, cid: &str) -> Result<(Option<Route>, &'static str)> {
        if !self.active.contains(cid) {
            return Ok((None, "disconnected"));
        }
        let c = &self.input.geometry.channels[cid];
        let Some((src, content)) = self.source(&c.source_port)? else {
            return Ok((None, "source_empty"));
        };
        let target_unit = &self.input.geometry.ports[&c.target_port].unit;
        if let Some(i) = self.gate_index.get(target_unit) {
            let g = &self.state.logistics.gate_counters[*i];
            let set = &self.input.gate_settings[target_unit];
            if !set["item"].is_null() && set["item"] != content.item {
                return Ok((None, "identity_mismatch"));
            }
            if !g.blocked_reasons.is_empty() {
                return Ok((None, "gate_blocked"));
            }
        }
        if self.production_abstraction
            && self.input.geometry.units[target_unit].kind == "协议核心"
            && crate::ledger::ORES.contains(&content.item.as_str())
        {
            return Err(Stop::unsupported(
                "cycle.domain.D2",
                cid,
                "回矿候选读仓库容量，超出当前矿量抽象；普通run仍可执行",
            ));
        }
        let Some(dst) = self.target(&c.target_port, &content.item)? else {
            return Ok((None, "target_kind"));
        };
        if let Some(i) = self.inv.get(&dst) {
            let rows = &self.state.inventory[*i].contents;
            if let Some(first) = rows.first() {
                let n = rows
                    .iter()
                    .try_fold(0, |n, c| add(n, c.quantity.integer(&dst)?, &dst))?;
                if first.item != content.item || self.caps[&dst].is_some_and(|cap| n >= cap) {
                    return Ok((None, "target_capacity"));
                }
            }
        }
        let uid = &self.input.geometry.ports[&c.source_port].unit;
        let kind = &self.input.catalog.kinds[&self.input.geometry.units[uid].kind];
        if kind.family == "transport" {
            let entered = content
                .entered_at
                .as_ref()
                .ok_or_else(|| Stop::invalid(&src, "运输格缺入格时刻"))?
                .integer(&src)?;
            if self
                .t
                .checked_sub(entered)
                .ok_or_else(|| Stop::new("inconclusive", "resource.integer", cid, "时差溢出"))?
                < 1
            {
                return Ok((None, "residence"));
            }
        }
        if self.usage.get(&c.source_port).copied().unwrap_or(0) > 0
            || self.usage.get(&c.target_port).copied().unwrap_or(0) > 0
        {
            return Ok((None, "port_budget"));
        }
        Ok((
            Some(Route {
                source: src,
                target: dst,
                item: content.item,
            }),
            "ready",
        ))
    }
    /// 受限转移§4.1：扣减保持仓库历史身份；清空普通格则释放身份。
    pub(crate) fn remove(&mut self, slot: &str, item: &str, count: i64) -> Result<()> {
        self.invalidate_slot(slot);
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
        self.invalidate_slot(slot);
        let rows = &mut self.state.inventory[index].contents;
        if let Some(c) = rows.iter_mut().find(|c| {
            c.item == item
                && c.entered_at
                    .as_ref()
                    .is_some_and(|t| t.integer(slot).is_ok_and(|entered| entered == self.t))
        }) {
            c.quantity = Quantity::calc(add(c.quantity.integer(slot)?, count, slot)?)
        } else {
            rows.push(Content {
                item: item.into(),
                quantity: Quantity::calc(count),
                entered_at: Some(Time::at(self.t)),
            });
            rows.sort_by(|a, b| a.item.cmp(&b.item));
        }
        Ok(())
    }
    /// 内核输入§3.1、内核输出§2：生成事件只注册一次。
    pub(crate) fn allocate(&mut self, id: &str) -> Result<()> {
        if !self.allocated.insert(id.into()) {
            return Err(Stop::invalid(id, "运行事件与已注册身份冲突"));
        }
        Ok(())
    }
    /// 内核输出§2：待事件消费与模板机会均禁止重复执行。
    pub(crate) fn execute(&mut self, id: &str) -> Result<()> {
        if !self.allocated.contains(id) || !self.executed.insert(id.into()) {
            return Err(Stop::invalid(id, "事件未注册或重复执行"));
        }
        Ok(())
    }
    /// 内核输出§2：关闭记录时仍执行真实守卫和事件身份检查。
    pub(crate) fn record(&mut self, event: Event) {
        if self.capture {
            self.records.push(event)
        }
    }
}
