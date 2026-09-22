//! 内核输出§2–§3：独立于转移重算的全记录事件注册、消费与待办连续性校验。
use crate::{value::*, Input};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

/// 内核输入§3.1：读非空身份，拒绝将缺字段折叠为空标签。
fn identity<'a>(value: &'a Value, at: &str) -> Result<&'a str> {
    value
        .as_str()
        .filter(|s| !s.is_empty())
        .ok_or_else(|| Stop::invalid(at, "事件身份须为非空字符串"))
}

/// 内核输出§2：初态账本已经消费过的事件不能再列为待办或重新执行。
pub(crate) fn seed_executed(input: &Input, start: &Value) -> Result<BTreeSet<String>> {
    let context = &start["semantic_context"];
    let mut result = BTreeSet::new();
    let time = instant(&start["environment"]["time"], "seed.time")?;
    let rounds = context["judgment_context"]["value"]["round"]
        .as_u64()
        .ok_or_else(|| Stop::invalid("judgment_context.round", "须为非负整数"))?;
    let history: BTreeMap<_, _> = input.raw["timeline"]["events"]
        .as_array()
        .unwrap()
        .iter()
        .map(|e| (e["id"].as_str().unwrap(), e))
        .collect();
    let mut passages = BTreeSet::new();
    let mut descriptors = BTreeMap::new();
    for key in ["movements", "internal_passages"] {
        for row in context["tick_context"]["value"][key]
            .as_array()
            .ok_or_else(|| Stop::invalid(key, "初态账本须为数组"))?
        {
            fields(
                row,
                if key == "movements" {
                    "event channel item quantity"
                } else {
                    "event batch channel"
                },
                key,
            )?;
            let id = identity(&row["event"], key)?;
            let channel = identity(&row["channel"], key)?;
            let (operation, target) = if key == "movements" {
                if !input.geometry.channels.contains_key(channel) || !result.insert(id.into()) {
                    return Err(Stop::invalid(id, "成功移动身份重复或PC未知"));
                }
                let item = identity(&row["item"], "movements.item")?;
                if num(&row["quantity"], "movements.quantity")? != 1
                    || !input
                        .catalog
                        .recipes
                        .values()
                        .any(|r| r.inputs.contains_key(item) || r.outputs.contains_key(item))
                {
                    return Err(Stop::invalid(id, "移动件数或物种非法"));
                }
                ("move", channel)
            } else {
                let batch = identity(&row["batch"], "internal_passages.batch")?;
                if !input.geometry.buffers.contains(channel)
                    || !passages.insert((id.to_string(), batch.to_string(), channel.to_string()))
                {
                    return Err(Stop::invalid(id, "内部穿越重复或BC未知"));
                }
                result.insert(id.into());
                let target = channel
                    .strip_prefix("BC|")
                    .and_then(|s| s.split(':').next())
                    .ok_or_else(|| Stop::invalid(id, "BC身份非法"))?;
                ("manufacture", target)
            };
            let descriptor = (operation.to_string(), target.to_string());
            if descriptors
                .insert(id.to_string(), descriptor.clone())
                .is_some_and(|old| old != descriptor)
            {
                return Err(Stop::invalid(id, "同一已消费实例被用于不同操作或目标"));
            }
            if let Some(event) = history.get(id) {
                if event["kind"] != "runtime" || instant(&event["time"], id)? != time {
                    return Err(Stop::invalid(id, "已消费实例与全局历史类型/时刻冲突"));
                }
            }
            if id.starts_with("J|") {
                let parts: Vec<_> = id.split('|').collect();
                let position = parts.get(3).and_then(|s| s.parse::<usize>().ok());
                let round = parts.get(2).and_then(|s| s.parse::<u64>().ok());
                if parts.len() != 4
                    || parts[1] != time.to_string()
                    || round.is_none_or(|r| r >= rounds)
                    || position
                        .and_then(|i| input.templates.get(i))
                        .is_none_or(|t| t.operation != operation || t.target != target)
                    || id != format!("J|{time}|{}|{}", round.unwrap_or(0), position.unwrap_or(0))
                {
                    return Err(Stop::invalid(id, "成功账本与J实例时刻/扫描位置/模板不符"));
                }
            } else if id.starts_with("C|") || id.starts_with("W|") || !history.contains_key(id) {
                return Err(Stop::invalid(id, "成功账本须引用全局runtime或合法J实例"));
            }
        }
    }
    for id in context["judgment_context"]["value"]["ordered_events"]
        .as_array()
        .ok_or_else(|| Stop::invalid("ordered_events", "须为数组"))?
    {
        result.insert(identity(id, "ordered_events")?.to_string());
    }
    Ok(result)
}

