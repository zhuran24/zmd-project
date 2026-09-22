//! 输出§5.1/§5.3：引用先核原始字节、按所属文件目录解析，再独立核前缀及周期。
use crate::{
    catalog::sha256,
    cycle::{self, SearchOptions},
    event_identity::EventValidator,
    output,
    value::*,
    Config, Engine, Input,
};
use serde_json::{json, Value};
use std::path::{Path, PathBuf};
pub(crate) fn write_json(path: &Path, value: &Value) -> Result<()> {
    std::fs::write(
        path,
        serde_json::to_string_pretty(value).map_err(|e| Stop::invalid("json", e.to_string()))?
            + "\n",
    )
    .map_err(|e| Stop::invalid(path.display().to_string(), e.to_string()))
}
pub(crate) fn input_producer() -> Value {
    json!({"kind":"kernel","path":concat!(env!("CARGO_MANIFEST_DIR"),"/src/lib.rs"),"claim":"Rust内核装载并核验的完整输入引用；不证明种子可达"})
}
pub(crate) fn artifact_ref(path: &Path, format: &str, producer: Value) -> Result<Value> {
    let path = path
        .canonicalize()
        .map_err(|e| Stop::invalid("reference.path", e.to_string()))?;
    Ok(json!({"path":path,"sha256":sha256(&path)?,"producer":producer,"format":format}))
}
pub(crate) fn resolved(base: &Path, v: &Value, at: &str) -> Result<PathBuf> {
    let text = v
        .as_str()
        .filter(|s| !s.is_empty())
        .ok_or_else(|| Stop::invalid(at, "缺非空路径"))?;
    base.join(text)
        .canonicalize()
        .map_err(|e| Stop::invalid(at, e.to_string()))
}
fn load_ref(reference: &Value, base: &Path) -> Result<(PathBuf, Value, Value)> {
    fields(reference, "path sha256 producer format", "artifact_ref")?;
    fields(
        &reference["producer"],
        "kind path claim",
        "artifact_ref.producer",
    )?;
    let path = resolved(base, &reference["path"], "artifact_ref.path")?;
    if sha256(&path)? != reference["sha256"] {
        return Err(Stop::invalid("artifact_ref.sha256", "引用原始字节指纹不符"));
    }
    let mut canonical = reference.clone();
    canonical["path"] = json!(path);
    canonical["producer"]["path"] = json!(resolved(
        base,
        &reference["producer"]["path"],
        "artifact_ref.producer.path"
    )?);
    Ok((path.clone(), read_json(&path)?, canonical))
}
pub(crate) fn canonical_fingerprints(value: &mut Value, base: &Path) -> Result<()> {
    for row in value["fingerprints"]
        .as_array_mut()
        .ok_or_else(|| Stop::invalid("fingerprints", "须为数组"))?
    {
        fields(row, "role path sha256", "fingerprints[]")?;
        let p = resolved(base, &row["path"], "fingerprints.path")?;
        if sha256(&p)? != row["sha256"] {
            return Err(Stop::invalid(
                p.display().to_string(),
                "来源指纹不符，须重验而非刷新",
            ));
        }
        row["path"] = json!(p);
    }
    Ok(())
}
/// 输出§4/§5：证明引用与运行引用同样先核字节，路径相对所属证书。
pub(crate) fn canonical_proof_sources(value: &mut Value, base: &Path) -> Result<()> {
    fn source(row: &mut Value, base: &Path) -> Result<()> {
        fields(row, "path sha256", "proof_source")?;
        let path = resolved(base, &row["path"], "proof_source.path")?;
        if sha256(&path)? != row["sha256"] {
            return Err(Stop::invalid("proof_source.sha256", "证明引用原始字节指纹不符"));
        }
        row["path"] = json!(path);
        Ok(())
    }
    if let Some(scope) = value.get_mut("evidence_scope") {
        for key in ["context_bindings", "proof_sources"] {
            for row in scope[key].as_array_mut().ok_or_else(|| Stop::invalid(key, "证明来源须为数组"))? {
                source(row, base)?;
            }
        }
    }
    if let Some(cycle) = value.get_mut("cycle").filter(|v| v.is_object()) {
        for key in ["definition", "mapping_proof"] {
            source(&mut cycle["normalization"][key], base)?;
        }
        for row in cycle["reception_scope"]["proof_sources"].as_array_mut()
            .ok_or_else(|| Stop::invalid("reception_scope.proof_sources", "须为数组"))? {
            source(row, base)?;
        }
        for key in ["forward_projection", "reverse_reconstruction", "all_reachable_cycles"] {
            for row in cycle["correspondence"][key]["proof_sources"].as_array_mut()
                .ok_or_else(|| Stop::invalid("correspondence.proof_sources", "须为数组"))? {
                source(row, base)?;
            }
        }
    }
    Ok(())
}
pub fn verify_cycle(result: &Value, config: &Config, config_path: &Path) -> Result<Value> {
    verify_cycle_at(result, config, config_path, Path::new("."))
}
/// 两模式均实际从原种子搜索，再独立从周期起点重跑恰P刻；完全只读。
pub fn verify_cycle_at(
    result: &Value,
    config: &Config,
    config_path: &Path,
    base: &Path,
) -> Result<Value> {
    fields(result,"schema result_id status level execution_mode port_meeting seed parameter_point reading support_domain domain_report fingerprints record_mode replay_input_ref run_record_ref last_state cycle stop budget open_items evidence_scope environment_assumption","cycle")?;
    if result["schema"] != "kernel-cycle-v3" || (!result["level"].is_null() && result["level"] != "production_part") {
        return Err(Stop::invalid("cycle", "版本不符或具体完整周期验收尚未实现"));
    }
    if result["replay_input_ref"].is_null() {
        let mut supplied = result.clone();
        canonical_fingerprints(&mut supplied, base)?;
        canonical_proof_sources(&mut supplied, base)?;
        let source = supplied["fingerprints"]
            .as_array()
            .and_then(|a| a.iter().find(|r| r["role"] == "input"))
            .and_then(|r| r["path"].as_str())
            .ok_or_else(|| {
                Stop::invalid(
                    "cycle.load_stop",
                    "仅结构诊断；失败输入不可寻址，不能报告独立验收通过",
                )
            })?;
        let source = PathBuf::from(source);
        let stop = Input::load(&source, config, false)
            .and_then(Engine::new_production)
            .err()
            .ok_or_else(|| {
                Stop::invalid(
                    "cycle.load_stop",
                    "来源可完整装载，禁止伪造装载前空外壳丢弃前缀",
                )
            })?;
        let raw = read_json(&source).ok();
        let meeting = raw
            .as_ref()
            .and_then(|r| {
                r["parameters"]["fixed"]["connection.port_meeting"]["value"].as_str()
            })
            .unwrap_or("");
        let ticks = result["budget"]["max_ticks"]
            .as_u64()
            .filter(|n| *n > 0)
            .ok_or_else(|| Stop::invalid("max_ticks", "须为正整数"))? as usize;
        let sweeps = result["budget"]["max_sweeps"]
            .as_u64()
            .filter(|n| *n > 0)
            .ok_or_else(|| Stop::invalid("max_sweeps", "须为正整数"))?
            as usize;
        let mut expected = load_stopped_cycle(&stop, ticks, sweeps, meeting);
        if !["none", "referenced"].contains(&result["record_mode"].as_str().unwrap_or("")) {
            return Err(Stop::invalid("record_mode", "未知记录模式"));
        }
        expected["record_mode"] = result["record_mode"].clone();
        attach_load_context(&mut expected, &source, config_path)?;
        if expected != supplied {
            return Err(Stop::invalid(
                "cycle.load_stop",
                "装载停止及最小上下文与独立复现不符",
            ));
        }
        return Ok(
            json!({"status":"input_checked","cycle_replayed":false,"diagnostic_replayed":true,"reason":"失败输入及依赖指纹已核，复现同一装载停止；无游戏转移或周期"}),
        );
    }
    let mut supplied = result.clone();
    canonical_fingerprints(&mut supplied, base)?;
    canonical_proof_sources(&mut supplied, base)?;
    let (source, raw, input_ref) = load_ref(&result["replay_input_ref"], base)?;
    if input_ref["format"] != "kernel-input-v3"
        || raw["schema"] != "kernel-input-v3"
        || input_ref["producer"] != input_producer()
    {
        return Err(Stop::invalid("replay_input_ref", "格式或输入producer不符"));
    }
    supplied["replay_input_ref"] = input_ref;
    let input = Input::parse(raw, &source, config, false)?;
    let ticks = result["budget"]["max_ticks"]
        .as_u64()
        .filter(|n| *n > 0)
        .ok_or_else(|| Stop::invalid("max_ticks", "须为正整数"))? as usize;
    let sweeps = result["budget"]["max_sweeps"]
        .as_u64()
        .filter(|n| *n > 0)
        .ok_or_else(|| Stop::invalid("max_sweeps", "须为正整数"))? as usize;
    let mut loaded_record = None;
    let mut options = SearchOptions::default();
    match result["record_mode"].as_str() {
        Some("referenced") => {
            let (path, record, reference) = load_ref(&result["run_record_ref"], base)?;
            let record = output::canonical_record(&record, path.parent().unwrap())?;
            let format = format!(
                "{}/{}",
                record["schema"].as_str().unwrap_or(""),
                record["trace"]["format"].as_str().unwrap_or("")
            );
            let producer = &record["producer"];
            if ![
                "kernel-output-v4/full_state_each_instant",
                "kernel-output-v4/checkpoint_delta",
            ]
            .contains(&format.as_str())
                || reference["format"] != format
                || reference["producer"] != *producer
                || producer["kind"] != "kernel"
            {
                return Err(Stop::invalid("run_record_ref", "格式或producer与目标不符"));
            }
            output::verify_record_events(&record, &input)?;
            supplied["run_record_ref"] = reference;
            options.record_path = Some(path);
            loaded_record = Some(record);
        }
        Some("none") if result["run_record_ref"].is_null() => (),
        _ => return Err(Stop::invalid("record_mode", "记录模式与引用不一致")),
    }
    let (mut expected, expected_record) =
        cycle::search(input.clone(), config, config_path, ticks, sweeps, &options)?;
    if let (Some(given), Some(mut regenerated)) = (&loaded_record, expected_record) {
        if given["trace"]["format"] == "checkpoint_delta" {
            let k = given["trace"]["checkpoint_interval"]
                .as_u64()
                .filter(|n| *n > 0)
                .ok_or_else(|| Stop::invalid("checkpoint_interval", "须正整数"))?
                as usize;
            let mut previous = regenerated["trace"]["start_state"].clone();
            for (i, row) in regenerated["trace"]["ticks"]
                .as_array_mut()
                .unwrap()
                .iter_mut()
                .enumerate()
            {
                let current = row["state"].clone();
                if i % k != 0 {
                    row.as_object_mut().unwrap().remove("state");
                    row["delta"] = json!(output::delta(&previous, &current)?);
                }
                previous = current;
            }
            regenerated["trace"]["format"] = json!("checkpoint_delta");
            regenerated["trace"]["checkpoint_interval"] = json!(k);
            regenerated["trace"]["delta_encoding"] = json!("object_replace_v1");
        }
        if *given != regenerated {
            return Err(Stop::invalid(
                "run_record_ref",
                "完整v3前缀与独立重算逐字段不符",
            ));
        }
        expected["run_record_ref"] = supplied["run_record_ref"].clone();
    }
    if !supplied["cycle"].is_null() {
        let definition = &mut supplied["cycle"]["normalization"]["definition"];
        definition["path"] = json!(resolved(
            base,
            &definition["path"],
            "normalization.definition"
        )?);
    }
    if expected != supplied {
        return Err(Stop::invalid("cycle", "完整证书与原种子独立搜索重算不符"));
    }
    // 独立身份审计使用流式注册器，不保留全部完整快照。
    let mut prefix = Engine::new_production(input.clone())?;
    prefix.max_sweeps = sweeps;
    prefix.set_cache_enabled(true);
    let mut registry = EventValidator::new(&input, &json!(prefix.state))?;
    let completed = result["budget"]["completed_ticks"].as_u64().unwrap();
    let mut previous = json!(prefix.state);
    for _ in 0..completed {
        let row = prefix.step(true)?.unwrap();
        registry.tick(&row)?;
        crate::ledger::verify_tick(&previous, &row)?;
        previous = row["state"].clone();
    }
    let c = &result["cycle"];
    if c.is_null() {
        return Ok(
            json!({"status":"input_checked","cycle_replayed":false,"prefix_replayed":completed,"reason":"原种子前缀及停止/预算位置已复现，无周期"}),
        );
    }
    let period = num(&c["period"], "period")?;
    let mut replay = Engine::new_production(cycle::checkpoint_input(
        &input,
        c["start_state"].clone(),
        config,
    )?)?;
    replay.max_sweeps = sweeps;
    replay.set_cache_enabled(true);
    let mut registry = EventValidator::new(&input, &c["start_state"])?;
    let record_trace = loaded_record
        .as_ref()
        .map(|r| output::decode_trace(&r["trace"]))
        .transpose()?;
    let a = instant(&c["start_time"], "start")?;
    let mut previous = c["start_state"].clone();
    for index in 0..period as usize {
        let row = replay.step_tick(true)?.unwrap();
        registry.tick(&row)?;
        crate::ledger::verify_tick(&previous, &row)?;
        previous = row["state"].clone();
        if json!({"time":row["time"],"warehouse_ledger":row["warehouse_ledger"]})
            != c["ledger"][index]
        {
            return Err(Stop::invalid("cycle.ledger", "P刻独立重跑台账不符"));
        }
        if let Some(trace) = &record_trace {
            let original = trace["ticks"]
                .as_array()
                .unwrap()
                .iter()
                .find(|t| t["time"] == row["time"])
                .ok_or_else(|| Stop::invalid("cycle.replay", "记录缺周期刻"))?;
            for field in ["time", "events", "state", "warehouse_ledger", "closure"] {
                if row[field] != original[field] {
                    return Err(Stop::invalid(
                        format!("cycle.replay[{index}].{field}"),
                        "周期重跑逐字段不符",
                    ));
                }
            }
        }
    }
    if json!(replay.state) != c["end_state"] || replay.cycle_key()? != c["end_key"] {
        return Err(Stop::invalid("cycle.replay", "P刻完整终态或键不符"));
    }
    Ok(
        json!({"status":"input_checked","cycle_replayed":true,"prefix_replayed":completed,"period":period,"start_time":a,"checks":["引用原始字节/format/producer和完整来源链","原种子到达前缀及跨刻事件身份","独立重建D动态前件及周期账/率/接收域","从周期起点P次step_tick及完整终态"]}),
    )
}
/// KQ-09装载前外壳不伪造读法；结构通过与独立验收明确区分。
pub fn load_stopped_cycle(
    stop: &Stop,
    max_ticks: usize,
    max_sweeps: usize,
    port_meeting: &str,
) -> Value {
    let status = match stop.status.as_str() {
        "invalid_input" => "invalid_input",
        "inconclusive" => "inconclusive",
        _ => "stopped",
    };
    let meeting = if port_meeting == "shared_edge_opposite" {
        json!(port_meeting)
    } else {
        Value::Null
    };
    json!({"schema":"kernel-cycle-v3","evidence_scope":output::evidence_scope("diagnostic","diagnostic", &[]),"environment_assumption":"仓库收得下成品。","result_id":"cycle:load-stop","status":status,"level":null,"execution_mode":"production_abstraction","port_meeting":meeting,"seed":null,"parameter_point":null,"reading":{"port_meeting":meeting,"warehouse_acceptance":"unresolved","acceptance_quantifier":"unresolved","cycle_interpretation":"production_projection","remaining_assumptions":["装载未成立，未形成可认证参数点"]},"support_domain":{"name":"phase_production_v1","uncovered":["完整输入未通过装载"]},"domain_report":(1..=5).map(|i|json!({"condition":format!("D.{i}"),"status":"unresolved","scope":"not_checked","locations":[stop.location],"evidence":[format!("未完成装载：{}",stop.reason)]})).collect::<Vec<_>>(),"fingerprints":[],"record_mode":"none","replay_input_ref":null,"run_record_ref":null,"last_state":null,"cycle":null,"stop":{"kind":if stop.status=="inconclusive"{"resource"}else{stop.status.as_str()},"axis":stop.axis,"event":stop.location,"time":null,"reason":stop.reason,"partial_events":[]},"budget":{"max_ticks":max_ticks.max(1),"max_sweeps":max_sweeps.max(1),"completed_ticks":0},"open_items":[stop.to_string(),"装载诊断未独立复现；技术停止不证明布局无解"]})
}
/// 输出§5.1.2：失败输入仍可读取时锁住诊断材料；不把非法输入包装成可回放引用。
pub fn attach_load_context(result: &mut Value, source: &Path, config_path: &Path) -> Result<()> {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .map_err(|e| Stop::invalid("root", e.to_string()))?;
    let mut paths = vec![
        ("input", source.to_path_buf()),
        ("profile", config_path.to_path_buf()),
    ];
    for name in [
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
        paths.push(("checker", root.join("crates/kernel/src").join(name)));
    }
    for name in [
        "受限转移定义.md",
        "运行语义.md",
        "内核输入.md",
        "内核输出.md",
    ] {
        paths.push(("semantics", root.join("规格").join(name)));
    }
    paths.push(("schema", root.join("规格/内核输出.schema.json")));
    paths.push(("semantics", root.join("crates/kernel/周期键读取审计.md")));
    if let Ok(raw) = read_json(source) {
        for (role, reference) in [
            ("catalog", &raw["catalog"]),
            ("axis_registry", &raw["parameters"]["axis_registry"]),
        ] {
            if let Some(p) = reference["path"].as_str() {
                paths.push((role, source.parent().unwrap_or(Path::new(".")).join(p)));
            }
        }
    }
    for name in [
        "《明日方舟：终末地》游戏规则.txt",
        "求解任务.txt",
        "求解约束.txt",
    ] {
        paths.push(("formal_source", root.parent().unwrap().join(name)));
    }
    result["fingerprints"] = json!(paths
        .into_iter()
        .filter(|(_, p)| p.is_file())
        .map(|(role, p)| {
            let path = p
                .canonicalize()
                .map_err(|e| Stop::invalid("fingerprints", e.to_string()))?;
            Ok(json!({"role":role,"path":path,"sha256":sha256(&path)?}))
        })
        .collect::<Result<Vec<_>>>()?);
    Ok(())
}
