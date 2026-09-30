//! 内核输入§1–§7、受限转移§1：装载支持域、真实排序接口及静态历史检查。
use crate::{catalog::*, config::*, value::*};
use serde_json::Value;
use std::{
    collections::{BTreeMap, BTreeSet},
    path::{Path, PathBuf},
};
#[derive(Clone, Debug)]
pub struct Input {
    pub raw: Value,
    pub path: PathBuf,
    pub catalog: Catalog,
    pub geometry: Geometry,
    pub parameters: Parameters,
    pub connection_times: BTreeMap<String, i64>,
    pub graph: crate::graph::StepGraph,
    pub transfer_timing: BTreeMap<String, String>,
    pub assignments: BTreeMap<String, String>,
    pub switches: BTreeMap<(String, String), bool>,
    pub gate_settings: BTreeMap<String, Value>,
    pub recipe_order: Vec<String>,
    pub slot_order: Vec<String>,
    pub tie_order: Vec<String>,
    pub source_paths: Vec<(String, PathBuf)>,
}
/// 内核输入§5：显式顺序的集合须恰等且无重复。
pub fn permutation(
    actual: &[String],
    expected: impl IntoIterator<Item = String>,
    at: &str,
) -> Result<()> {
    let set: BTreeSet<_> = actual.iter().cloned().collect();
    if set.len() != actual.len() || set != expected.into_iter().collect() {
        return Err(Stop::invalid(at, "顺序须不重不漏覆盖定义域"));
    }
    Ok(())
}
/// 内核输入§3.1：全局事件身份、已解时距及先后图无环。
fn timeline(data: &Value) -> Result<BTreeMap<String, Value>> {
    fields(
        &data["timeline"],
        "events relations connection_events",
        "timeline",
    )?;
    let rows: Vec<Value> = decode(data["timeline"]["events"].clone(), "timeline.events")?;
    let mut events = BTreeMap::new();
    for row in rows {
        fields(&row, "id kind time", "timeline.events[]")?;
        if ![
            "build",
            "debug_operation",
            "offline",
            "blueprint_complete",
            "debug_end",
            "unit_removed",
            "unit_rebuilt",
            "connection_open",
            "connection_close",
            "withdraw_product",
            "runtime",
        ]
        .contains(&row["kind"].as_str().unwrap_or(""))
        {
            return Err(Stop::invalid("timeline.events.kind", "未知事件类型"));
        }
        let id = row["id"]
            .as_str()
            .ok_or_else(|| Stop::invalid("event.id", "须为字符串"))?
            .to_string();
        if id.is_empty() || events.contains_key(&id) {
            return Err(Stop::invalid(&id, "重复或空事件 id"));
        }
        if id.starts_with("E|") {
            return Err(Stop::invalid(&id, "历史占用运行事件保留前缀"));
        }
        if !row["time"].is_null() {
            instant(&row["time"], &id)?;
        }
        events.insert(id, row);
    }
    let mut next: BTreeMap<String, Vec<String>> =
        events.keys().map(|k| (k.clone(), vec![])).collect();
    let mut indegree: BTreeMap<String, usize> = events.keys().map(|k| (k.clone(), 0)).collect();
    let mut relations = data["timeline"]["relations"]
        .as_array()
        .ok_or_else(|| Stop::invalid("timeline.relations", "须为数组"))?
        .clone();
    // 内核输入§3.1：同一个图核所有顺序来源，包含跨中间事件的传递冲突。
    let mut precedes = |a: &Value, b: &Value, at: &str| {
        relations.push(
            serde_json::json!({"before":a,"after":b,"relation":"occurs_before","basis":[at]}),
        );
    };
    if let Some(order) = data["construction"]["selected_order"].as_array() {
        let moments = data["construction"]["moments"]
            .as_array()
            .ok_or_else(|| Stop::invalid("construction.moments", "须为数组"))?;
        let mut previous = None;
        for unit in order {
            let moment = moments
                .iter()
                .find(|m| m["unit"] == *unit)
                .ok_or_else(|| Stop::invalid("construction.selected_order", "建造项缺失"))?;
            if let Some(a) = previous {
                precedes(a, &moment["event"], "construction.selected_order");
            }
            previous = Some(&moment["event"]);
            precedes(
                &moment["event"],
                &data["construction"]["complete_event"],
                "construction.complete_event",
            );
        }
    }
    precedes(
        &data["construction"]["complete_event"],
        &data["environment"]["debug_end_event"],
        "environment.debug_end_event",
    );
    for (rows, at) in [
        (&data["debug_operations"], "debug_operations"),
        (
            &data["environment"]["offline"]["selected_events"],
            "environment.offline.selected_events",
        ),
        (
            &data["environment"]["product_withdrawal"]["selected_events"],
            "environment.product_withdrawal.selected_events",
        ),
    ] {
        let rows = rows
            .as_array()
            .ok_or_else(|| Stop::invalid(at, "须为数组"))?;
        for pair in rows.windows(2) {
            precedes(&pair[0]["event"], &pair[1]["event"], at);
        }
    }
    for row in data["debug_operations"].as_array().unwrap() {
        let at = "debug_operations.when";
        for a in row["when"]["after"]
            .as_array()
            .ok_or_else(|| Stop::invalid(at, "after须为数组"))?
        {
            precedes(a, &row["event"], at);
        }
        for b in row["when"]["before"]
            .as_array()
            .ok_or_else(|| Stop::invalid(at, "before须为数组"))?
        {
            precedes(&row["event"], b, at);
        }
        precedes(&row["event"], &data["environment"]["debug_end_event"], at);
    }
    for row in data["timeline"]["connection_events"]
        .as_array()
        .ok_or_else(|| Stop::invalid("timeline.connection_events", "须为数组"))?
    {
        precedes(
            &row["cause"],
            &row["event"],
            "timeline.connection_events.cause",
        );
    }
    for row in data["environment"]["product_withdrawal"]["selected_events"]
        .as_array()
        .unwrap()
    {
        precedes(
            &data["environment"]["debug_end_event"],
            &row["event"],
            "product_withdrawal.selected_events",
        );
    }
    let supply = &data["parameters"]["fixedness_unproven"]["warehouse.external_supply"]["value"];
    if let Some(rows) = supply["events"].as_array() {
        for pair in rows.windows(2) {
            precedes(
                &pair[0]["event"],
                &pair[1]["event"],
                "warehouse.external_supply.events",
            );
        }
    }
    for r in &relations {
        fields(r, "before after relation basis", "relation")?;
        let a = r["before"].as_str().unwrap_or("");
        let b = r["after"].as_str().unwrap_or("");
        let ea = events
            .get(a)
            .ok_or_else(|| Stop::invalid(a, "关系引用悬空"))?;
        let eb = events
            .get(b)
            .ok_or_else(|| Stop::invalid(b, "关系引用悬空"))?;
        let relation = r["relation"].as_str().unwrap_or("");
        if !["strict", "same_time", "occurs_before"].contains(&relation) {
            return Err(Stop::invalid("relation", "未知先后关系"));
        }
        if ea["time"]["kind"] == "step" && eb["time"]["kind"] == "step" {
            let x = instant(&ea["time"], a)?;
            let y = instant(&eb["time"], b)?;
            if !(match relation {
                "strict" => x < y,
                "same_time" => x == y,
                _ => x <= y,
            }) {
                return Err(Stop::invalid(format!("{a}->{b}"), "实际时刻与关系冲突"));
            }
        }
        if relation != "same_time" {
            next.get_mut(a).unwrap().push(b.into());
            *indegree.get_mut(b).unwrap() += 1;
        }
    }
    let mut ready: Vec<_> = indegree
        .iter()
        .filter(|(_, n)| **n == 0)
        .map(|(k, _)| k.clone())
        .collect();
    let mut count = 0;
    while let Some(a) = ready.pop() {
        count += 1;
        for b in &next[&a] {
            let n = indegree.get_mut(b).unwrap();
            *n -= 1;
            if *n == 0 {
                ready.push(b.clone())
            }
        }
    }
    if count != events.len() {
        return Err(Stop::invalid("timeline.relations", "先后图有环"));
    }
    Ok(events)
}
impl Input {
    /// 内核输入§1–§6：v4 输入严格装载，要求完整参数、状态与步进先后。
    pub fn load(path: &Path, config: &Config) -> Result<Self> {
        Self::parse(read_json(path)?, path, config)
    }
    /// 第五轮K5：内存输入使用显式基目录解析引用，不读取虚拟输入文件。
    pub fn parse_with_base(raw: Value, base_dir: &Path, config: &Config) -> Result<Self> {
        Self::parse(raw, &base_dir.join("memory-input.json"), config)
    }
    /// 内核输入§1–§6：与文件入口共享验证，可用于排列回归和受控试验。
    pub fn parse(raw: Value, path: &Path, config: &Config) -> Result<Self> {
        fields(&raw,"schema purpose catalog timeline layout construction settings parameters initial_state debug_operations environment contract_binding scenario","input")?;
        if raw["schema"] != "kernel-input-v4" {
            return Err(Stop::invalid(
                "schema",
                "历史输入版本，见 数据/样例/历史说明.md",
            ));
        }
        validate_tree(&raw, "input")?;
        if !raw["contract_binding"].is_null() {
            return Err(Stop::unsupported(
                "contract_binding",
                "contract_binding",
                "非空送料映射尚未执行；内核输入§7",
            ));
        }
        let base = path
            .parent()
            .ok_or_else(|| Stop::invalid("input", "路径缺父目录"))?;
        let catref: Reference = decode(raw["catalog"].clone(), "catalog")?;
        let catpath = reference(base, &catref)?;
        let catalog = Catalog::load(&catpath)?;
        let mut source_paths = vec![("catalog".into(), catpath)];
        for source in catalog.raw["sources"]
            .as_array()
            .ok_or_else(|| Stop::invalid("catalog.sources", "缺来源"))?
        {
            let relative = source["path"]
                .as_str()
                .ok_or_else(|| Stop::invalid("catalog.sources", "缺路径"))?;
            let p = catalog
                .path
                .parent()
                .unwrap()
                .join(catalog.raw["source_root"].as_str().unwrap_or("."))
                .join(relative)
                .canonicalize()
                .map_err(|e| Stop::invalid(relative, e.to_string()))?;
            if sha256(&p)? != source["sha256"].as_str().unwrap_or("") {
                return Err(Stop::invalid(relative, "正式源指纹不符"));
            }
            source_paths.push(("formal_source".into(), p));
        }
        let parameters: Parameters = decode(raw["parameters"].clone(), "parameters")?;
        config.validate(&parameters)?;
        let axispath = reference(base, &parameters.axis_registry)?;
        if std::fs::read(&axispath).map_err(|e| Stop::invalid("axis_registry", e.to_string()))?
            != include_bytes!("../../../规格/内核配置-v2.json")
        {
            return Err(Stop::invalid("axis_registry", "配置字节不同于编译时配置"));
        }
        source_paths.push(("axis_registry".into(), axispath));
        if parameters.value(Axis::ConnectionPortMeeting)? != "shared_edge_opposite" {
            return Err(Stop::unsupported(
                "connection.port_meeting",
                "parameters",
                "仅支持共边相反法向",
            ));
        }
        fields(
            &raw["layout"],
            "base id anchor units physical_channels buffer_channels snapshots post_debug",
            "layout",
        )?;
        let geometry = Geometry::build(&raw["layout"], &catalog)?;
        let mut snapshot_ids =
            BTreeSet::from([raw["layout"]["id"].as_str().unwrap_or("").to_string()]);
        for (index, snapshot) in raw["layout"]["snapshots"]
            .as_array()
            .ok_or_else(|| Stop::invalid("layout.snapshots", "须为数组"))?
            .iter()
            .enumerate()
        {
            let at = format!("layout.snapshots[{index}]");
            fields(
                snapshot,
                "id anchor units physical_channels buffer_channels",
                &at,
            )?;
            let id = snapshot["id"]
                .as_str()
                .filter(|s| !s.is_empty())
                .ok_or_else(|| Stop::invalid(format!("{at}.id"), "须为非空字符串"))?;
            if !snapshot_ids.insert(id.to_string()) {
                return Err(Stop::invalid(format!("{at}.id"), "快照标签重复"));
            }
            let mut s = snapshot.clone();
            s["base"] = raw["layout"]["base"].clone();
            Geometry::build(&s, &catalog)?;
        }
        let events = timeline(&raw)?;
        fields(
            &raw["construction"],
            "mode order_domain selected_order moments complete_event",
            "construction",
        )?;
        if raw["construction"]["mode"] != "blueprint_once"
            || raw["construction"]["order_domain"] != "all_rule_consistent_orders"
        {
            return Err(Stop::invalid("construction", "建造史模式非法"));
        }
        for (location, anchor) in [
            ("layout.anchor", &raw["layout"]["anchor"]),
            ("settings.anchor", &raw["settings"]["anchor"]),
            (
                "initial_state.anchor",
                &raw["initial_state"]["anchor"]["value"],
            ),
        ] {
            fields(anchor, "event side", location)?;
            if !events.contains_key(anchor["event"].as_str().unwrap_or(""))
                || !["before", "after"].contains(&anchor["side"].as_str().unwrap_or(""))
            {
                return Err(Stop::invalid(location, "锚点引用或侧非法"));
            }
        }

        let selected: Vec<String> = decode(
            raw["construction"]["selected_order"].clone(),
            "construction.selected_order",
        )?;
        permutation(
            &selected,
            geometry.units.keys().cloned(),
            "construction.selected_order",
        )?;
        let rank: BTreeMap<_, _> = selected
            .iter()
            .enumerate()
            .map(|(i, u)| (u.clone(), i))
            .collect();
        let mut belt = false;
        for u in &selected {
            if geometry.units[u].kind == "传送带" {
                belt = true
            } else if belt {
                return Err(Stop::invalid(
                    "construction.selected_order",
                    "传送带必须在其他单位之后",
                ));
            }
        }
        let mut builds = BTreeMap::new();
        for m in raw["construction"]["moments"]
            .as_array()
            .ok_or_else(|| Stop::invalid("construction.moments", "须为数组"))?
        {
            fields(m, "event unit placement", "construction.moments[]")?;
            let u = m["unit"].as_str().unwrap_or("");
            let e = m["event"].as_str().unwrap_or("");
            if !geometry.units.contains_key(u)
                || !events.contains_key(e)
                || events[e]["kind"] != "build"
                || builds.insert(u.to_string(), e.to_string()).is_some()
            {
                return Err(Stop::invalid("construction.moments", "建成身份非法/重复"));
            }
            for key in [
                "kind",
                "origin",
                "rotation",
                "port_layout",
                "occupied_cells",
            ] {
                if m["placement"][key] != geometry.units[u].raw[key] {
                    return Err(Stop::unsupported(
                        "initialization.debug_actions",
                        u,
                        "当前几何不同于首次建造；须核历史后效",
                    ));
                }
            }
        }
        permutation(
            &builds.keys().cloned().collect::<Vec<_>>(),
            geometry.units.keys().cloned(),
            "construction.moments",
        )?;
        {
            for pair in selected.windows(2) {
                let a = instant(&events[&builds[&pair[0]]]["time"], &pair[0])?;
                let b = instant(&events[&builds[&pair[1]]]["time"], &pair[1])?;
                if a > b {
                    return Err(Stop::invalid(
                        "construction.selected_order",
                        "与建成时刻相反",
                    ));
                }
            }
        }
        let mut connection_times = BTreeMap::new();
        let mut connection_build_ranks = BTreeMap::new();
        for c in raw["timeline"]["connection_events"]
            .as_array()
            .ok_or_else(|| Stop::invalid("connection_events", "须为数组"))?
        {
            fields(
                c,
                "event channel action cause geometry_snapshot construction_basis",
                "connection_event",
            )?;
            let cid = c["channel"].as_str().unwrap_or("");
            let channel = geometry
                .channels
                .get(cid)
                .ok_or_else(|| Stop::invalid(cid, "未知接通边"))?;
            if c["action"] != "open" || connection_times.contains_key(cid) {
                return Err(Stop::unsupported(
                    "connection.order",
                    cid,
                    "运行前多生命段接通史尚需单独重放",
                ));
            }
            let eid = c["event"].as_str().unwrap_or("");
            let e = events
                .get(eid)
                .ok_or_else(|| Stop::invalid(eid, "接通事件缺失"))?;
            let a = &geometry.ports[&channel.source_port].unit;
            let b = &geometry.ports[&channel.target_port].unit;
            let later = if rank[a] > rank[b] { a } else { b };
            let basis: Decision = decode(c["construction_basis"].clone(), cid)?;
            let v = basis.resolved(cid, false)?;
            if v["source_build"] != builds[a]
                || v["target_build"] != builds[b]
                || v["later_build"] != builds[later]
                || c["cause"] != builds[later]
                || e["kind"] != "connection_open"
            {
                return Err(Stop::invalid(cid, "接通记录不来自两端较晚建成"));
            }
            let t = instant(&e["time"], eid)?;
            if t != instant(&events[&builds[later]]["time"], later)? {
                return Err(Stop::invalid(cid, "接通时刻不等于较晚建成时刻"));
            }
            connection_times.insert(cid.to_string(), t);
            connection_build_ranks.insert(cid.to_string(), rank[later]);
        }
        permutation(
            &connection_times.keys().cloned().collect::<Vec<_>>(),
            geometry.channels.keys().cloned(),
            "timeline.connection_events",
        )?;
        // 桥端口恒为双向，接通史只决定通道时刻和轮询次序。
        fields(
            &raw["settings"],
            "anchor switches gates warehouse_assignments",
            "settings",
        )?;
        let mut switches = BTreeMap::new();
        for s in raw["settings"]["switches"]
            .as_array()
            .ok_or_else(|| Stop::invalid("switches", "须为数组"))?
        {
            fields(s, "unit function enabled", "switch")?;
            let u = s["unit"].as_str().unwrap_or("");
            let f = s["function"].as_str().unwrap_or("");
            let unit = geometry
                .units
                .get(u)
                .ok_or_else(|| Stop::invalid(u, "开关引用未知单位"))?;
            if !catalog.kinds[&unit.kind].functions.iter().any(|x| x == f) {
                return Err(Stop::invalid(u, "该单位没有此功能"));
            }
            let enabled = if s["enabled"].is_boolean() {
                s["enabled"].as_bool().unwrap()
            } else {
                let d: Decision = decode(s["enabled"].clone(), "switch.enabled")?;
                d.resolved("switch.enabled", false)?
                    .as_bool()
                    .ok_or_else(|| Stop::invalid(u, "开关须为布尔"))?
            };
            if switches.insert((u.into(), f.into()), enabled).is_some() {
                return Err(Stop::invalid(u, "开关重复"));
            }
        }
        let expected: BTreeSet<_> = geometry
            .units
            .iter()
            .flat_map(|(u, x)| {
                catalog.kinds[&x.kind]
                    .functions
                    .iter()
                    .map(move |f| (u.clone(), f.clone()))
            })
            .collect();
        if switches.keys().cloned().collect::<BTreeSet<_>>() != expected {
            return Err(Stop::invalid("settings.switches", "开关缺失"));
        }
        let mut assignments = BTreeMap::new();
        for a in raw["settings"]["warehouse_assignments"]
            .as_array()
            .ok_or_else(|| Stop::invalid("warehouse_assignments", "须为数组"))?
        {
            fields(a, "port slot", "warehouse_assignment")?;
            let port = a["port"].as_str().unwrap_or("");
            let slot = a["slot"].as_str().unwrap_or("");
            if slot.is_empty()
                || assignments
                    .insert(port.to_string(), slot.to_string())
                    .is_some()
            {
                return Err(Stop::invalid(port, "仓库指派重复/空格标签"));
            }
        }
        let output_ports: Vec<_> = geometry
            .ports
            .iter()
            .filter(|(_, p)| {
                p.role == "output"
                    && ["协议核心", "仓库取货口"].contains(&geometry.units[&p.unit].kind.as_str())
            })
            .map(|(id, _)| id.clone())
            .collect();
        permutation(
            &assignments.keys().cloned().collect::<Vec<_>>(),
            output_ports,
            "warehouse_assignments",
        )?;
        let mut gate_settings = BTreeMap::new();
        for (index, g) in raw["settings"]["gates"]
            .as_array()
            .ok_or_else(|| Stop::invalid("gates", "须为数组"))?
            .iter()
            .enumerate()
        {
            fields(g, "unit item total_limit window_limit", "gate")?;
            if !g["item"].is_null()
                && !g["item"].as_str().is_some_and(|item| {
                    catalog
                        .recipes
                        .values()
                        .any(|r| r.inputs.contains_key(item) || r.outputs.contains_key(item))
                })
            {
                return Err(Stop::invalid(
                    format!("settings.gates[{index}].item"),
                    "须为目录物品名或 null",
                ));
            }
            let uid = g["unit"].as_str().unwrap_or("");
            if !geometry
                .units
                .get(uid)
                .is_some_and(|u| u.kind == "物品准入口")
                || gate_settings.insert(uid.into(), g.clone()).is_some()
            {
                return Err(Stop::invalid(uid, "准入口设置重复或单位不符"));
            }
            for (f, limit) in [
                (
                    "total_limit",
                    num(
                        &catalog.raw["units"]
                            .as_array()
                            .unwrap()
                            .iter()
                            .find(|r| r["id"] == "物品准入口")
                            .unwrap()["settings"]["total_limit"]["max"],
                        "total_limit.max",
                    )?,
                ),
                (
                    "window_limit",
                    num(
                        &catalog.raw["units"]
                            .as_array()
                            .unwrap()
                            .iter()
                            .find(|r| r["id"] == "物品准入口")
                            .unwrap()["settings"]["window_limit"]["max"],
                        "window_limit.max",
                    )?,
                ),
            ] {
                if !g[f].is_null() {
                    let n = num(&g[f], f)?;
                    if g["item"].is_null() || n < 1 || n > limit {
                        return Err(Stop::invalid(uid, "准入口限额/身份非法"));
                    }
                }
            }
        }
        permutation(
            &gate_settings.keys().cloned().collect::<Vec<_>>(),
            geometry
                .units
                .iter()
                .filter(|(_, u)| u.kind == "物品准入口")
                .map(|(u, _)| u.clone()),
            "settings.gates",
        )?;
        let mut result = Self {
            raw,
            path: path.to_path_buf(),
            catalog,
            geometry,
            parameters,
            connection_times,
            graph: crate::graph::StepGraph::default(),
            transfer_timing: BTreeMap::new(),
            assignments,
            switches,
            gate_settings,
            recipe_order: vec![],
            slot_order: vec![],
            tie_order: vec![],
            source_paths,
        };
        result.validate_runtime_interfaces()?;
        // 一步内仍逐个建成；只有同一次建成引起的通道才真正并列。
        let mut previous_build = BTreeMap::new();
        for ch in &result.tie_order {
            let build = connection_build_ranks[ch];
            if previous_build
                .insert(result.connection_times[ch], build)
                .is_some_and(|previous| previous > build)
            {
                return Err(Stop::new(
                    "invalid_input",
                    "connection.tie",
                    ch,
                    "同一步内不同建成引起的通道次序须与 construction.selected_order 一致",
                ));
            }
        }
        result.check_input_axes()?;
        result.transfer_timing = result.parameters.value(Axis::TransferTiming)?["values"]
            .as_array()
            .unwrap()
            .iter()
            .map(|r| {
                (
                    r["unit"].as_str().unwrap().to_string(),
                    r["timing"].as_str().unwrap().to_string(),
                )
            })
            .collect();
        result.graph = crate::graph::StepGraph::build(&result)?;
        Ok(result)
    }
    /// 内核输入§5.2–§5.4：接口对象形状与全序必须完整。
    fn validate_runtime_interfaces(&mut self) -> Result<()> {
        let read_order = |axis: Axis, key: &str| -> Result<Vec<String>> {
            let v = self.parameters.value(axis)?;
            fields(v, &format!("kind {key}"), axis.name())?;
            if v["kind"] != "explicit_order" {
                return Err(Stop::unsupported(axis.name(), axis.name(), "缺显式全序"));
            }
            decode(v[key].clone(), axis.name())
        };
        self.tie_order = read_order(Axis::ConnectionTie, "channels")?;
        permutation(
            &self.tie_order,
            self.geometry.channels.keys().cloned(),
            "connection.tie",
        )?;
        self.recipe_order = read_order(Axis::ManufacturingRecipeSelection, "recipes")?;
        permutation(
            &self.recipe_order,
            self.catalog.recipes.keys().cloned(),
            "manufacturing.recipe_selection",
        )?;
        self.slot_order = read_order(Axis::ManufacturingInputSlotSelection, "slots")?;
        let cap = self.catalog.slots(
            &self.geometry.units,
            self.parameters
                .value(Axis::BridgeCapacity)?
                .as_i64()
                .ok_or_else(|| Stop::invalid("bridge.capacity", "须为整数"))?,
        )?;
        permutation(
            &self.slot_order,
            cap.keys()
                .filter(|s| s.split(':').nth(1) == Some("input"))
                .cloned(),
            "manufacturing.input_slot_selection",
        )?;
        for (a, want) in [
            (Axis::ConnectionBuildOrder, "construction.selected_order"),
            (Axis::ConnectionOrder, "timeline_connection_history"),
        ] {
            if self.parameters.value(a)? != want {
                return Err(Stop::unsupported(a.name(), a.name(), "历史接口未实现"));
            }
        }
        Ok(())
    }
}