struct Registry<'a> {
    history: BTreeMap<String, &'a Value>,
    registered: BTreeMap<String, Value>,
    executed: BTreeSet<String>,
    previous_pending: BTreeSet<String>,
}
impl Registry<'_> {
    /// 内核输出§2：历史 runtime 仅可在初态恢复；同一待事件跨状态描述不能改变。
    fn pending(&mut self, state: &Value, initial: bool) -> Result<()> {
        let mut current = BTreeSet::new();
        for row in state["semantic_context"]["pending_events"]["value"]
            .as_array()
            .ok_or_else(|| Stop::invalid("pending_events", "须为数组"))?
        {
            fields(
                row,
                "event operation target trigger predecessors status",
                "pending_events[]",
            )?;
            let id = identity(&row["event"], "pending_events.event")?;
            if !current.insert(id.to_string()) || self.executed.contains(id) {
                return Err(Stop::invalid(id, "待事件重复或已执行又待办"));
            }
            if !["manufacture_complete", "gate_window_expiry"]
                .contains(&row["operation"].as_str().unwrap_or(""))
                || row["status"] != "waiting"
                || row["trigger"]["kind"] != "at_time"
            {
                return Err(Stop::invalid(id, "待事件操作、状态或触发类型非法"));
            }
            instant(&row["trigger"]["value"], id)?;
            let descriptor = json!({"operation":row["operation"],"target":row["target"],"trigger":row["trigger"],"predecessors":row["predecessors"]});
            if let Some(old) = self.registered.get(id) {
                if *old != descriptor {
                    return Err(Stop::invalid(id, "同一待事件的操作/目标/触发被改用"));
                }
            } else {
                if let Some(history) = self.history.get(id) {
                    if !initial
                        || history["kind"] != "runtime"
                        || history["time"] != row["trigger"]["value"]
                    {
                        return Err(Stop::invalid(id, "待事件复用历史身份或时刻冲突"));
                    }
                }
                self.registered.insert(id.to_string(), descriptor);
            }
        }
        if self
            .previous_pending
            .iter()
            .any(|id| !self.executed.contains(id) && !current.contains(id))
        {
            return Err(Stop::invalid("pending_events", "待事件未经执行而消失"));
        }
        self.previous_pending = current;
        Ok(())
    }
}

/// 内核输出§2–§3：可独立调用；初态、跨时刻及两种编码解码后的身份必须闭合。
pub fn validate_event_identity(input: &Input, start: &Value, ticks: &[Value]) -> Result<()> {
    let mut validator = EventValidator::new(input, start)?;
    for tick in ticks {
        validator.tick(tick)?;
    }
    Ok(())
}
/// 无记录核验保留跨刻身份集合，逐刻消费后释放完整状态和事件数组。
pub(crate) struct EventValidator<'a> {
    input: &'a Input,
    registry: Registry<'a>,
}
impl<'a> EventValidator<'a> {
    pub(crate) fn new(input: &'a Input, start: &Value) -> Result<Self> {
        let mut registry = Registry {
            history: input.raw["timeline"]["events"]
                .as_array()
                .unwrap()
                .iter()
                .map(|e| (e["id"].as_str().unwrap().to_string(), e))
                .collect(),
            registered: BTreeMap::new(),
            executed: seed_executed(input, start)?,
            previous_pending: BTreeSet::new(),
        };
        registry.pending(start, true)?;
        Ok(Self { input, registry })
    }
    pub(crate) fn tick(&mut self, tick: &Value) -> Result<()> {
        let input = self.input;
        let registry = &mut self.registry;
        let supply = input
            .parameters
            .value(crate::config::Axis::WarehouseExternalSupply)?;
        let supplies: BTreeMap<_, _> = supply["events"]
            .as_array()
            .into_iter()
            .flatten()
            .map(|e| (e["event"].as_str().unwrap(), e))
            .collect();
        let mut previous_phase = None;
        for event in tick["events"]
            .as_array()
            .ok_or_else(|| Stop::invalid("ticks.events", "须为数组"))?
        {
            let id = identity(&event["event"], "ticks.events.event")?;
            // 受限转移§2.1：身份合法也不能反排固定阶段；窗口同批不以日志顺序赋予新语义。
            let phase = match event["operation"].as_str() {
                Some("manufacture_complete") => 0,
                Some("ore_supply") => 1,
                Some("gate_window_expiry") => 2,
                Some("move" | "manufacture" | "transfer" | "gate_identity_maintenance") => 3,
                _ => return Err(Stop::invalid(id, "本版未知执行事件类型")),
            };
            if previous_phase.is_some_and(|p| p > phase) {
                return Err(Stop::invalid(id, "执行次序违反固定边界阶段"));
            }
            previous_phase = Some(phase);
            if registry.executed.contains(id) {
                return Err(Stop::invalid(id, "跨时刻事件重复执行"));
            }
            if let Some(pending) = registry.registered.get(id) {
                if event["operation"] != pending["operation"]
                    || event["target"] != pending["target"]
                    || (pending["operation"] == "gate_window_expiry"
                        && pending["trigger"]["value"] != tick["time"])
                {
                    return Err(Stop::invalid(id, "执行的操作/目标/时刻与待事件登记不符"));
                }
            } else if let Some(supply) = supplies.get(id) {
                if event["operation"] != "ore_supply"
                    || event["target"] != "warehouse"
                    || supply["time"] != tick["time"]
                {
                    return Err(Stop::invalid(id, "补矿事件被改用"));
                }
            } else if registry.history.contains_key(id)
                || ["manufacture_complete", "gate_window_expiry", "ore_supply"]
                    .contains(&event["operation"].as_str().unwrap_or(""))
            {
                return Err(Stop::invalid(id, "执行复用历史身份或非判定事件未经登记"));
            }
            registry.executed.insert(id.to_string());
        }
        let consumed = seed_executed(input, &tick["state"])?;
        if !consumed.is_subset(&registry.executed) {
            return Err(Stop::invalid("tick_context", "成功账本引用未执行事件"));
        }
        registry.pending(&tick["state"], false)?;
        Ok(())
    }
}
