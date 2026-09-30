//! 66 个步进参数轴；取值来自编译时锁定配置。
use crate::value::*;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum Axis {
    #[serde(rename = "polling.direct_peer")]
    PollingDirectPeer,
    #[serde(rename = "connection.port_meeting")]
    ConnectionPortMeeting,
    #[serde(rename = "initialization.rotation_stage")]
    InitializationRotationStage,
    #[serde(rename = "transfer.judgment")]
    TransferJudgment,
    #[serde(rename = "manufacturing.port_slot_relation")]
    ManufacturingPortSlotRelation,
    #[serde(rename = "manufacturing.output_blocked")]
    ManufacturingOutputBlocked,
    #[serde(rename = "gate.limit_requires_identity")]
    GateLimitRequiresIdentity,
    #[serde(rename = "warehouse.capacity")]
    WarehouseCapacity,
    #[serde(rename = "warehouse.delivery_count")]
    WarehouseDeliveryCount,
    #[serde(rename = "bridge.inventory_scope")]
    BridgeInventoryScope,
    #[serde(rename = "bridge.scheduling_scope")]
    BridgeSchedulingScope,
    #[serde(rename = "time.domain")]
    TimeDomain,
    #[serde(rename = "polling.initial_cursor")]
    PollingInitialCursor,
    #[serde(rename = "polling.split_merge_start")]
    PollingSplitMergeStart,
    #[serde(rename = "polling.split_merge_singleton")]
    PollingSplitMergeSingleton,
    #[serde(rename = "transfer.cooldown_scope")]
    TransferCooldownScope,
    #[serde(rename = "transfer.pause")]
    TransferPause,
    #[serde(rename = "transfer.failure_cooldown")]
    TransferFailureCooldown,
    #[serde(rename = "transfer.partial_acceptance")]
    TransferPartialAcceptance,
    #[serde(rename = "manufacturing.input_mixing")]
    ManufacturingInputMixing,
    #[serde(rename = "manufacturing.input_capacity_scope")]
    ManufacturingInputCapacityScope,
    #[serde(rename = "manufacturing.recipe_match_scope")]
    ManufacturingRecipeMatchScope,
    #[serde(rename = "manufacturing.recipe_completeness")]
    ManufacturingRecipeCompleteness,
    #[serde(rename = "manufacturing.empty_slot_identity")]
    ManufacturingEmptySlotIdentity,
    #[serde(rename = "gate.window_clock")]
    GateWindowClock,
    #[serde(rename = "gate.counter_start")]
    GateCounterStart,
    #[serde(rename = "initialization.belt_shape_lifecycle")]
    InitializationBeltShapeLifecycle,
    #[serde(rename = "warehouse.acceptance")]
    WarehouseAcceptance,
    #[serde(rename = "warehouse.acceptance_quantifier")]
    WarehouseAcceptanceQuantifier,
    #[serde(rename = "warehouse.empty_slot_identity")]
    WarehouseEmptySlotIdentity,
    #[serde(rename = "bridge.capacity")]
    BridgeCapacity,
    #[serde(rename = "power.cell_rule")]
    PowerCellRule,
    #[serde(rename = "connection.build_order")]
    ConnectionBuildOrder,
    #[serde(rename = "connection.order")]
    ConnectionOrder,
    #[serde(rename = "connection.tie")]
    ConnectionTie,
    #[serde(rename = "connection.belt_shape")]
    ConnectionBeltShape,
    #[serde(rename = "transfer.phase")]
    TransferPhase,
    #[serde(rename = "manufacturing.recipe_selection")]
    ManufacturingRecipeSelection,
    #[serde(rename = "manufacturing.input_slot_selection")]
    ManufacturingInputSlotSelection,
    #[serde(rename = "initialization.warehouse_anchor")]
    InitializationWarehouseAnchor,
    #[serde(rename = "initialization.other_inventory")]
    InitializationOtherInventory,
    #[serde(rename = "initialization.switches")]
    InitializationSwitches,
    #[serde(rename = "initialization.build_timing")]
    InitializationBuildTiming,
    #[serde(rename = "initialization.debug_end")]
    InitializationDebugEnd,
    #[serde(rename = "warehouse.external_supply")]
    WarehouseExternalSupply,
    #[serde(rename = "gate.counter_edit")]
    GateCounterEdit,
    #[serde(rename = "gate.cancel_limit")]
    GateCancelLimit,
    #[serde(rename = "offline.order_domain")]
    OfflineOrderDomain,
    #[serde(rename = "offline.events")]
    OfflineEvents,
    #[serde(rename = "offline.cursor_effect")]
    OfflineCursorEffect,
    #[serde(rename = "offline.inventory_effect")]
    OfflineInventoryEffect,
    #[serde(rename = "offline.progress_effect")]
    OfflineProgressEffect,
    #[serde(rename = "offline.direction_effect")]
    OfflineDirectionEffect,
    #[serde(rename = "offline.gate_total_effect")]
    OfflineGateTotalEffect,
    #[serde(rename = "offline.gate_window_effect")]
    OfflineGateWindowEffect,
    #[serde(rename = "offline.gate_window_start_effect")]
    OfflineGateWindowStartEffect,
    #[serde(rename = "initialization.debug_actions")]
    InitializationDebugActions,
    #[serde(rename = "initialization.rebuild_inventory")]
    InitializationRebuildInventory,
    #[serde(rename = "warehouse.withdrawal_policy")]
    WarehouseWithdrawalPolicy,
    #[serde(rename = "warehouse.withdrawal_timing")]
    WarehouseWithdrawalTiming,
    #[serde(rename = "warehouse.periodic_lift")]
    WarehousePeriodicLift,
    #[serde(rename = "manufacturing.recipe_quantity_match")]
    ManufacturingRecipeQuantityMatch,
    #[serde(rename = "manufacturing.recipe_extra_items")]
    ManufacturingRecipeExtraItems,
    #[serde(rename = "component.belt_segment")]
    ComponentBeltSegment,
    #[serde(rename = "step.order")]
    StepOrder,
    #[serde(rename = "transfer.timing")]
    TransferTiming,
}
impl Axis {
    pub fn name(self) -> &'static str {
        match self {
            Self::PollingDirectPeer => "polling.direct_peer",
            Self::ConnectionPortMeeting => "connection.port_meeting",
            Self::InitializationRotationStage => "initialization.rotation_stage",
            Self::TransferJudgment => "transfer.judgment",
            Self::ManufacturingPortSlotRelation => "manufacturing.port_slot_relation",
            Self::ManufacturingOutputBlocked => "manufacturing.output_blocked",
            Self::GateLimitRequiresIdentity => "gate.limit_requires_identity",
            Self::WarehouseCapacity => "warehouse.capacity",
            Self::WarehouseDeliveryCount => "warehouse.delivery_count",
            Self::BridgeInventoryScope => "bridge.inventory_scope",
            Self::BridgeSchedulingScope => "bridge.scheduling_scope",
            Self::TimeDomain => "time.domain",
            Self::PollingInitialCursor => "polling.initial_cursor",
            Self::PollingSplitMergeStart => "polling.split_merge_start",
            Self::PollingSplitMergeSingleton => "polling.split_merge_singleton",
            Self::TransferCooldownScope => "transfer.cooldown_scope",
            Self::TransferPause => "transfer.pause",
            Self::TransferFailureCooldown => "transfer.failure_cooldown",
            Self::TransferPartialAcceptance => "transfer.partial_acceptance",
            Self::ManufacturingInputMixing => "manufacturing.input_mixing",
            Self::ManufacturingInputCapacityScope => "manufacturing.input_capacity_scope",
            Self::ManufacturingRecipeMatchScope => "manufacturing.recipe_match_scope",
            Self::ManufacturingRecipeCompleteness => "manufacturing.recipe_completeness",
            Self::ManufacturingEmptySlotIdentity => "manufacturing.empty_slot_identity",
            Self::GateWindowClock => "gate.window_clock",
            Self::GateCounterStart => "gate.counter_start",
            Self::InitializationBeltShapeLifecycle => "initialization.belt_shape_lifecycle",
            Self::WarehouseAcceptance => "warehouse.acceptance",
            Self::WarehouseAcceptanceQuantifier => "warehouse.acceptance_quantifier",
            Self::WarehouseEmptySlotIdentity => "warehouse.empty_slot_identity",
            Self::BridgeCapacity => "bridge.capacity",
            Self::PowerCellRule => "power.cell_rule",
            Self::ConnectionBuildOrder => "connection.build_order",
            Self::ConnectionOrder => "connection.order",
            Self::ConnectionTie => "connection.tie",
            Self::ConnectionBeltShape => "connection.belt_shape",
            Self::TransferPhase => "transfer.phase",
            Self::ManufacturingRecipeSelection => "manufacturing.recipe_selection",
            Self::ManufacturingInputSlotSelection => "manufacturing.input_slot_selection",
            Self::InitializationWarehouseAnchor => "initialization.warehouse_anchor",
            Self::InitializationOtherInventory => "initialization.other_inventory",
            Self::InitializationSwitches => "initialization.switches",
            Self::InitializationBuildTiming => "initialization.build_timing",
            Self::InitializationDebugEnd => "initialization.debug_end",
            Self::WarehouseExternalSupply => "warehouse.external_supply",
            Self::GateCounterEdit => "gate.counter_edit",
            Self::GateCancelLimit => "gate.cancel_limit",
            Self::OfflineOrderDomain => "offline.order_domain",
            Self::OfflineEvents => "offline.events",
            Self::OfflineCursorEffect => "offline.cursor_effect",
            Self::OfflineInventoryEffect => "offline.inventory_effect",
            Self::OfflineProgressEffect => "offline.progress_effect",
            Self::OfflineDirectionEffect => "offline.direction_effect",
            Self::OfflineGateTotalEffect => "offline.gate_total_effect",
            Self::OfflineGateWindowEffect => "offline.gate_window_effect",
            Self::OfflineGateWindowStartEffect => "offline.gate_window_start_effect",
            Self::InitializationDebugActions => "initialization.debug_actions",
            Self::InitializationRebuildInventory => "initialization.rebuild_inventory",
            Self::WarehouseWithdrawalPolicy => "warehouse.withdrawal_policy",
            Self::WarehouseWithdrawalTiming => "warehouse.withdrawal_timing",
            Self::WarehousePeriodicLift => "warehouse.periodic_lift",
            Self::ManufacturingRecipeQuantityMatch => "manufacturing.recipe_quantity_match",
            Self::ManufacturingRecipeExtraItems => "manufacturing.recipe_extra_items",
            Self::ComponentBeltSegment => "component.belt_segment",
            Self::StepOrder => "step.order",
            Self::TransferTiming => "transfer.timing",
        }
    }
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum Disposition {
    #[serde(rename = "本版选值")]
    Selected,
    #[serde(rename = "已定")]
    Fixed,
    #[serde(rename = "由输入全称量化")]
    Input,
    #[serde(rename = "超出覆盖即停")]
    Stop,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct AxisConfig {
    pub disposition: Disposition,
    pub value: Value,
    pub meaning: String,
    pub coverage_loss: String,
    pub extension_gate: String,
    pub choice: String,
    pub lifetime: String,
    pub basis: String,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Config {
    pub schema: String,
    pub profile_id: String,
    pub revision: String,
    pub axis_count: usize,
    pub axes: BTreeMap<Axis, AxisConfig>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Reference {
    pub path: String,
    pub sha256: String,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Parameters {
    pub axis_registry: Reference,
    pub profile_id: Option<String>,
    pub fixed: BTreeMap<Axis, Decision>,
    pub offline_mutable: BTreeMap<Axis, Decision>,
    pub fixedness_unproven: BTreeMap<Axis, Decision>,
}
impl Config {
    /// 受限模型声明§2：以编译期读取的配置作为实现支持表，拒绝配置改值伪装支持。
    pub fn parse(v: Value) -> Result<Self> {
        let c: Self = decode(v, "config")?;
        let supported: Self = decode(
            serde_json::from_str(include_str!("../../../规格/内核配置-v2.json"))
                .map_err(|e| Stop::invalid("embedded_config", e.to_string()))?,
            "embedded_config",
        )?;
        if c.revision != supported.revision
            || c.schema != supported.schema
            || c.profile_id != supported.profile_id
            || c.axis_count != supported.axis_count
            || c.axes.keys().ne(supported.axes.keys())
        {
            return Err(Stop::invalid("config.axes", "配置版本或轴全集不符"));
        }
        for (a, r) in &c.axes {
            let s = &supported.axes[a];
            if r != s {
                return Err(Stop::unsupported(
                    a.name(),
                    format!("config.axes.{}", a.name()),
                    "配置修改超出已实现取值/处置",
                ));
            }
        }
        Ok(c)
    }
    /// 受限转移§1：每轴恰有一个输入决定，固定轴不可变，输入轴不使用配置接口作为值。
    pub fn validate(&self, p: &Parameters) -> Result<()> {
        if p.profile_id.as_deref() != Some(self.profile_id.as_str()) {
            return Err(Stop::unsupported(
                "profile_id",
                "parameters.profile_id",
                "执行须显式选择配置",
            ));
        }
        let mut seen = BTreeMap::new();
        for (group, lifetime, rows) in [
            ("fixed", "F", &p.fixed),
            ("offline_mutable", "O", &p.offline_mutable),
            ("fixedness_unproven", "U", &p.fixedness_unproven),
        ] {
            for (a, d) in rows {
                if seen.insert(*a, ()).is_some() {
                    return Err(Stop::invalid(
                        format!("parameters.{group}.{}", a.name()),
                        "轴重复",
                    ));
                }
                let rule = self
                    .axes
                    .get(a)
                    .ok_or_else(|| Stop::invalid(a.name(), "未知轴"))?;
                let expected = if rule.lifetime.starts_with('F') {
                    "F"
                } else if rule.lifetime == "O" {
                    "O"
                } else {
                    "U"
                };
                if lifetime != expected {
                    return Err(Stop::invalid(a.name(), "轴生命周期错组"));
                }
                let value = d.resolved(a.name(), false)?;
                if rule.disposition != Disposition::Input && *value != rule.value {
                    return Err(if rule.disposition == Disposition::Fixed {
                        Stop::new(
                            "invalid_input",
                            a.name(),
                            format!("parameters.{group}.{}", a.name()),
                            "已定轴值冲突",
                        )
                    } else {
                        Stop::unsupported(
                            a.name(),
                            format!("parameters.{group}.{}", a.name()),
                            "未支持的轴值",
                        )
                    });
                }
            }
        }
        if seen.len() != self.axes.len() {
            return Err(Stop::invalid("parameters", "轴缺失"));
        }
        Ok(())
    }
    /// 受限转移§1：显式请求停止域；义务请求同样不能静默执行。
    pub fn request(&self, a: Axis, location: &str) -> Result<()> {
        let r = &self.axes[&a];
        if r.disposition == Disposition::Stop {
            return Err(Stop::unsupported(a.name(), location, &r.meaning));
        }
        Ok(())
    }
}
impl Parameters {
    /// 内核输入§5：按轴身份检索已解实际值，不接受默认值。
    pub fn value(&self, a: Axis) -> Result<&Value> {
        self.fixed
            .get(&a)
            .or_else(|| self.offline_mutable.get(&a))
            .or_else(|| self.fixedness_unproven.get(&a))
            .ok_or_else(|| Stop::invalid(a.name(), "缺少轴"))?
            .resolved(a.name(), false)
    }
}
