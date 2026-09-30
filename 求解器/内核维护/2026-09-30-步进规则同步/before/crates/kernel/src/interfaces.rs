//! 内核输入§5.3–§6：输入轴的语义接口与历史封套核验。
use crate::{config::Axis, input::Input, value::*};
use serde_json::json;
use std::collections::BTreeSet;
impl Input {
    /// 内核输入§5.4：所有输入接口逐个识别，不把任意非空字符串当可执行值。
    pub(crate) fn check_input_axes(&self) -> Result<()> {
        let p = &self.parameters;
        for (a, kind, path) in [
            (
                Axis::InitializationOtherInventory,
                "synthetic_seed",
                "initial_state.nonwarehouse",
            ),
            (Axis::InitializationSwitches, "input_settings", "settings"),
            (Axis::InitializationBuildTiming, "input_history", "timeline"),
        ] {
            let v = p.value(a)?;
            if v["kind"] != kind || v["path"] != path {
                return Err(Stop::unsupported(
                    a.name(),
                    a.name(),
                    "未支持的输入来源接口",
                ));
            }
        }
        let anchor = p.value(Axis::InitializationWarehouseAnchor)?;
        fields(anchor, "kind event side", "initialization.warehouse_anchor")?;
        if anchor["kind"] != "input_anchor"
            || anchor["event"] != self.raw["initial_state"]["anchor"]["value"]["event"]
            || anchor["side"] != self.raw["initial_state"]["anchor"]["value"]["side"]
        {
            return Err(Stop::invalid(
                "initialization.warehouse_anchor",
                "参数锚点与任务初始锚点不符",
            ));
        }
        let end = p.value(Axis::InitializationDebugEnd)?;
        fields(
            end,
            "kind event not_a_timing_strategy",
            "initialization.debug_end",
        )?;
        if end["kind"] != "input_witness"
            || end["event"] != self.raw["environment"]["debug_end_event"]
            || end["not_a_timing_strategy"] != true
        {
            return Err(Stop::unsupported(
                "initialization.debug_end",
                "parameters",
                "须为具体历史见证，不能给定时策略",
            ));
        }
        let shapes = p.value(Axis::ConnectionBeltShape)?;
        fields(shapes, "kind values", "connection.belt_shape")?;
        if shapes["kind"] != "layout_build_history" {
            return Err(Stop::unsupported(
                "connection.belt_shape",
                "parameters",
                "未支持形状接口",
            ));
        }
        let mut seen = BTreeSet::new();
        for r in shapes["values"]
            .as_array()
            .ok_or_else(|| Stop::invalid("belt_shape.values", "须为数组"))?
        {
            fields(r, "unit build_event shape", "belt_shape")?;
            let uid = r["unit"].as_str().unwrap_or("");
            let u = self
                .geometry
                .units
                .get(uid)
                .ok_or_else(|| Stop::invalid(uid, "形状引用未知单位"))?;
            if u.kind != "传送带" || !seen.insert(uid.to_string()) {
                return Err(Stop::invalid(uid, "形状身份重复/类型错误"));
            }
            let layout = u.raw["port_layout"].as_u64().unwrap() as usize;
            let edges = self.catalog.kinds[&u.kind].layouts[layout]
                .as_array()
                .unwrap();
            let sides = ["south", "east", "north", "west"];
            let mut input = 0;
            let mut output = 0;
            for e in edges {
                let index = sides.iter().position(|s| e["side"] == *s).unwrap();
                if e["role"] == "input" {
                    input = index
                } else {
                    output = index
                }
            }
            let shape = match (output + 4 - input) % 4 {
                1 => "turn_left",
                2 => "straight",
                3 => "turn_right",
                _ => return Err(Stop::invalid(uid, "带同边进出")),
            };
            let build = self.raw["construction"]["moments"]
                .as_array()
                .unwrap()
                .iter()
                .find(|m| m["unit"] == uid)
                .unwrap();
            if r["shape"] != shape || r["build_event"] != build["event"] {
                return Err(Stop::invalid(uid, "形状/生命段与几何不符"));
            }
        }
        let expected: BTreeSet<_> = self
            .geometry
            .units
            .iter()
            .filter(|(_, u)| u.kind == "传送带")
            .map(|(u, _)| u.clone())
            .collect();
        if seen != expected {
            return Err(Stop::invalid("connection.belt_shape", "传送带形状未覆盖"));
        }
        let phase = p.value(Axis::TransferPhase)?;
        fields(phase, "kind values", "transfer.phase")?;
        if phase["kind"] != "explicit_residuals" {
            return Err(Stop::unsupported(
                "transfer.phase",
                "parameters",
                "未支持冷却接口",
            ));
        }
        let seed = &self.raw["initial_state"]["nonwarehouse"]["value"];
        let mut boxes = BTreeSet::new();
        for (index, r) in phase["values"]
            .as_array()
            .ok_or_else(|| Stop::invalid("transfer.phase.values", "须为数组"))?
            .iter()
            .enumerate()
        {
            fields(r, "unit slot remaining", "transfer.phase.value")?;
            let uid = r["unit"].as_str().unwrap_or("");
            if !r["slot"].is_null()
                || !boxes.insert(uid.to_string())
                || !self
                    .geometry
                    .units
                    .get(uid)
                    .is_some_and(|u| u.kind == "协议储存箱")
            {
                return Err(Stop::invalid(uid, "按箱相位字段错误"));
            }
            // 输入§1.1/§5.4：历史初相位可不同于当前冷却，但自身始终须在本版Time域内。
            let at = format!("transfer.phase.values[{index}].remaining");
            let remaining = instant(&r["remaining"], &at)?;
            if remaining < 0 || remaining > self.catalog.kinds["协议储存箱"].cooldown {
                return Err(Stop::invalid(at, "初相位超出箱体冷却范围"));
            }
            let pr = seed["progress"]
                .as_array()
                .ok_or_else(|| Stop::invalid("seed.progress", "须为数组"))?
                .iter()
                .find(|x| x["unit"] == uid)
                .ok_or_else(|| Stop::invalid(uid, "缺箱进度"))?;
            if pr["cooldowns"].as_array().is_none_or(|c| c.len() != 1)
                || (seed["semantic_context"]["judgment_context"]["value"]["phase"]
                    != "after_closure"
                    && r["remaining"] != pr["cooldowns"][0]["remaining"])
            {
                return Err(Stop::invalid(uid, "相位与种子冷却不符"));
            }
        }
        if boxes
            != self
                .geometry
                .units
                .iter()
                .filter(|(_, u)| u.kind == "协议储存箱")
                .map(|(u, _)| u.clone())
                .collect()
        {
            return Err(Stop::invalid("transfer.phase", "箱相位未覆盖"));
        }
        let supply = p.value(Axis::WarehouseExternalSupply)?;
        let sufficient = supply["kind"] == "sufficient";
        fields(
            supply,
            if sufficient {
                "kind"
            } else {
                "kind events through"
            },
            "warehouse.external_supply",
        )?;
        if !sufficient && supply["kind"] != "explicit_ore_history" {
            return Err(Stop::unsupported(
                "warehouse.external_supply",
                "parameters",
                "未知补矿模式",
            ));
        }
        let start = instant(&seed["environment"]["time"], "seed.time")?;
        let through = if sufficient {
            i64::MAX
        } else {
            instant(&supply["through"], "ore_history.through")?
        };
        if through < start {
            return Err(Stop::invalid("ore_history.through", "历史覆盖早于种子"));
        }
        let mut ids = BTreeSet::new();
        let mut previous = None;
        for r in supply["events"].as_array().into_iter().flatten() {
            fields(r, "event time item quantity", "ore_history.event")?;
            let id = r["event"].as_str().unwrap_or("");
            let t = instant(&r["time"], "ore_history.time")?;
            if id.is_empty()
                || !ids.insert(id)
                || previous.is_some_and(|p| p > t)
                || (t < start
                    && seed["semantic_context"]["judgment_context"]["value"]["phase"]
                        != "after_closure")
                || t > through
                || !["源矿", "蓝铁矿"].contains(&r["item"].as_str().unwrap_or(""))
                || num(&r["quantity"], id)? <= 0
            {
                return Err(Stop::invalid(
                    "ore_history.events",
                    "补给身份/物种/数量/顺序/范围非法",
                ));
            }
            previous = Some(t);
            let found = self.raw["timeline"]["events"]
                .as_array()
                .unwrap()
                .iter()
                .find(|e| e["id"] == id)
                .ok_or_else(|| Stop::invalid(id, "补给必须登记全局 runtime 事件"))?;
            if found["kind"] != "runtime" || found["time"] != r["time"] {
                return Err(Stop::invalid(id, "补给与全局事件登记不符"));
            }
        }
        fields(
            &self.raw["initial_state"],
            "anchor warehouse nonwarehouse reachability",
            "initial_state",
        )?;
        let wh = &self.raw["initial_state"]["warehouse"];
        fields(wh, "slots unlisted", "initial_state.warehouse")?;
        if wh["unlisted"] != "empty" {
            return Err(Stop::invalid(
                "initial_state.warehouse.unlisted",
                "任务初始仓库必须显式声明其他物品为空",
            ));
        }
        let rows = wh["slots"]
            .as_array()
            .ok_or_else(|| Stop::invalid("initial_state.warehouse", "缺初始仓库"))?;
        let initial_items: BTreeSet<_> = ["源矿", "蓝铁矿", "荞花", "砂叶", "荞花种子", "砂叶种子"]
            .into_iter()
            .collect();
        let mut got = BTreeSet::new();
        let mut slots = BTreeSet::new();
        let inventory: BTreeSet<_> = seed["inventory"]
            .as_array()
            .ok_or_else(|| Stop::invalid("StateSeed.inventory", "须为数组"))?
            .iter()
            .filter_map(|r| r["slot"].as_str())
            .collect();
        for (index, row) in rows.iter().enumerate() {
            let at = format!("initial_state.warehouse.slots[{index}]");
            fields(row, "slot item quantity empty_identity", &at)?;
            let slot = row["slot"]
                .as_str()
                .filter(|s| !s.is_empty())
                .ok_or_else(|| Stop::invalid(format!("{at}.slot"), "须为非空字符串"))?;
            if !slots.insert(slot)
                || inventory.contains(slot)
                || crate::warehouse::reserved_slot(slot)
            {
                return Err(Stop::invalid(
                    format!("{at}.slot"),
                    "初始仓库标签重复或占用单位格命名域",
                ));
            }
            let quantity = num(&row["quantity"], &at)?;
            if !row["item"].is_null() && !row["item"].is_string() {
                return Err(Stop::invalid(format!("{at}.item"), "须为物品名或 null"));
            }
            if let Some(item) = row["item"].as_str() {
                if !got.insert(item)
                    || quantity != self.catalog.warehouse_capacity
                    || row["empty_identity"]["status"] != "not_applicable"
                {
                    return Err(Stop::invalid(
                        "initial_state.warehouse",
                        "任务初始锚点非每种满仓或重复物种",
                    ));
                }
            } else if quantity != 0
                || row["empty_identity"]["status"] != "specified"
                || !row["empty_identity"]["value"].is_null()
            {
                return Err(Stop::invalid(at, "任务初始额外空格须为零且无历史物种"));
            }
        }
        if got != initial_items {
            return Err(Stop::invalid("initial_state.warehouse", "初始六物种不符"));
        }
        let reachability: Decision = decode(
            self.raw["initial_state"]["reachability"].clone(),
            "initial_state.reachability",
        )?;
        if !["specified", "derived"].contains(&reachability.status.as_str()) {
            return Err(Stop::invalid(
                "initial_state.reachability",
                "条件种子也须给出处说明",
            ));
        }
        reachability.resolved("initial_state.reachability", false)?;
        fields(
            &self.raw["environment"],
            "ore_supply offline product_withdrawal debug_end_event zero_intervention_after_debug",
            "environment",
        )?;
        if self.raw["environment"]["ore_supply"] != "task_continuous_sufficient"
            || self.raw["environment"]["zero_intervention_after_debug"] != true
        {
            return Err(Stop::invalid("environment", "外部过程/阶段前提不符"));
        }
        for key in ["offline", "product_withdrawal"] {
            let required = if key == "offline" {
                "event_domain selected_events"
            } else {
                "policy selected_events"
            };
            fields(&self.raw["environment"][key], required, key)?;
        }
        self.check_action_references()?;
        self.check_event_owners()?;
        let policy = &self.raw["environment"]["product_withdrawal"]["policy"];
        if policy["status"] != "specified" || policy["value"]["schema"] != "withdrawal-policy-v1" {
            return Err(Stop::unsupported(
                "warehouse.withdrawal_policy",
                "environment.product_withdrawal.policy",
                "策略未解或版本未知",
            ));
        }
        if policy["value"]["rules"] == json!([])
            && !policy["value"]["admissibility"]["value"].is_object()
        {
            return Err(Stop::invalid(
                "withdrawal.policy",
                "空策略也须给 no_actions 出处",
            ));
        }
        Ok(())
    }
    /// 内核输入§3.1：反向核全局登记的拥有者；关系、锚点和原因引用本身不拥有事件。
    fn check_event_owners(&self) -> Result<()> {
        let mut owners = std::collections::BTreeMap::<String, (String, String)>::new();
        let mut own = |id: &serde_json::Value, kind: &str, owner: String| -> Result<()> {
            let id = id
                .as_str()
                .filter(|s| !s.is_empty())
                .ok_or_else(|| Stop::invalid(&owner, "拥有者缺事件身份"))?;
            if let Some(previous) = owners.insert(id.into(), (kind.into(), owner.clone())) {
                if previous != (kind.into(), owner) {
                    return Err(Stop::invalid(id, "一个事件被不同记录重复拥有"));
                }
            }
            Ok(())
        };
        for (rows, kind, at) in [
            (
                &self.raw["construction"]["moments"],
                "build",
                "construction.moments",
            ),
            (
                &self.raw["debug_operations"],
                "debug_operation",
                "debug_operations",
            ),
            (
                &self.raw["environment"]["offline"]["selected_events"],
                "offline",
                "offline",
            ),
            (
                &self.raw["environment"]["product_withdrawal"]["selected_events"],
                "withdraw_product",
                "product_withdrawal",
            ),
        ] {
            for (index, row) in rows.as_array().unwrap().iter().enumerate() {
                own(&row["event"], kind, format!("{at}[{index}]"))?;
                if row["action"] == "rebuild" {
                    own(
                        &row["payload"]["remove_event"],
                        "unit_removed",
                        format!("{at}[{index}].remove"),
                    )?;
                    own(
                        &row["payload"]["build_event"],
                        "unit_rebuilt",
                        format!("{at}[{index}].build"),
                    )?;
                }
            }
        }
        own(
            &self.raw["construction"]["complete_event"],
            "blueprint_complete",
            "construction.complete_event".into(),
        )?;
        own(
            &self.raw["environment"]["debug_end_event"],
            "debug_end",
            "environment.debug_end_event".into(),
        )?;
        for (index, row) in self.raw["timeline"]["connection_events"]
            .as_array()
            .unwrap()
            .iter()
            .enumerate()
        {
            let kind = match row["action"].as_str() {
                Some("open") => "connection_open",
                Some("close") => "connection_close",
                _ => return Err(Stop::invalid("connection_events.action", "未知通道动作")),
            };
            own(&row["event"], kind, format!("connection_events[{index}]"))?;
        }
        let supply = self.parameters.value(Axis::WarehouseExternalSupply)?;
        for (index, row) in supply["events"]
            .as_array()
            .into_iter()
            .flatten()
            .enumerate()
        {
            own(&row["event"], "runtime", format!("ore_supply[{index}]"))?;
        }
        let context = &self.raw["initial_state"]["nonwarehouse"]["value"]["semantic_context"];
        for (index, row) in context["pending_events"]["value"]
            .as_array()
            .ok_or_else(|| Stop::invalid("pending_events", "须为已解数组"))?
            .iter()
            .enumerate()
        {
            own(&row["event"], "runtime", format!("pending_events[{index}]"))?;
        }
        for key in ["movements", "internal_passages"] {
            for row in context["tick_context"]["value"][key]
                .as_array()
                .ok_or_else(|| Stop::invalid(key, "须为数组"))?
            {
                // 同一制造判定可拥有多条BC子动作，均引用同一实例。
                own(
                    &row["event"],
                    "runtime",
                    format!("seed_executed:{}", row["event"]),
                )?;
            }
        }
        for event in self.raw["timeline"]["events"].as_array().unwrap() {
            let id = event["id"].as_str().unwrap();
            if owners
                .get(id)
                .is_none_or(|(kind, _)| event["kind"] != *kind)
            {
                return Err(Stop::invalid(
                    format!("timeline.events.{id}"),
                    "全局事件缺对应类型的拥有记录",
                ));
            }
        }
        Ok(())
    }
    /// 内核输入§3.3、§6.1–§6.2：动作只引用其所属全局类型，不能伪装 runtime 绕过停止。
    fn check_action_references(&self) -> Result<()> {
        let events = self.raw["timeline"]["events"].as_array().unwrap();
        let mut owned = BTreeSet::new();
        for (rows, kind, shape, at) in [
            (
                &self.raw["environment"]["offline"]["selected_events"],
                "offline",
                "event new_connection_order effects",
                "environment.offline.selected_events",
            ),
            (
                &self.raw["environment"]["product_withdrawal"]["selected_events"],
                "withdraw_product",
                "event rule action",
                "environment.product_withdrawal.selected_events",
            ),
            (
                &self.raw["debug_operations"],
                "debug_operation",
                "event action target payload when effects",
                "debug_operations",
            ),
        ] {
            for (index, row) in rows
                .as_array()
                .ok_or_else(|| Stop::invalid(at, "须为数组"))?
                .iter()
                .enumerate()
            {
                let location = format!("{at}[{index}]");
                fields(row, shape, &location)?;
                let id = row["event"].as_str().unwrap_or("");
                if !owned.insert(id) || !events.iter().any(|e| e["id"] == id && e["kind"] == kind) {
                    return Err(Stop::invalid(
                        format!("{location}.event"),
                        format!("须唯一引用全局 {kind} 事件"),
                    ));
                }
            }
        }
        for (id, kind, at) in [
            (
                &self.raw["construction"]["complete_event"],
                "blueprint_complete",
                "construction.complete_event",
            ),
            (
                &self.raw["environment"]["debug_end_event"],
                "debug_end",
                "environment.debug_end_event",
            ),
        ] {
            if !events.iter().any(|e| e["id"] == *id && e["kind"] == kind) {
                return Err(Stop::invalid(at, format!("须引用 {kind} 事件")));
            }
        }
        Ok(())
    }
}
