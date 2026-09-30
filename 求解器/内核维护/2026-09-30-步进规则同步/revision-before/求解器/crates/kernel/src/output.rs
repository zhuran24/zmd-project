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
    if trace["format"] == "full_state_each_step" {
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
    let rows = result["steps"]
        .as_array_mut()
        .ok_or_else(|| Stop::invalid("trace.steps", "须为数组"))?;
    let mut previous = trace["start_state"].clone();
    for (i, row) in rows.iter_mut().enumerate() {
        if i % k == 0 {
            if row.get("state").is_none() || row.get("delta").is_some() {
                return Err(Stop::invalid(format!("steps[{i}]"), "检查点须为全状态"));
            }
            previous = row["state"].clone();
        } else {
            if row.get("state").is_some() {
                return Err(Stop::invalid(format!("steps[{i}]"), "非检查点禁止全状态"));
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
    o.insert("format".into(), json!("full_state_each_step"));
    Ok(result)
}
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
    paths.push((
        "semantics".into(),
        root.join("crates/kernel/周期键读取审计.md"),
    ));
    for p in [
        "value.rs",
        "config.rs",
        "model.rs",
        "catalog.rs",
        "input.rs",
        "interfaces.rs",
        "engine.rs",
        "warehouse.rs",
        "polling.rs",
        "step.rs",
        "graph.rs",
        "output.rs",
        "ledger.rs",
        "cycle.rs",
        "cycle_io.rs",
        "digest.rs",
        "seed.rs",
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

/// 单一输入和固定参数的有限执行，不提交全称或完整循环证明。
pub(crate) fn evidence_scope(kind: &str, direction: &str, sources: &[Value]) -> Value {
    json!({"kind":kind,"support_domain":["固定布局、设定、step-order-v1 与整数步的有限执行"],
        "fixed_parameter_lifecycle":"本段无离线或玩家动作，先后与参数固定",
        "context_bindings":sources.iter().map(|r|json!({"path":r["path"],"sha256":r["sha256"]})).collect::<Vec<_>>(),
        "initial_state_coverage":{"description":"一个显式条件种子及已重放前缀","exact_reachable_set_enumerated":false},
        "direction":direction,"review_status":"author_checked","proof_sources":[]})
}
/// 66 轴的本次证据；只以实际事件和流量宣称 exercised。
pub fn coverage(config: &Config, steps: &[Value], input: &Input) -> Vec<Value> {
    let mut evidence = BTreeMap::<String, BTreeSet<String>>::new();
    for step in steps {
        for event in step["events"].as_array().into_iter().flatten() {
            let id = event["event"].as_str().unwrap_or("").to_string();
            let mut add = |family: &str| {
                evidence
                    .entry(family.into())
                    .or_default()
                    .insert(id.clone());
            };
            if ["start", "complete", "flush"]
                .iter()
                .any(|p| event["phase"] == *p)
            {
                add("manufacturing.");
            }
            if event["detail"].get("transfer").is_some() {
                add("transfer.");
            }
            for mv in event["moves"].as_array().into_iter().flatten() {
                if event["phase"] == "judge" {
                    for name in ["time.domain", "component.belt_segment", "step.order"] {
                        add(name);
                    }
                }
                if let Some(ch) = input
                    .geometry
                    .channels
                    .get(mv["channel"].as_str().unwrap_or(""))
                {
                    for port in [&ch.source_port, &ch.target_port] {
                        let u = &input.geometry.ports[port].unit;
                        match input.geometry.units[u].kind.as_str() {
                            "桥接器" => add("bridge."),
                            "物品准入口" if port == &ch.target_port => add("gate."),
                            _ => (),
                        }
                    }
                    let graph = &input.graph;
                    for (subject, side) in [
                        (&graph.sender[&ch.id], "output"),
                        (&graph.receiver[&ch.id], "input"),
                    ] {
                        let channels = if side == "input" {
                            graph.inputs(subject)
                        } else {
                            graph.outputs(subject)
                        };
                        if channels.len() > 1 {
                            add("polling.");
                            if matches!(subject,crate::graph::Subject::Component(i) if
                                (graph.components[*i].kind==crate::graph::ComponentKind::Splitter && side=="output") ||
                                (graph.components[*i].kind==crate::graph::ComponentKind::Merger && side=="input"))
                            {
                                add("polling.split_merge");
                            }
                        }
                    }
                }
            }
        }
        for flow in crate::ledger::FLOWS {
            if !step["warehouse_ledger"][flow]
                .as_array()
                .is_none_or(Vec::is_empty)
            {
                for row in step["warehouse_ledger"][flow].as_array().unwrap() {
                    let id = row["event"]
                        .as_str()
                        .map(str::to_string)
                        .unwrap_or_else(|| format!("step:{}:{flow}", step["step"]));
                    evidence
                        .entry("warehouse.".into())
                        .or_default()
                        .insert(id.clone());
                    evidence
                        .entry(format!("warehouse.flow.{flow}"))
                        .or_default()
                        .insert(id);
                }
            }
        }
    }
    config.axes.iter().map(|(axis,row)| {
        let name=axis.name();
        let key=if name.starts_with("polling.split_merge") {"polling.split_merge"}
            else if name=="warehouse.external_supply" {"warehouse.flow.external_supply"}
            else { ["polling.","transfer.","manufacturing.","bridge.","gate.","warehouse."].into_iter().find(|s|name.starts_with(s)).unwrap_or(name) };
        let ids=evidence.get(key).cloned().unwrap_or_default();
        let (status,ev)=if name=="warehouse.periodic_lift" {("proof_pending",vec!["完整循环复原及全称覆盖待证".to_string()])}
            else if row.disposition==Disposition::Stop {("stop_not_triggered",vec!["有限前缀未触及停止域".into()])}
            else if !ids.is_empty() {("exercised",ids.into_iter().collect())}
            else if row.disposition==Disposition::Input || name.starts_with("initialization.") || name.starts_with("connection.") {("input_checked",vec!["已核当前输入；不证明全称覆盖".into()])}
            else {("not_exercised",vec!["本次未记录该机制实际后效".into()])};
        json!({"axis":name,"reason":row.coverage_loss,"disposition":row.disposition,"coverage_status":status,"evidence":ev,
            "other_values":if row.disposition==Disposition::Fixed{"已定域无其它值"}else{"其它值及其联合组合未覆盖"}})
    }).collect()
}
pub fn step_row(engine: &Engine, report: &crate::model::StepReport) -> Value {
    json!({"step":report.step,"events":report.events,"state":engine.state,"warehouse_ledger":report.ledger})
}
/// 每一行对应一步；停止时只保留成功完成的边界状态。
pub fn run_record(
    mut engine: Engine,
    config: &Config,
    config_path: &Path,
    steps: usize,
    format: &str,
    interval: usize,
) -> Result<Value> {
    if !["full_state_each_step", "checkpoint_delta"].contains(&format) || interval == 0 {
        return Err(Stop::invalid("trace.format", "未知格式或检查点间隔为零"));
    }
    if read_json(&engine.input.path)? != engine.input.raw {
        return Err(Stop::invalid(
            "fingerprints.input",
            "内存输入与持久来源不同；记录不能绑定另一份输入",
        ));
    }
    let start = json!(engine.state);
    let from = engine.time();
    let mut rows = Vec::new();
    let mut stop = None;
    for _ in 0..steps {
        match engine.step() {
            Ok(report) => rows.push(step_row(&engine, &report)),
            Err(e) => {
                stop = Some(e);
                break;
            }
        }
    }
    let uncovered = coverage(config, &rows, &engine.input);
    let completed = rows
        .iter()
        .flat_map(|r| r["events"].as_array().unwrap())
        .filter(|e| e["phase"] == "complete")
        .count();
    let end = from
        .checked_add(rows.len() as i64)
        .ok_or_else(|| Stop::invalid("end_step", "整数越界"))?;
    let mut previous = start.clone();
    if format == "checkpoint_delta" {
        for (i, row) in rows.iter_mut().enumerate() {
            let current = row["state"].clone();
            if i % interval != 0 {
                row.as_object_mut().unwrap().remove("state");
                row["delta"] = json!(delta(&previous, &current)?);
            }
            previous = current;
        }
    }
    let mut trace = json!({"start_state":start,"steps":rows,"end_step":end,"format":format});
    if format == "checkpoint_delta" {
        trace["checkpoint_interval"] = json!(interval);
        trace["delta_encoding"] = json!("object_replace_v1");
    }
    let sources = fingerprints(&engine.input, config_path, &[])?;
    let status = stop
        .as_ref()
        .map(|s| s.status.as_str())
        .unwrap_or("completed");
    let open = stop.iter().map(ToString::to_string).collect::<Vec<_>>();
    Ok(
        json!({"schema":"kernel-output-v5","evidence_scope":evidence_scope("finite_trace","diagnostic",&sources),
        "execution_mode":if engine.production_abstraction{"production_abstraction"}else{"finite_concrete"},
        "port_meeting":engine.input.parameters.value(Axis::ConnectionPortMeeting)?,
        "run_id":format!("kernel:{}:{from}:{steps}",engine.input.path.file_stem().and_then(|s|s.to_str()).unwrap_or("input")),
        "profile_id":config.profile_id,"producer":{"kind":"kernel","path":concat!(env!("CARGO_MANIFEST_DIR"),"/src/lib.rs"),"claim":"整数步有限条件轨迹；不作全称或完整目标认证"},
        "status":status,"fingerprints":sources,"parameter_assignment":engine.input.raw["parameters"],
        "input_history":{"timeline":engine.input.raw["timeline"],"construction":engine.input.raw["construction"],"debug_operations":engine.input.raw["debug_operations"],"environment":engine.input.raw["environment"],"reachability":engine.input.raw["initial_state"]["reachability"]},
        "uncovered_axes":uncovered,"trace":trace,
        "validation_scope":{"kind":"finite_trace","from":tv(from),"through":tv(end),"initial_history":"conditional_witness","universal_parameters":false,"all_reachable_cycles":false,"target_certified":false,"manufacturing_cycles_completed":q(completed as i64)},"open_items":open}),
    )
}
pub fn stopped_record(stop: &Stop) -> Value {
    json!({"schema":"kernel-output-v5","evidence_scope":evidence_scope("diagnostic","diagnostic",&[]),"execution_mode":"finite_concrete","port_meeting":"shared_edge_opposite","run_id":"kernel:load-stop","profile_id":"kernel_profile_v2","producer":{"kind":"kernel","path":concat!(env!("CARGO_MANIFEST_DIR"),"/src/lib.rs"),"claim":"装载停止，未形成后继"},"status":stop.status,"fingerprints":[],"parameter_assignment":null,"input_history":null,"uncovered_axes":[],"trace":null,"validation_scope":null,"open_items":[stop.to_string()]})
}
/// 连续步、事件身份及台账引用，与重放比较独立。
pub(crate) fn verify_step_events(previous: &Value, row: &Value) -> Result<()> {
    let step = row["step"]
        .as_i64()
        .ok_or_else(|| Stop::invalid("step", "须为整数"))?;
    if step != instant(&previous["environment"]["time"], "step")?
        || instant(&row["state"]["environment"]["time"], "state.time")? != add(step, 1, "step")?
    {
        return Err(Stop::invalid("step", "步与前后边界不连续"));
    }
    let events: Vec<crate::model::Event> = decode(row["events"].clone(), "events")?;
    let mut ids = BTreeSet::new();
    for (i, e) in events.iter().enumerate() {
        if e.event != format!("E|{step}|{i}")
            || !["supply", "complete", "flush", "judge", "start"].contains(&e.phase.as_str())
        {
            return Err(Stop::invalid("events", "身份不连续或阶段未知"));
        }
        ids.insert(e.event.as_str());
    }
    for flow in crate::ledger::FLOWS {
        for entry in row["warehouse_ledger"][flow]
            .as_array()
            .ok_or_else(|| Stop::invalid(flow, "缺台账数组"))?
        {
            if let Some(id) = entry.get("event") {
                if !id.as_str().is_some_and(|id| ids.contains(id)) {
                    return Err(Stop::invalid(flow, "台账引用未知事件"));
                }
            } else if flow != "representative_adjustment" {
                return Err(Stop::invalid(flow, "台账缺事件引用"));
            }
        }
    }
    crate::ledger::verify_tick(previous, row)
}
pub(crate) fn verify_record_events(record: &Value, _input: &Input) -> Result<()> {
    if record["schema"] != "kernel-output-v5" {
        return Err(Stop::invalid("schema", "仅接受 v5 记录"));
    }
    let trace = decode_trace(&record["trace"])?;
    let mut previous = trace["start_state"].clone();
    for row in trace["steps"]
        .as_array()
        .ok_or_else(|| Stop::invalid("trace.steps", "须为数组"))?
    {
        verify_step_events(&previous, row)?;
        previous = row["state"].clone();
    }
    if trace["end_step"] != instant(&previous["environment"]["time"], "end_step")? {
        return Err(Stop::invalid("trace.end_step", "末边界不符"));
    }
    Ok(())
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
    let steps = trace["steps"]
        .as_array()
        .ok_or_else(|| Stop::invalid("trace.steps", "须为数组"))?
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
    let engine = if record["execution_mode"] == "production_abstraction" {
        Engine::new_production(input)?
    } else {
        Engine::new(input)?
    };
    if record["execution_mode"] == "production_abstraction" {
        engine.production_domain()?;
    }
    let recomputed = run_record(engine, config, config_path, steps, format, k)?;
    if record != recomputed {
        return Err(Stop::invalid("record", "交付记录与完整重算逐字段不同"));
    }
    Ok(())
}
