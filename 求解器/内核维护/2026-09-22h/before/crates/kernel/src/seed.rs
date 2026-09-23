//! 第五轮K1：初刻派生与检查点恢复分别处理，不倒造已经执行的轮询历史。
use crate::{engine::Engine, input::Input, model::*, value::*, Config};
use serde_json::{json, Value};
use std::{collections::BTreeSet, path::Path};

impl Input {
    /// 输入§6：保留具体库存/进度和显式仲裁顺序，由同一引擎派生冗余上下文。
    pub fn canonicalize_seed(raw: Value, base: &Path, config: &Config) -> Result<Value> {
        // 输入§6.4、KQ-07：先解析封套及完整结构，再区分新起点与历史检查点。
        let mut input = Self::parse_with_base(raw, base, config, false)?;
        let decision: Decision = decode(
            input.raw["initial_state"]["nonwarehouse"].clone(),
            "initial_state.nonwarehouse",
        )?;
        let mut state: State = decode(
            decision
                .resolved("initial_state.nonwarehouse", false)?
                .clone(),
            "initial_state.nonwarehouse.value",
        )?;
        let phase = state
            .semantic_context
            .judgment_context
            .resolved("judgment_context", false)?["phase"]
            .as_str()
            .unwrap_or("");
        if phase == "before_boundary" {
            let current = input.parameters.current();
            let mut names: Vec<_> = state
                .semantic_context
                .parameter_values
                .iter()
                .map(|row| row.axis.clone())
                .collect();
            if names.iter().cloned().collect::<BTreeSet<_>>() != current.keys().cloned().collect()
                || names.len() != current.len()
            {
                names = current.keys().cloned().collect();
            }
            state.semantic_context.parameter_values = names
                .iter()
                .map(|axis| {
                    let (value, lifetime) = &current[axis];
                    Ok(ParameterValue {
                        axis: axis.clone(),
                        value: decode(value.clone(), axis)?,
                        lifetime: lifetime.clone(),
                    })
                })
                .collect::<Result<_>>()?;
            input.raw["initial_state"]["nonwarehouse"]["value"] = json!(state);
        }
        // after_closure的参数缺失、冲突和生命周期错误由严格装载拒收，不作修补。
        let engine = Engine::new_derived(input)?;
        let mut result = engine.input.raw.clone();
        result["initial_state"]["nonwarehouse"]["value"] = json!(engine.state);
        // 输入§1.2：导出到另一目录仍定位同一已校验来源，不沿用旧文件的相对基目录。
        result["catalog"]["path"] = json!(engine.input.catalog.path);
        let registry = engine
            .input
            .source_paths
            .iter()
            .find(|(role, _)| role == "axis_registry")
            .ok_or_else(|| Stop::invalid("axis_registry", "缺已解析来源"))?;
        result["parameters"]["axis_registry"]["path"] = json!(registry.1);
        if let Some(document) =
            result["initial_state"]["reachability"]["value"]["document"].as_str()
        {
            if let Ok(resolved) = base.join(document).canonicalize() {
                result["initial_state"]["reachability"]["value"]["document"] = json!(resolved);
            }
        }
        Ok(result)
    }
}

