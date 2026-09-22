//! 内核输出§1–§3：来源闭合、逐轴五态、全状态及规范检查点增量。
use crate::{
    catalog::sha256,
    config::{Axis, Config, Disposition},
    engine::Engine,
    input::Input,
    value::*,
};
use serde_json::{json, Value};
use std::{
    collections::{BTreeMap, BTreeSet},
    path::{Path, PathBuf},
};
/// 内核输出§2.1：对象同键递归；数组及变键对象整字段替换，路径不穿数组。
pub fn delta(before: &Value, after: &Value) -> Result<Vec<Value>> {
    /// 内核输出§2.1：UTF-8 字节键序的深度优先规范增量。
    fn walk(a: &Value, b: &Value, path: &mut Vec<String>, out: &mut Vec<Value>) -> Result<()> {
        if a == b {
            return Ok(());
        }
        if let (Some(x), Some(y)) = (a.as_object(), b.as_object()) {
            if x.keys().eq(y.keys()) {
                for (k, v) in x {
                    path.push(k.clone());
                    walk(v, &y[k], path, out)?;
                    path.pop();
                }
                return Ok(());
            }
        }
        if path.is_empty() {
            return Err(Stop::invalid("delta", "禁止根替换"));
        }
        out.push(json!({"op":"replace","path":path,"value":b}));
        Ok(())
    }
    let mut result = Vec::new();
    walk(before, after, &mut vec![], &mut result)?;
    Ok(result)
}
/// 内核输出§2.1：连续重建并核规范差分，拒绝重复/祖先冲突及无变化替换。
pub fn apply_delta(before: &Value, ops: &[Value]) -> Result<Value> {
    let mut after = before.clone();
    for op in ops {
        fields(op, "op path value", "delta.operation")?;
        if op["op"] != "replace" {
            return Err(Stop::invalid("delta.op", "仅支持 replace"));
        }
        let path: Vec<String> = decode(op["path"].clone(), "delta.path")?;
        if path.is_empty() || path.iter().any(String::is_empty) {
            return Err(Stop::invalid("delta.path", "路径为空"));
        }
        let mut node = &mut after;
        for key in &path {
            node = node
                .as_object_mut()
                .and_then(|o| o.get_mut(key))
                .ok_or_else(|| Stop::invalid("delta.path", "路径须沿已有对象键；不得穿数组"))?;
        }
        *node = op["value"].clone();
    }
    if delta(before, &after)? != ops {
        return Err(Stop::invalid("delta", "增量不规范或有路径冲突"));
    }
    Ok(after)
}
/// 内核输出§2.1：检查点索引及末尾残段同样重建。
pub fn decode_trace(trace: &Value) -> Result<Value> {
    if trace["format"] == "full_state_each_instant" {
        return Ok(trace.clone());
    }
    if trace["format"] != "checkpoint_delta" || trace["delta_encoding"] != "object_replace_v1" {
        return Err(Stop::invalid("trace.format", "未知轨迹格式"));
    }
    let k = trace["checkpoint_interval"]
        .as_u64()
        .filter(|n| *n > 0)
        .ok_or_else(|| Stop::invalid("checkpoint_interval", "须正整数"))? as usize;
    let mut result = trace.clone();
    let rows = result["ticks"]
        .as_array_mut()
        .ok_or_else(|| Stop::invalid("trace.ticks", "须为数组"))?;
    let mut previous = trace["start_state"].clone();
    for (i, row) in rows.iter_mut().enumerate() {
        if i % k == 0 {
            if row.get("state").is_none() || row.get("delta").is_some() {
                return Err(Stop::invalid(format!("ticks[{i}]"), "检查点须为全状态"));
            }
            previous = row["state"].clone();
        } else {
            if row.get("state").is_some() {
                return Err(Stop::invalid(format!("ticks[{i}]"), "非检查点禁止全状态"));
            }
            let ops: Vec<Value> = decode(row["delta"].clone(), "delta")?;
            previous = apply_delta(&previous, &ops)?;
            row.as_object_mut().unwrap().remove("delta");
            row["state"] = previous.clone();
        }
    }
    let o = result.as_object_mut().unwrap();
    o.remove("checkpoint_interval");
    o.remove("delta_encoding");
    o.insert("format".into(), json!("full_state_each_instant"));
    Ok(result)
}
/// 内核输出§1：参数投影只在确实消费时登记，来源和逐轴值不得漂移。
pub fn validate_projection(path: &Path, input: &Input, config: &Config) -> Result<()> {
    let p = read_json(path)?;
    fields(
        &p,
        "schema profile_id profile_source configuration_source axis_source axes",
        "parameter_projection",
    )?;
    if p["schema"] != "profile-assignment-v2" || p["profile_id"] != config.profile_id {
        return Err(Stop::invalid("parameter_projection", "版本/配置名不符"));
    }
    for key in ["profile_source", "configuration_source", "axis_source"] {
        let r = decode(p[key].clone(), key)?;
        crate::catalog::reference(path.parent().unwrap(), &r)?;
    }
    let mut seen = BTreeSet::new();
    for row in p["axes"]
        .as_array()
        .ok_or_else(|| Stop::invalid("projection.axes", "须为数组"))?
    {
        fields(
            row,
            "axis decision disposition coverage_loss",
            "projection.axes[]",
        )?;
        let a: Axis = decode(row["axis"].clone(), "axis")?;
        let conf = &config.axes[&a];
        let current = input.parameters.current();
        if !seen.insert(a)
            || row["decision"] != current[a.name()].0
            || row["disposition"] != json!(conf.disposition)
            || row["coverage_loss"] != conf.coverage_loss
        {
            return Err(Stop::invalid(a.name(), "投影值/处置/覆盖损失不符"));
        }
    }
    if seen.len() != config.axes.len() {
        return Err(Stop::invalid("projection.axes", "轴未覆盖"));
    }
    Ok(())
}
/// 内核输出§1：指纹覆盖本次实现、配置、正式源、语义及实际消费的投影/黄金。
pub fn fingerprints(
    input: &Input,
    config_path: &Path,
    extra: &[(String, PathBuf)],
) -> Result<Vec<Value>> {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .map_err(|e| Stop::invalid("root", e.to_string()))?;
    let mut paths = vec![
        ("input".into(), input.path.clone()),
        ("profile".into(), config_path.to_path_buf()),
    ];
    paths.extend(input.source_paths.clone());
    paths.push(("profile".into(), root.join("规格/受限模型声明.md")));
    for p in [
        "受限转移定义.md",
        "运行语义.md",
        "内核输入.md",
        "内核输出.md",
    ] {
        paths.push(("semantics".into(), root.join("规格").join(p)));
    }
    paths.push(("schema".into(), root.join("规格/内核输出.schema.json")));
    paths.push(("semantics".into(), root.join("crates/kernel/周期键读取审计.md")));
    for p in [
        "value.rs",
        "config.rs",
        "model.rs",
        "catalog.rs",
        "input.rs",
        "interfaces.rs",
        "engine.rs",
        "event_identity.rs",
        "warehouse.rs",
        "polling.rs",
        "transition.rs",
        "output.rs",
        "ledger.rs",
        "cycle.rs",
        "cycle_io.rs",
        "digest.rs",
        "seed.rs",
        "cache.rs",
        "lib.rs",
        "main.rs",
    ] {
        paths.push(("checker".into(), root.join("crates/kernel/src").join(p)));
    }
    for p in ["Cargo.toml", "Cargo.lock", "crates/kernel/Cargo.toml"] {
        paths.push(("checker".into(), root.join(p)));
    }
    paths.extend(extra.iter().cloned());
    let mut result = Vec::new();
    let mut seen = BTreeSet::new();
    for (role, p) in paths {
        let path = p
            .canonicalize()
            .map_err(|e| Stop::invalid(p.display().to_string(), e.to_string()))?;
        if !seen.insert((role.clone(), path.clone())) {
            continue;
        }
        result.push(json!({"role":role,"path":path,"sha256":sha256(&path)?}));
    }
    Ok(result)
}
/// 输出§5.1：单个输入及固定参数的工程证据，证明义务随证书另列。
pub(crate) fn evidence_scope(kind: &str, direction: &str, sources: &[Value]) -> Value {
    json!({
        "kind":kind,
        "support_domain":["固定布局、设定、global/event-order-v1及整数时钟的受限工程执行",
            "ordered_sweeps与retain_survivors为明示工程组织；一般失败环真实唤醒对应仍待证明"],
        "fixed_parameter_lifecycle":"judgment.order_scope=fixed_run_order；judgment.order整场固定，回放和端点逐值核对；本段无离线或玩家动作",
        "context_bindings":sources.iter().map(|r| json!({"path":r["path"],"sha256":r["sha256"]})).collect::<Vec<_>>(),
        "initial_state_coverage":{"description":"一个显式种子及其实际已重放前缀；调试程序全部可能后态另核","exact_reachable_set_enumerated":false},
        "direction":direction,"review_status":"author_checked","proof_sources":[]
    })
}
/// 内核输出§1：五态按这次实际记录分开；赋值不等于触发。
pub fn coverage(config: &Config, ticks: &[Value], input: &Input) -> Vec<Value> {
    let mut phases = manufacturing_phases(input);
    let mut manufacturing = BTreeMap::new();
    for tick in ticks {
        manufacturing_evidence(tick, input, &mut phases, &mut manufacturing);
    }
    coverage_with_manufacturing(config, ticks, input, &manufacturing)
}
/// 内核输出§1：流式增量输出也使用编码前取得的逐轴制造证据。
fn coverage_with_manufacturing(
    config: &Config,
    ticks: &[Value],
    input: &Input,
    manufacturing: &BTreeMap<String, Vec<String>>,
) -> Vec<Value> {
    let events: Vec<_> = ticks
        .iter()
        .flat_map(|t| t["events"].as_array().into_iter().flatten())
        .collect();
    let evidence = |op: &str, out: &str| -> Vec<String> {
        events
            .iter()
            .filter(|e| e["operation"] == op && (out.is_empty() || e["outcome"] == out))
            .filter_map(|e| e["event"].as_str().map(str::to_string))
            .collect()
    };
    let moves = evidence("move", "success");
    let complete = evidence("manufacture_complete", "");
    let transfer: Vec<_> = events
        .iter()
        .filter(|e| {
            e["operation"] == "transfer"
                && ["success", "failure"].contains(&e["outcome"].as_str().unwrap_or(""))
        })
        .filter_map(|e| e["event"].as_str().map(str::to_string))
        .collect();
    let expiry = evidence("gate_window_expiry", "");
    config.axes.iter().map(|(axis,row)|{let name=axis.name();let(mut status,mut ev)=("not_exercised",vec!["本次未记录该机制实际后效；参数赋值不等于覆盖。".to_string()]);
        if (name.starts_with("time.")||["judgment.order","judgment.order_scope","polling.dual_permission","polling.memory_scope","polling.eligibility_stage"].contains(&name))&&!moves.is_empty(){status="exercised";ev=moves.clone();}
        if name=="time.manufacture_events"{if !complete.is_empty(){status="exercised";ev=complete.clone()}else{status="not_exercised";ev=vec!["本次没有制造完成".into()]}}
        if let Some(ids)=manufacturing.get(name){if !ids.is_empty(){status="exercised";ev=ids.clone();}}
        if ["connection.build_order","connection.order","connection.tie","connection.port_meeting","connection.belt_shape","initialization.warehouse_anchor","initialization.other_inventory","initialization.switches","initialization.build_timing","initialization.debug_end","warehouse.capacity","power.cell_rule","polling.initial_cursor","polling.direct_peer"].contains(&name){status="input_checked";ev=vec!["本次输入/目录/种子检查；单一历史不证明全称可达性。".into()];}
        if ["polling.both_failure","polling.ungraded_blocked"].contains(&name){let ids=evidence("move","failure");if !ids.is_empty(){status="exercised";ev=ids;}}
        if name=="polling.level_tie"{let ids:Vec<_>=events.iter().filter(|e|e["basis"].as_array().is_some_and(|b|b.iter().any(|s|s.as_str().is_some_and(|s|s.starts_with("polling.level_tie="))))).filter_map(|e|e["event"].as_str().map(str::to_string)).collect();if !ids.is_empty(){status="exercised";ev=ids;}}
        if name.starts_with("transfer.")&&!transfer.is_empty()&&!["transfer.pause","transfer.resume_event"].contains(&name){status="exercised";ev=transfer.clone();}
        if name=="transfer.pause" {
            let paused:Vec<_>=input.raw["initial_state"]["nonwarehouse"]["value"]["progress"].as_array().into_iter().flatten().filter(|p|p["cooldowns"].as_array().is_some_and(|c|!c.is_empty()&&instant(&c[0]["remaining"],"cooldown").is_ok_and(|n|n>0))).filter_map(|p|p["unit"].as_str()).filter(|u|!input.geometry.powered.contains(*u)||input.switches.get(&(u.to_string(),"transfer".into()))!=Some(&true)).collect();
            let ids:Vec<_>=events.iter().filter(|e|e["operation"]=="transfer"&&e["detail"]=="function_disabled"&&paused.contains(&e["target"].as_str().unwrap_or(""))).filter_map(|e|e["event"].as_str().map(str::to_string)).collect();
            if !ids.is_empty(){status="exercised";ev=ids;}
        }
        if name=="transfer.resume_event"{status="not_exercised";ev=vec!["运行段开关/供电固定，暂停后重新启用需未支持的调试或离线后效；未以普通冷却到期冒领。".into()];}
        if ["gate.concurrent_expiry","gate.window_clock","gate.window_recovery","gate.reconnect_record","polling.membership_change"].contains(&name)&&!expiry.is_empty(){status="exercised";ev=expiry.clone();}
        if name.starts_with("polling.split_merge"){let ids:Vec<_>=events.iter().filter(|e|e["operation"]=="move"&&["success","failure"].contains(&e["outcome"].as_str().unwrap_or(""))).filter(|e|input.geometry.channels.get(e["target"].as_str().unwrap_or("")).is_some_and(|c|input.geometry.units[&input.geometry.ports[&c.source_port].unit].kind=="分流器"||input.geometry.units[&input.geometry.ports[&c.target_port].unit].kind=="汇流器")).filter_map(|e|e["event"].as_str().map(str::to_string)).collect();if !ids.is_empty(){status="exercised";ev=ids;}}
        if name=="connection.bridge_first_contact" && input.geometry.units.values().any(|u|u.kind=="桥接器") {
            status="input_checked";
            ev=vec!["仅校验输入中已解桥方向及先接历史；运行段不执行建造/先接定向，后续搬运不构成定向事件。".into()];
        }
        if name.starts_with("bridge.") {
            let ids:Vec<_>=events.iter().filter(|e|e["operation"]=="move"&&e["outcome"]=="success").filter(|e|input.geometry.channels.get(e["target"].as_str().unwrap_or("")).is_some_and(|c|[&c.source_port,&c.target_port].iter().any(|p|input.geometry.units[&input.geometry.ports[*p].unit].kind=="桥接器"))).filter_map(|e|e["event"].as_str().map(str::to_string)).collect();
            if !ids.is_empty(){status="exercised";ev=ids;}
        }
        if ["damping.branch","damping.belt_component_rule"].contains(&name){
            let ids:Vec<_>=events.iter().filter(|e|e["basis"].as_array().is_some_and(|a|a.iter().any(|b|b.as_str().is_some_and(|s|s.strip_prefix("damping.evaluated:").is_some_and(|list|list.split(';').any(|part|part.starts_with(if name=="damping.branch" {"branch:"}else{"belt_component:"}))))))).filter_map(|e|e["event"].as_str().map(str::to_string)).collect();
            if !ids.is_empty(){status="exercised";ev=ids;}
        }
        if name=="damping.belt_adjacency"{status="not_exercised";ev=vec!["本版path_runs只计路径连续带串，不调用geometric_components的几何邻接轴。".into()];}
        if ["manufacturing.input_mixing","manufacturing.input_capacity_scope","manufacturing.port_slot_relation","manufacturing.input_slot_selection","manufacturing.empty_slot_identity"].contains(&name){
            let ids:Vec<_>=events.iter().filter(|e|e["operation"]=="move"&&e["outcome"]=="success").filter(|e|input.geometry.channels.get(e["target"].as_str().unwrap_or("")).is_some_and(|c|input.catalog.kinds[&input.geometry.units[&input.geometry.ports[&c.target_port].unit].kind].family=="manufacturing")).filter_map(|e|e["event"].as_str().map(str::to_string)).collect();
            if !ids.is_empty(){status="exercised";ev=ids;}
        }
        if ["warehouse.delivery_count","warehouse.empty_slot_identity","warehouse.external_supply"].contains(&name){
            let flows=if name=="warehouse.external_supply"{vec!["external_supply"]}else{vec!["core_inbound","wireless_inbound"]};
            let ids:Vec<_>=ticks.iter().flat_map(|t|flows.iter().flat_map(move |f|t["warehouse_ledger"][*f].as_array().into_iter().flatten())).filter_map(|r|r["event"].as_str().map(str::to_string)).collect();
            if !ids.is_empty(){status="exercised";ev=ids;}
        }
        if row.disposition==Disposition::Stop{status="stop_not_triggered";ev=vec!["所请求的有限前缀未触及停止域，不证明该域后效。".into()];}
        if ["gate.identity_recovery","gate.total_recovery","gate.identity_subject","polling.membership_change"].contains(&name){let ids=evidence("gate_identity_maintenance","");if !ids.is_empty(){status="exercised";ev=ids;}}
        if name=="warehouse.periodic_lift"{status="proof_pending";ev=vec!["具体完整周期复原及全称覆盖分别待证；当前接口生成受限生产诊断。".into()];}
        json!({"axis":name,"reason":row.coverage_loss,"disposition":row.disposition,"coverage_status":status,"evidence":ev,"other_values":if row.disposition==Disposition::Fixed{"已定域无其它值；未执行结构仍未验证"}else{"其它值及其联合组合未覆盖"}})
    }).collect()
}
/// 内核输出§1、受限转移§4.2：由子动作账与判前批次阶段逐轴取证，完成分支不能借开工冒领。
fn manufacturing_evidence(
    tick: &Value,
    input: &Input,
    phases: &mut BTreeMap<String, String>,
    result: &mut BTreeMap<String, Vec<String>>,
) {
    let passages = tick["state"]["semantic_context"]["tick_context"]["value"]["internal_passages"]
        .as_array()
        .unwrap();
    for event in tick["events"].as_array().unwrap() {
        let Some(uid) = event["target"].as_str() else {
            continue;
        };
        if event["operation"] == "manufacture_complete" {
            phases.insert(uid.into(), "completed".into());
        }
        if event["operation"] != "manufacture" {
            continue;
        }
        let id = event["event"].as_str().unwrap();
        let phase = phases.get_mut(uid).unwrap();
        let output = passages.iter().any(|p| {
            p["event"] == id
                && p["channel"]
                    .as_str()
                    .is_some_and(|c| c.starts_with(&format!("BC|{uid}:buffer:")))
        });
        let intake = passages.iter().any(|p| {
            p["event"] == id
                && p["channel"]
                    .as_str()
                    .is_some_and(|c| c.starts_with(&format!("BC|{uid}:input:")))
        });
        let mut axes = Vec::new();
        if *phase == "completed" {
            axes.push("manufacturing.output_blocked");
        }
        if output {
            *phase = "idle".into();
        }
        if intake {
            axes.extend([
                "manufacturing.recipe_match_scope",
                "manufacturing.recipe_completeness",
                "manufacturing.recipe_quantity_match",
                "manufacturing.recipe_extra_items",
                "manufacturing.recipe_selection",
                "manufacturing.recipe_lock_time",
                "manufacturing.input_collection",
            ]);
            *phase = "intake".into();
        }
        if output || intake {
            axes.extend([
                "manufacturing.buffer_power_gate",
                "judgment.buffer_event_class",
                "cascade.buffer",
            ]);
        }
        if *phase == "intake"
            && input.geometry.powered.contains(uid)
            && input.switches.get(&(uid.into(), "manufacture".into())) == Some(&true)
        {
            *phase = "working".into();
        }
        for axis in axes {
            result.entry(axis.into()).or_default().push(id.into());
        }
    }
}
/// 内核输出§1：制造分支取证从给定种子阶段起算，不能假定全部 idle。
fn manufacturing_phases(input: &Input) -> BTreeMap<String, String> {
    input.raw["initial_state"]["nonwarehouse"]["value"]["progress"]
        .as_array()
        .unwrap()
        .iter()
        .map(|p| {
            (
                p["unit"].as_str().unwrap().into(),
                p["phase"].as_str().unwrap().into(),
            )
        })
        .collect()
}
/// 内核输出§1–§2.1：逐刻读取引擎快照，增量模式仅保留上一状态作编码。
pub fn run_record(
    mut engine: Engine,
    config: &Config,
    config_path: &Path,
    ticks: usize,
    format: &str,
    interval: usize,
) -> Result<Value> {
    if !["full_state_each_instant", "checkpoint_delta"].contains(&format) || interval == 0 {
        return Err(Stop::invalid("format", "格式或检查点间隔非法"));
    }
    let start = json!(engine.state);
    let mut previous = start.clone();
    let mut rows = Vec::new();
    let mut acceptance = Vec::new();
    let mut manufacturing = BTreeMap::<String, Vec<String>>::new();
    let mut phases = manufacturing_phases(&engine.input);
    let mut stop = None;
    for index in 0..ticks {
        match engine.step(true) {
            Ok(Some(mut t)) => {
                acceptance.push(
                    serde_json::to_string(&engine.acceptance_report()?)
                        .map_err(|e| Stop::invalid("warehouse.acceptance", e.to_string()))?,
                );
                // 增量编码前取证，完整tick本身及黄金/差分对象保持不变。
                manufacturing_evidence(&t, &engine.input, &mut phases, &mut manufacturing);
                if format == "checkpoint_delta" {
                    let current = t.as_object_mut().unwrap().remove("state").unwrap();
                    if index % interval == 0 {
                        t["state"] = current.clone();
                    } else {
                        t["delta"] = json!(delta(&previous, &current)?);
                    }
                    previous = current;
                }
                rows.push(t)
            }
            Ok(None) => return Err(Stop::invalid("output", "记录被意外关闭")),
            Err(e) => {
                stop = Some(e);
                break;
            }
        }
    }
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
    let sample = root.join("数据/样例");
    let mut extra = Vec::new();
    let mut golden_match = false;
    for (name, projection) in [
        ("混做粉碎机两下游.json", "kernel_profile_v1参数赋值.json"),
        ("分流器三路轮询.json", "分流器三路轮询-参数赋值.json"),
    ] {
        if engine.input.path.canonicalize().ok() == sample.join(name).canonicalize().ok() {
            validate_projection(&sample.join(projection), &engine.input, config)?;
            extra.push(("parameter_projection".into(), sample.join(projection)));
        }
    }
    if engine.input.path.canonicalize().ok()
        == sample.join("混做粉碎机两下游.json").canonicalize().ok()
        && rows.len() == 4
        && stop.is_none()
    {
        let p = sample.join("混做粉碎机两下游-黄金轨迹.json");
        let golden = read_json(&p)?;
        let summaries: Vec<_> = rows.iter().map(|t| t["summary"].clone()).collect();
        if json!(summaries) != golden["ticks"] {
            return Err(Stop::invalid("golden.ticks", "黄金轨迹逐字段不同"));
        }
        golden_match = true;
        extra.push(("golden".into(), p));
        extra.push(("golden".into(), sample.join("混做粉碎机两下游-黄金轨迹.md")));
    }
    let mut uncovered = coverage_with_manufacturing(config, &rows, &engine.input, &manufacturing);
    for row in &mut uncovered {
        if ["warehouse.acceptance", "warehouse.acceptance_quantifier"]
            .contains(&row["axis"].as_str().unwrap_or(""))
            && !acceptance.is_empty()
        {
            row["coverage_status"] = json!("exercised");
            row["evidence"] = json!(acceptance);
        }
    }
    if let Some(stop) = &stop {
        for row in &mut uncovered {
            if row["axis"] == stop.axis {
                row["coverage_status"] = json!(if stop.axis == "warehouse.periodic_lift" {
                    "proof_pending"
                } else {
                    "input_checked"
                });
                row["evidence"] = json!([stop.to_string()]);
            }
        }
    }
    let completed = rows
        .iter()
        .flat_map(|t| t["events"].as_array().into_iter().flatten())
        .filter(|e| e["operation"] == "manufacture_complete")
        .count() as i64;
    let end = rows
        .last()
        .map(|t| t["time"].clone())
        .unwrap_or(start["environment"]["time"].clone());
    let from = rows
        .first()
        .map(|t| t["time"].clone())
        .unwrap_or(start["environment"]["time"].clone());
    let mut trace = json!({"start_state":start,"ticks":rows,"end_time":end,"format":format});
    if format == "checkpoint_delta" {
        trace["checkpoint_interval"] = json!(interval);
        trace["delta_encoding"] = json!("object_replace_v1");
    }
    let status = stop
        .as_ref()
        .map(|s| s.status.as_str())
        .unwrap_or("completed");
    let mut open = vec![
        "有限轨迹不证明全称参数、初态可达性、全部可达循环或目标。".into(),
        "规格疑问见 求解器/规格/内核实现-对规格的疑问.md。".into(),
    ];
    if let Some(e) = &stop {
        open.push(e.to_string());
    }
    let sources = fingerprints(&engine.input,config_path,&extra)?;
    let scope = evidence_scope("diagnostic", "diagnostic", &sources);
    Ok(
        json!({"schema":"kernel-output-v4","evidence_scope":scope,"execution_mode":if engine.production_abstraction {"production_abstraction"}else{"finite_concrete"},"port_meeting":engine.input.parameters.value(Axis::ConnectionPortMeeting)?,"run_id":format!("kernel:{}:{}:{}",engine.input.path.file_stem().and_then(|s|s.to_str()).unwrap_or("input"),from["value"]["value"].as_str().unwrap_or("?"),ticks),"profile_id":config.profile_id,"producer":{"kind":"kernel","path":root.join("crates/kernel/src/lib.rs").canonicalize().map_err(|e|Stop::invalid("producer",e.to_string()))?,"claim":"Rust 受限内核的有限条件轨迹；不作全称或完整目标认证"},"status":status,"fingerprints":sources,"parameter_assignment":engine.input.raw["parameters"],"input_history":{"timeline":engine.input.raw["timeline"],"construction":engine.input.raw["construction"],"debug_operations":engine.input.raw["debug_operations"],"environment":engine.input.raw["environment"],"reachability":engine.input.raw["initial_state"]["reachability"]},"uncovered_axes":uncovered,"trace":trace,"validation_scope":json!({"kind":"finite_trace","from":from,"through":end,"golden_match":golden_match,"initial_history":"conditional_witness","universal_parameters":false,"all_reachable_cycles":false,"target_certified":false,"manufacturing_cycles_completed":q(completed)}),"open_items":open}),
    )
}
/// 内核输出§1：装载失败不制造非法的“完整参数/轨迹”对象。
pub fn stopped_record(stop: &Stop) -> Value {
    json!({"schema":"kernel-output-v4","evidence_scope":evidence_scope("diagnostic","diagnostic", &[]),"execution_mode":"finite_concrete","port_meeting":"shared_edge_opposite","run_id":"kernel:load-stop","profile_id":"kernel_profile_v1","producer":{"kind":"kernel","path":concat!(env!("CARGO_MANIFEST_DIR"),"/src/lib.rs"),"claim":"装载停止，未形成游戏后继"},"status":stop.status,"fingerprints":[],"parameter_assignment":null,"input_history":null,"uncovered_axes":[],"trace":null,"validation_scope":null,"open_items":[stop.to_string()]})
}
/// 输出§2/§5.3：独立检查完整前缀的注册、单次消费和时序，普通与周期验收共用。
pub(crate) fn verify_record_events(record: &Value, input: &Input) -> Result<()> {
    if record["trace"].is_null() && record["status"] != "completed" {
        return Ok(());
    }
    let decoded = decode_trace(&record["trace"])?;
    let mut previous = decoded["start_state"].clone();
    for tick in decoded["ticks"]
        .as_array()
        .ok_or_else(|| Stop::invalid("trace.ticks", "须为数组"))?
    {
        crate::ledger::verify_tick(&previous, tick)?;
        previous = tick["state"].clone();
    }
    crate::event_identity::validate_event_identity(
        input,
        &decoded["start_state"],
        decoded["ticks"]
            .as_array()
            .ok_or_else(|| Stop::invalid("trace.ticks", "须为数组"))?,
    )
}
/// 内核输出§1：只规范属于记录的来源路径，输入内的参数路径仍保持原输入表示。
pub fn canonical_record(record: &Value, base: &Path) -> Result<Value> {
    let mut canonical = record.clone();
    crate::cycle_io::canonical_fingerprints(&mut canonical, base)?;
    crate::cycle_io::canonical_proof_sources(&mut canonical, base)?;
    canonical["producer"]["path"] = json!(crate::cycle_io::resolved(
        base,
        &record["producer"]["path"],
        "producer.path"
    )?);
    Ok(canonical)
}
/// 内核输出§1：记录输入来源相对记录所在目录，禁止依赖调用者cwd。
pub fn record_input_path(record: &Value, base: &Path) -> Result<PathBuf> {
    let source = record["fingerprints"]
        .as_array()
        .and_then(|rows| rows.iter().find(|row| row["role"] == "input"))
        .ok_or_else(|| Stop::invalid("fingerprints", "缺输入来源"))?;
    crate::cycle_io::resolved(base, &source["path"], "fingerprints.input.path")
}
/// 内核输出§3：内存记录兼容入口；相对路径基目录为当前目录。
pub fn verify_record(
    record: &Value,
    input: Input,
    config: &Config,
    config_path: &Path,
) -> Result<()> {
    verify_record_at(record, input, config, config_path, Path::new("."))
}
/// 内核输出§1/§3：核原始来源字节后规范路径，再严格比较重算的完整记录。
pub fn verify_record_at(
    record: &Value,
    input: Input,
    config: &Config,
    config_path: &Path,
    base: &Path,
) -> Result<()> {
    let record = canonical_record(record, base)?;
    if record["status"] != "completed" || record["producer"]["kind"] != "kernel" {
        return Err(Stop::invalid("record", "验收入口只接已完成内核记录"));
    }
    let trace = &record["trace"];
    verify_record_events(&record, &input)?;
    let ticks = trace["ticks"]
        .as_array()
        .ok_or_else(|| Stop::invalid("trace.ticks", "须为数组"))?
        .len();
    let format = trace["format"]
        .as_str()
        .ok_or_else(|| Stop::invalid("trace.format", "须为字符串"))?;
    let k = if format == "checkpoint_delta" {
        trace["checkpoint_interval"]
            .as_u64()
            .ok_or_else(|| Stop::invalid("checkpoint_interval", "须为正整数"))? as usize
    } else {
        1
    };
    let mut engine = if record["execution_mode"] == "production_abstraction" {
        Engine::new_production(input)?
    } else {
        Engine::new(input)?
    };
    engine.set_cache_enabled(true);
    if record["execution_mode"] == "production_abstraction" {
        engine.production_domain()?;
    }
    let recomputed = run_record(engine, config, config_path, ticks, format, k)?;
    if record != recomputed {
        return Err(Stop::invalid("record", "交付记录与完整重算逐字段不同"));
    }
    Ok(())
}
