//! 运行语义§2、内核输入§6：完整状态的无损编码与确定迭代结构。
use crate::value::*;
use serde::{Deserialize, Serialize};
use serde_json::Value;
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Content {
    pub item: String,
    pub quantity: Quantity,
    pub entered_at: Option<Time>,
    /// 桥格物品的直接来路；空值表示初态尚未移动。
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub last_unit: Option<String>,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Inventory {
    pub slot: String,
    pub contents: Vec<Content>,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct WarehouseSlot {
    pub slot: String,
    pub item: Option<String>,
    pub quantity: Quantity,
    pub empty_identity: Decision,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Warehouse {
    pub slots: Vec<WarehouseSlot>,
    pub unlisted: String,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Cooldown {
    pub slot: Option<String>,
    pub remaining: Time,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Progress {
    pub unit: String,
    pub phase: String,
    pub recipe: Option<String>,
    pub candidate_recipes: Vec<String>,
    pub locked_recipe: Option<String>,
    pub remaining: Option<Time>,
    pub cooldowns: Vec<Cooldown>,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Level {
    pub id: String,
    pub members: Vec<String>,
    pub next_channel: String,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Side {
    pub unit: String,
    pub side: String,
    /// 桥按本地轴分开调度，其余单位为空。
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub axis: Option<String>,
    pub graded: bool,
    pub current_level: Option<String>,
    pub levels: Vec<Level>,
}
impl Side {
    pub(crate) fn label(&self) -> String {
        match &self.axis {
            Some(axis) => format!("{}:{}:{}", self.unit, self.side, axis),
            None => format!("{}:{}", self.unit, self.side),
        }
    }
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct PollMemory {
    pub schema: String,
    pub sides: Vec<Side>,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Gate {
    pub unit: String,
    pub total_received: Quantity,
    pub window_received: Quantity,
    pub window_started_at: Option<Time>,
    pub blocked_reasons: Vec<String>,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Logistics {
    pub active_channels: Vec<String>,
    pub blocked_channels: Vec<String>,
    pub poll_memory: Decision,
    pub gate_counters: Vec<Gate>,
    pub connection_order: Decision,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Environment {
    pub time: Time,
    pub stage: String,
    pub online: bool,
    pub withdrawal_memory: Decision,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Arbitration {
    pub level_order: Vec<String>,
    pub warehouse_empty_slot_order: Vec<String>,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct ParameterValue {
    pub axis: String,
    pub value: Decision,
    pub lifetime: String,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct SemanticContext {
    pub arbitration: Arbitration,
    pub parameter_values: Vec<ParameterValue>,
    pub judgment_context: Decision,
    pub pending_events: Decision,
    pub tick_context: Decision,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct State {
    pub layout_snapshot: String,
    pub settings_anchor: Value,
    pub warehouse: Warehouse,
    pub inventory: Vec<Inventory>,
    pub progress: Vec<Progress>,
    pub logistics: Logistics,
    pub environment: Environment,
    pub semantic_context: SemanticContext,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(deny_unknown_fields)]
pub struct Template {
    pub operation: String,
    pub target: String,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Event {
    pub event: String,
    pub operation: String,
    pub target: String,
    pub outcome: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub detail: Option<String>,
    pub basis: Vec<String>,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Pending {
    pub event: String,
    pub operation: String,
    pub target: String,
    pub trigger: Value,
    pub predecessors: Vec<String>,
    pub status: String,
}
