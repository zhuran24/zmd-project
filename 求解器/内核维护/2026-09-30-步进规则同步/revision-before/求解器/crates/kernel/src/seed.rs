//! 步边界种子规范化；不继承或推测旧语义轮询。
use crate::{model::*, value::*, Config, Engine, Input};
use serde_json::{json, Value};
use std::path::Path;
impl Input {
    pub fn canonicalize_seed(raw: Value, base: &Path, config: &Config) -> Result<Value> {
        let mut input = Self::parse_with_base(raw, base, config)?;
        let mut state: State = decode(
            input.raw["initial_state"]["nonwarehouse"]["value"].clone(),
            "StateSeed",
        )?;
        let time = state.environment.time.integer("time")?;
        let sides = input.graph.cursor_sides();
        for side in sides.keys() {
            if !state
                .logistics
                .poll_state
                .cursors
                .iter()
                .any(|r| &r.side == side)
            {
                state.logistics.poll_state.cursors.push(Cursor {
                    side: side.clone(),
                    last_success: None,
                });
            }
        }
        for (unit, channels) in &input.graph.outputs_nt {
            if channels.len() > 1
                && !state
                    .logistics
                    .poll_state
                    .recency
                    .iter()
                    .any(|r| &r.unit == unit)
            {
                state.logistics.poll_state.recency.push(Recency {
                    unit: unit.clone(),
                    order: vec![],
                });
            }
        }
        state
            .logistics
            .poll_state
            .cursors
            .sort_by(|a, b| a.side.cmp(&b.side));
        state
            .logistics
            .poll_state
            .recency
            .sort_by(|a, b| a.unit.cmp(&b.unit));
        for gate in &mut state.logistics.gate_counters {
            if let Some(w) = &gate.window_started_at {
                if add(
                    w.integer(&gate.unit)?,
                    input.catalog.kinds["物品准入口"].window,
                    &gate.unit,
                )? <= time
                {
                    gate.window_started_at = None;
                    gate.window_received = Quantity::calc(0);
                }
            }
        }
        for row in &mut state.inventory {
            row.contents.sort_by(|a, b| a.item.cmp(&b.item));
        }
        input.raw["initial_state"]["nonwarehouse"]["value"] = json!(state);
        let engine = Engine::new(input)?;
        let mut raw = engine.input.raw.clone();
        raw["initial_state"]["nonwarehouse"]["value"] = json!(engine.state);
        raw["catalog"]["path"] = json!(engine.input.catalog.path);
        let registry = engine
            .input
            .source_paths
            .iter()
            .find(|(r, _)| r == "axis_registry")
            .ok_or_else(|| Stop::invalid("axis_registry", "缺来源"))?;
        raw["parameters"]["axis_registry"]["path"] = json!(registry.1);
        if let Some(doc) = raw["initial_state"]["reachability"]["value"]["document"].as_str() {
            if let Ok(p) = base.join(doc).canonicalize() {
                raw["initial_state"]["reachability"]["value"]["document"] = json!(p);
            }
        }
        Ok(raw)
    }
}
