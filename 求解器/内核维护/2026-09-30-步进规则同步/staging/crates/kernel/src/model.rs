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
pub struct Progress { pub unit: String, pub phase: String, pub recipe: Option<String>, pub remaining: Option<Time>, pub cooldown: Option<Time> }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Cursor { pub side: String, pub last_success: Option<String> }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Recency { pub unit: String, pub order: Vec<String> }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct PollState { pub schema: String, pub cursors: Vec<Cursor>, pub recency: Vec<Recency> }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Gate { pub unit: String, pub total_received: Quantity, pub window_received: Quantity, pub window_started_at: Option<Time> }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Logistics { pub poll_state: PollState, pub gate_counters: Vec<Gate> }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Environment { pub time: Time, pub stage: String, pub online: bool, pub withdrawal_memory: Decision }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct SemanticContext { pub warehouse_empty_slot_order: Vec<String> }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct State { pub layout_snapshot: String, pub settings_anchor: Value, pub warehouse: Warehouse, pub inventory: Vec<Inventory>, pub progress: Vec<Progress>, pub logistics: Logistics, pub environment: Environment, pub semantic_context: SemanticContext }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Move { pub channel: String, pub item: String }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Event { pub event: String, pub phase: String, pub subject: String, pub moves: Vec<Move>, pub detail: Option<Value> }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct StepReport { pub step: i64, pub events: Vec<Event>, pub ledger: Value }