impl Engine {
    /// 第五轮K1：before_boundary为新调度起点；after_closure保留已验真实续接游标。
    pub(crate) fn derive_context(&mut self) -> Result<()> {
        if self.state.semantic_context.judgment_context.value["phase"] == "after_closure" {
            return Ok(());
        }
        self.state.logistics.connection_order.value = json!("timeline_connection_history");
        let expected: BTreeSet<_> = self
            .input
            .geometry
            .units
            .iter()
            .filter(|(_, u)| self.input.catalog.kinds[&u.kind].family != "power")
            .flat_map(|(u, _)| {
                [
                    (u.clone(), "input".to_string()),
                    (u.clone(), "output".to_string()),
                ]
            })
            .collect();
        if self
            .memory
            .sides
            .iter()
            .map(|s| (s.unit.clone(), s.side.clone()))
            .collect::<BTreeSet<_>>()
            != expected
        {
            self.memory.sides = expected
                .into_iter()
                .map(|(unit, side)| Side {
                    unit,
                    side,
                    graded: true,
                    current_level: None,
                    levels: vec![],
                })
                .collect();
        }
        let all = self.group_levels(
            &self.input.geometry.channels.keys().cloned().collect(),
            false,
        )?;
        let labels: BTreeSet<_> = all
            .iter()
            .flat_map(|s| s.levels.iter().map(|l| l.id.clone()))
            .collect();
        let order = &mut self.state.semantic_context.arbitration.level_order;
        if order.iter().cloned().collect::<BTreeSet<_>>() != labels || order.len() != labels.len() {
            return Err(Stop::invalid(
                "arbitration.level_order",
                "种子派生仍需显式仲裁全序；不得把id排序暗作物理优先级",
            ));
        }
        let blocked: BTreeSet<_> = self
            .input
            .geometry
            .channels
            .iter()
            .filter(|(_, c)| {
                let uid = &self.input.geometry.ports[&c.target_port].unit;
                self.gate_index.get(uid).is_some_and(|i| {
                    !self.state.logistics.gate_counters[*i]
                        .blocked_reasons
                        .is_empty()
                })
            })
            .map(|(id, _)| id.clone())
            .collect();
        self.active = self
            .input
            .geometry
            .channels
            .keys()
            .filter(|c| !blocked.contains(*c))
            .cloned()
            .collect();
        self.state.logistics.active_channels = self
            .channel_order
            .iter()
            .filter(|c| self.active.contains(*c))
            .cloned()
            .collect();
        self.state.logistics.blocked_channels = self
            .channel_order
            .iter()
            .filter(|c| blocked.contains(*c))
            .cloned()
            .collect();
        self.memory.sides = self.group_levels(&self.active, false)?;
        self.rebuild_memory()?;
        self.state.logistics.poll_memory.value = json!(self.memory);
        // 工作量只提供新种子的预计截止；已有暂停日程保留其原登记身份。
        let mut pending = Vec::new();
        for p in &self.state.progress {
            if p.phase == "working" {
                let deadline = add(
                    self.t,
                    p.remaining
                        .as_ref()
                        .ok_or_else(|| Stop::invalid(&p.unit, "缺剩余工作量"))?
                        .integer(&p.unit)?,
                    &p.unit,
                )?;
                let old = self
                    .pending
                    .iter()
                    .find(|e| e.operation == "manufacture_complete" && e.target == p.unit);
                pending.push(old.cloned().unwrap_or(Pending {
                    event: format!("C|{deadline}|{}", p.unit),
                    operation: "manufacture_complete".into(),
                    target: p.unit.clone(),
                    trigger: json!({"kind":"at_time","value":tv(deadline)}),
                    predecessors: vec![],
                    status: "waiting".into(),
                }));
            }
        }
        for g in &self.state.logistics.gate_counters {
            if let Some(start) = &g.window_started_at {
                let deadline = add(
                    start.integer(&g.unit)?,
                    self.input.catalog.kinds["物品准入口"].window,
                    &g.unit,
                )?;
                pending.push(Pending {
                    event: format!("W|{deadline}|{}", g.unit),
                    operation: "gate_window_expiry".into(),
                    target: g.unit.clone(),
                    trigger: json!({"kind":"at_time","value":tv(deadline)}),
                    predecessors: vec![],
                    status: "waiting".into(),
                });
            }
        }
        self.pending = pending;
        self.allocated
            .extend(self.pending.iter().map(|p| p.event.clone()));
        self.state.semantic_context.pending_events.value = json!(self.pending);
        self.state.semantic_context.judgment_context.value = json!({"instant":tv(self.t),"phase":"before_boundary","order_scope":"global","round":0,"next_template":0,"ordered_events":[],"next_event":null});
        self.state.semantic_context.tick_context.value = json!({"window_start":tv(self.t),"window_end":tv(add(self.t,1,"time")?),"movements":[],"port_usage":[],"internal_passages":[]});
        Ok(())
    }
}
