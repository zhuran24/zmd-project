//! 受限转移§6：生产投影的有界查重、完整键和独立周期重跑。
use crate::{
    catalog::sha256,
    config::{Axis, Disposition},
    ledger::{FLOWS, ORES, PRODUCTS},
    model::State,
    output,
    value::*,
    Config, Engine, Input,
};
use serde_json::{json, Value};
use std::{collections::BTreeMap, path::Path};

/// 输入§1.1、转移§6.2：精确约分，不改变参数数组的语义顺序。
fn rational(s: &str) -> Result<String> {
    let parts: Vec<_> = s.split('/').collect();
    if parts.is_empty() || parts.len() > 2 {
        return Err(Stop::invalid("cycle.quantity", "非法有理数"));
    }
    let n = parts[0]
        .parse::<i128>()
        .map_err(|_| Stop::invalid("cycle.quantity", "非法分子"))?;
    let d = if parts.len() == 2 {
        parts[1]
            .parse::<i128>()
            .map_err(|_| Stop::invalid("cycle.quantity", "非法分母"))?
    } else {
        1
    };
    if d <= 0 {
        return Err(Stop::invalid("cycle.quantity", "分母须正"));
    }
    let mut a = n.unsigned_abs();
    let mut b = d as u128;
    while b != 0 {
        let c = a % b;
        a = b;
        b = c;
    }
    let divisor = i128::try_from(a).map_err(|_| Stop::invalid("cycle.quantity", "约分越界"))?;
    let (n, d) = (n / divisor, d / divisor);
    Ok(if d == 1 {
        n.to_string()
    } else {
        format!("{n}/{d}")
    })
}
/// 转移§6.2：相对时间超出运行整数域时停止，不能在release环绕成错误的键。
fn difference(a: i64, b: i64, at: &str) -> Result<i64> {
    a.checked_sub(b).ok_or_else(|| {
        Stop::new(
            "inconclusive",
            "resource.integer",
            at,
            "相对时间超出i64运行域",
        )
    })
}
fn normalize(v: &mut Value) -> Result<()> {
    match v {
        Value::Array(a) => {
            for x in a {
                normalize(x)?;
            }
        }
        Value::Object(o) => {
            if o.len() == 2 && o.contains_key("value") && o.contains_key("category") {
                let n = rational(
                    o["value"]
                        .as_str()
                        .ok_or_else(|| Stop::invalid("cycle.quantity", "缺字符串"))?,
                )?;
                o.remove("category");
                o.insert("value".into(), json!(n));
            } else {
                if o.contains_key("status") {
                    o.remove("basis");
                }
                for x in o.values_mut() {
                    normalize(x)?;
                }
            }
        }
        _ => (),
    }
    Ok(())
}
fn sort_rows(v: &mut Value, field: &str) {
    v.as_array_mut()
        .unwrap()
        .sort_by(|a, b| a[field].as_str().cmp(&b[field].as_str()));
}

impl Engine {
    /// 转移§6.1 D.1–D.5：绑定本引擎完整布局/设定/参数，不接受裸状态跨上下文查重。
    pub fn production_domain(&self) -> Result<Value> {
        for condition in 1..=5 {
            self.domain_condition(condition)?;
        }
        Ok(self.domain_report("static"))
    }
    /// 输出§5.1.1：逐条独立检查，不以首项失败省略其它四项。
    pub fn domain_report(&self, scope: &str) -> Value {
        json!((1..=5).map(|i| {
            let result = self.domain_condition(i);
            let (status, locations, evidence) = match result {
                Ok(()) => ("pass", vec![], vec![match i {
                    1 => "已装载固定布局、设定、global/v1、在线零干预、sufficient；无未来历史/玩家策略".into(),
                    2 => "当前两矿唯一正库存且无可检查回矿候选；未来PC及有资格全箱仍在容量/physical/权限前动态核验".into(),
                    3 => "O为空；成品格无取货指派；新格标签无冲突；retain_history保持该不变量".into(),
                    4 => "全部输入/种子/分支表已装载；未来无终点请求仍动态停止；不证明种子可达".into(),
                    _ => { let (core, boxes) = self.production_bound(); format!("结构界B={core}+300*{boxes}={} <80000；每PC每刻至多1、每箱每刻至多一次全箱300",core+300*boxes) }
                }]),
                Err(e) => (if e.status=="unresolved" || e.status=="inconclusive" {"unresolved"} else {"fail"}, vec![e.location], vec![e.reason]),
            };
            json!({"condition":format!("D.{i}"),"status":status,"scope":scope,"locations":locations,"evidence":evidence})
        }).collect::<Vec<_>>())
    }
    fn production_bound(&self) -> (usize, usize) {
        (
            self.input
                .geometry
                .channels
                .values()
                .filter(|c| {
                    self.input.geometry.units[&self.input.geometry.ports[&c.target_port].unit].kind
                        == "协议核心"
                })
                .count(),
            self.input
                .geometry
                .units
                .iter()
                .filter(|(id, u)| u.kind == "协议储存箱" && self.enabled(id, "transfer"))
                .count(),
        )
    }
    fn domain_condition(&self, condition: usize) -> Result<()> {
        let fail =
            |at: &str, why: &str| Stop::unsupported(&format!("cycle.domain.D{condition}"), at, why);
        match condition {
            1 => {
                if !self.sufficient()
                    || !self.state.environment.online
                    || self.state.environment.stage != "zero_intervention"
                {
                    return Err(fail(
                        "environment / warehouse.external_supply",
                        "要求sufficient、在线且零干预",
                    ));
                }
                let withdrawal = &self.state.environment.withdrawal_memory.value;
                if withdrawal["once_fired"] != json!([])
                    || withdrawal["pending_rules"] != json!([])
                    || self.input.raw["environment"]["product_withdrawal"]["policy"]["value"]
                        ["rules"]
                        != json!([])
                {
                    return Err(fail(
                        "environment.product_withdrawal",
                        "生产域不接受拿取记忆或未来玩家策略",
                    ));
                }
                for e in self.input.raw["timeline"]["events"].as_array().unwrap() {
                    if instant(&e["time"], "cycle.history")? > self.t
                        && !self.pending.iter().any(|p| e["id"] == p.event)
                    {
                        return Err(fail(
                            e["id"].as_str().unwrap(),
                            "历史含未来事件/预占运行身份",
                        ));
                    }
                }
                for p in &self.pending {
                    let prefix = if p.operation == "manufacture_complete" {
                        "C"
                    } else {
                        "W"
                    };
                    let canonical = format!(
                        "{prefix}|{}|{}",
                        instant(&p.trigger["value"], "cycle.pending")?,
                        p.target
                    );
                    if ["I|", "J|", "C|", "W|"]
                        .iter()
                        .any(|s| p.event.starts_with(s))
                        && p.event != canonical
                    {
                        return Err(fail(&p.event, "活动pending占用不相容的运行保留身份"));
                    }
                }
            }
            2 => {
                for item in ORES {
                    let rows: Vec<_> = self
                        .state
                        .warehouse
                        .slots
                        .iter()
                        .filter(|r| r.item.as_deref() == Some(item))
                        .collect();
                    if rows.len() != 1 || rows[0].quantity.integer(item)? <= 0 {
                        return Err(fail(item, "两矿必须各唯一正库存"));
                    }
                }
                self.check_production_candidates()?;
                for (unit, index) in &self.progress {
                    if self.input.geometry.units[unit].kind == "协议储存箱"
                        && self.enabled(unit, "transfer")
                        && self.state.progress[*index]
                            .cooldowns
                            .iter()
                            .all(|c| c.remaining.integer(unit).is_ok_and(|n| n == 0))
                    {
                        for index in &self.unit_inventory[unit] {
                            if self.state.inventory[*index]
                                .contents
                                .iter()
                                .any(|c| ORES.contains(&c.item.as_str()))
                            {
                                return Err(fail(unit, "有资格全箱含矿，先于仓库容量规划停止"));
                            }
                        }
                    }
                }
            }
            3 => {
                // §6.5.1的实际配置前件：逐口核最终指派，不能借达标必要条件代替。
                for (port, slot) in &self.input.assignments {
                    let row = &self.state.warehouse.slots[self.warehouse[slot]];
                    if !row.item.as_deref().is_some_and(|item| ORES.contains(&item)) {
                        return Err(fail(port, "仓库生产投影要求全部取货指派为原矿"));
                    }
                }
                if !self
                    .state
                    .semantic_context
                    .arbitration
                    .warehouse_empty_slot_order
                    .is_empty()
                {
                    return Err(fail(
                        "semantic_context.arbitration.warehouse_empty_slot_order",
                        "非空匿名空格序不能抽象",
                    ));
                }
                for r in &self.state.warehouse.slots {
                    let identity = r
                        .item
                        .as_deref()
                        .or_else(|| r.empty_identity.value.as_str());
                    if identity.is_some_and(|s| PRODUCTS.contains(&s))
                        && self.input.assignments.values().any(|s| s == &r.slot)
                    {
                        return Err(fail(&r.slot, "成品历史/现存格被取货端口指派"));
                    }
                    if let Some(hex) = r.slot.strip_prefix("W_new_") {
                        let expected = identity.map(|s| {
                            s.as_bytes()
                                .iter()
                                .map(|b| format!("{b:02x}"))
                                .collect::<String>()
                        });
                        if expected.as_deref() != Some(hex) {
                            return Err(fail(&r.slot, "规范新格标签与物种身份冲突"));
                        }
                    }
                }
            }
            4 => (), // 完整Engine装载已核静态义务；未来无终点请求在真实访问处停止。
            5 => {
                let (core, boxes) = self.production_bound();
                if core + 300 * boxes >= 80000 {
                    return Err(fail(
                        "layout.physical_channels / settings.switches",
                        "结构入量界B不小于80000",
                    ));
                }
            }
            _ => unreachable!(),
        }
        Ok(())
    }
    /// 转移§6.1 D.2：先扫描全部现存矿候选，再进入任何容量/物理/授权求值。
    pub(crate) fn check_production_candidates(&self) -> Result<()> {
        // 固定几何预索引所有核心入边；每次仍查活动性及源候选，不缓存动态D.2结论。
        for cid in &self.core_inbound_channels {
            if !self.active.contains(cid) {
                continue;
            }
            let c = &self.input.geometry.channels[cid];
            if self
                .source(&c.source_port)?
                .is_some_and(|(_, c)| ORES.contains(&c.item.as_str()))
            {
                return Err(Stop::unsupported(
                    "cycle.domain.D2",
                    cid,
                    "现存回矿候选读取被抽象容量，先于physical/级排序/授权停止",
                ));
            }
        }
        Ok(())
    }
    /// 转移§6.2：独立于同刻closure_key，完整规范键按内容相等。
    pub fn cycle_key(&self) -> Result<Value> {
        self.production_domain()?;
        encode_key(&self.state, &self.input)
    }
}

/// 转移§6.2：公开状态接口显式绑定完整上下文；调用前须通过Engine的D准入与状态验证。
pub fn cycle_key(state: &State, input: &Input) -> Result<Value> {
    let mut bound = input.clone();
    bound.raw["initial_state"]["nonwarehouse"]["value"] = json!(state);
    let validated = Engine::new_production(bound)?;
    validated.production_domain()?;
    encode_key(&validated.state, &validated.input)
}
fn encode_key(state: &State, input: &Input) -> Result<Value> {
    if state.layout_snapshot != input.raw["layout"]["id"]
        || state.settings_anchor != input.raw["settings"]["anchor"]
    {
        return Err(Stop::invalid("cycle_key.context", "布局/设定上下文不符"));
    }
    let t = state.environment.time.integer("cycle_key.time")?;
    let jc = &state.semantic_context.judgment_context.value;
    if jc["phase"] != "after_closure"
        || jc["order_scope"] != "global"
        || !jc["next_event"].is_null()
        || jc.get("continuation").is_some()
        || !state
            .semantic_context
            .arbitration
            .warehouse_empty_slot_order
            .is_empty()
    {
        return Err(Stop::unsupported(
            "cycle.domain",
            "cycle_key",
            "仅接已核D域的after_closure",
        ));
    }
    let mut s = json!(state);
    let slots = s["warehouse"]["slots"].as_array_mut().unwrap();
    slots.retain(|r| {
        !PRODUCTS.contains(
            &r["item"]
                .as_str()
                .or_else(|| r["empty_identity"]["value"].as_str())
                .unwrap_or(""),
        )
    });
    for r in slots.iter_mut() {
        if ORES.contains(&r["item"].as_str().unwrap_or("")) {
            r["quantity"] = json!({"value":"sufficient"});
        }
    }
    sort_rows(&mut s["warehouse"]["slots"], "slot");
    for row in s["inventory"].as_array_mut().unwrap() {
        let uid = row["slot"].as_str().unwrap().split(':').next().unwrap();
        let transport = input.catalog.kinds[&input.geometry.units[uid].kind].family == "transport";
        for c in row["contents"].as_array_mut().unwrap() {
            if transport {
                let age = difference(t, instant(&c["entered_at"], "age")?, "cycle.age")?;
                let residual = if age >= 1 { 0 } else { 1 };
                c["entered_at"] = json!({"residual":{"value":residual.to_string()}});
            } else {
                c["entered_at"] = Value::Null;
            }
        }
        // 非运输格的年龄分组是审计编码；同物种总量参与全部守卫。
        if !transport {
            let mut counts = BTreeMap::new();
            for c in row["contents"].as_array().unwrap() {
                let item = c["item"].as_str().unwrap().to_string();
                let old = counts.get(&item).copied().unwrap_or(0);
                counts.insert(
                    item,
                    add(
                        old,
                        num(&c["quantity"], "cycle.inventory")?,
                        "cycle.inventory",
                    )?,
                );
            }
            row["contents"] = json!(counts
                .into_iter()
                .map(|(item, n)| { json!({"item":item,"quantity":q(n),"entered_at":null}) })
                .collect::<Vec<_>>());
        }
        row["contents"].as_array_mut().unwrap().sort_by_key(|c| {
            (
                c["item"].as_str().unwrap().to_string(),
                c["entered_at"].to_string(),
            )
        });
    }
    sort_rows(&mut s["inventory"], "slot");
    for row in s["progress"].as_array_mut().unwrap() {
        row["candidate_recipes"]
            .as_array_mut()
            .unwrap()
            .sort_by_key(Value::to_string);
        sort_rows(&mut row["cooldowns"], "slot");
    }
    sort_rows(&mut s["progress"], "unit");
    let lg = &mut s["logistics"];
    for k in ["active_channels", "blocked_channels"] {
        lg[k].as_array_mut().unwrap().sort_by_key(Value::to_string);
    }
    let sides = lg["poll_memory"]["value"]["sides"].as_array_mut().unwrap();
    sides.sort_by_key(|r| {
        (
            r["unit"].as_str().unwrap().to_string(),
            r["side"].as_str().unwrap().to_string(),
            r["axis"].as_str().unwrap_or("").to_string(),
        )
    });
    for r in sides {
        sort_rows(&mut r["levels"], "id");
    }
    for r in lg["gate_counters"].as_array_mut().unwrap() {
        r["blocked_reasons"]
            .as_array_mut()
            .unwrap()
            .sort_by_key(Value::to_string);
        let uid = r["unit"].as_str().unwrap();
        let limit = &input.gate_settings[uid]["total_limit"];
        r["total_received"] = if limit.is_null() {
            Value::Null
        } else {
            q(num(&r["total_received"], "gate.total")?.min(num(limit, "gate.limit")?))
        };
        r["window_started_at"] = if r["window_started_at"].is_null() {
            json!({"phase":"idle"})
        } else {
            let elapsed = difference(
                t,
                instant(&r["window_started_at"], "elapsed")?,
                "cycle.elapsed",
            )?;
            let remaining = input.catalog.kinds["物品准入口"].window - elapsed;
            if remaining <= 0 || elapsed < 0 {
                return Err(Stop::invalid(
                    "cycle.window",
                    "闭包后窗口尚未维护或起点在未来",
                ));
            }
            json!({"phase":"active","received":num(&r["window_received"], "gate.window")?,
                "remaining":{"value":remaining.to_string()}})
        };
    }
    sort_rows(&mut lg["gate_counters"], "unit");
    s["environment"]["time"] = tv(0);
    let sc = &mut s["semantic_context"];
    sort_rows(&mut sc["parameter_values"], "axis");
    sc["judgment_context"]["value"] =
        json!({"instant":tv(0),"phase":"after_closure","order_scope":"global"});
    for r in sc["pending_events"]["value"].as_array_mut().unwrap() {
        // 转移§6.2：Engine公开状态可被调用方改写，判等入口也须拒绝未知trigger扩展。
        fields(&r["trigger"], "kind value", "pending_events.trigger")?;
        if r["trigger"]["kind"] != "at_time"
            || r["predecessors"] != json!([])
            || r["status"] != "waiting"
            || !["manufacture_complete", "gate_window_expiry"]
                .contains(&r["operation"].as_str().unwrap_or(""))
        {
            return Err(Stop::unsupported(
                "cycle.domain.D4",
                "pending_events",
                "待办超出生产键定义域",
            ));
        }
        let remaining = if r["operation"] == "manufacture_complete" {
            let progress = state
                .progress
                .iter()
                .find(|p| r["target"] == p.unit)
                .ok_or_else(|| Stop::invalid("cycle.pending", "完成事件缺制造进度"))?;
            r["trigger"]["kind"] = json!("remaining_work");
            progress
                .remaining
                .as_ref()
                .ok_or_else(|| Stop::invalid("cycle.pending", "缺剩余工作量"))?
                .integer("cycle.pending")?
        } else {
            difference(
                instant(&r["trigger"]["value"], "pending")?,
                t,
                "cycle.pending",
            )?
        };
        r["event"] = json!([r["operation"], r["target"], remaining.to_string()]);
        r["trigger"]["value"] = tv(remaining);
    }
    sc["pending_events"]["value"]
        .as_array_mut()
        .unwrap()
        .sort_by_key(|r| {
            (
                r["operation"].to_string(),
                r["target"].to_string(),
                r["trigger"]["value"]["value"]["value"].to_string(),
            )
        });
    let tc = &mut sc["tick_context"]["value"];
    for k in ["window_start", "window_end"] {
        tc[k] = tv(difference(instant(&tc[k], k)?, t, k)?);
    }
    if instant(&tc["window_start"], "start")? != 0 || instant(&tc["window_end"], "end")? != 1 {
        return Err(Stop::invalid("cycle.tick_context", "窗口不等于[0,1)"));
    }
    tc["port_usage"]
        .as_array_mut()
        .unwrap()
        .retain(|r| num(&r["quantity"], "port_usage").is_ok_and(|n| n != 0));
    sort_rows(&mut tc["port_usage"], "port");
    tc.as_object_mut().unwrap().remove("movements");
    tc.as_object_mut().unwrap().remove("internal_passages");
    normalize(&mut s)?;
    Ok(
        json!({"schema":"phase-cycle-key-v1","domain":"phase_production_v1","state":s,"product_acceptance":PRODUCTS.map(|item|json!({"item":item,"state":"receivable_at_all_checks"}))}),
    )
}

/// 输出§5.3：恢复完整检查点，参数及历史原封不动；活动日程由种子继续注册。
pub fn checkpoint_input(input: &Input, state: Value, _config: &Config) -> Result<Input> {
    let mut raw = input.raw.clone();
    raw["initial_state"]["nonwarehouse"]["value"] = state;
    // 初始transfer.phase属于固定三元组，续跑时不是新初相位。检查入口显式标识检查点。
    let mut resumed = input.clone();
    resumed.raw = raw;
    Ok(resumed)
}

fn stop_value(stop: &Stop, time: i64, events: &[crate::model::Event]) -> Value {
    json!({"kind":if stop.status=="inconclusive" {"resource"}else{stop.status.as_str()},"axis":stop.axis,"event":stop.location,"time":tv(time),"reason":stop.reason,"partial_events":events})
}
fn acceptance(engine: &Engine) -> Result<Value> {
    let report = engine.acceptance_report()?;
    Ok(
        json!({"time":report["time"],"products":report["products"].as_array().unwrap().iter().map(|p|json!({"item":p["item"],"capacity_available":p["capacity_available"],"physical_path_exists":p["physical_path_exists"],"selected_acceptance":p["capacity_and_path"]})).collect::<Vec<_>>()}),
    )
}

fn mapping_source() -> Result<Value> {
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("周期键读取审计.md");
    Ok(json!({"path":path,"sha256":sha256(&path)?}))
}
fn reception_scope(a: i64, b: i64, proof: &Value) -> Value {
    json!({"checks":"all_candidate_and_actual_checks","interval":format!("({a},{b}]，全部候选查询及实际提交"),
        "state_coverage":"D.1—D.5通过的生产代表；每刻先归零成品，结构入量界保证整刻接收容量",
        "recovery_state_coverage":"此证据限持续接收区间；接收中断后的恢复状态集合待联合证明",
        "status":"proved","proof_sources":[proof]})
}
fn correspondence(proof: &Value) -> Value {
    let group = |names: &[&str], status: &str, why: &str| {
        json!({"status":status,"proof_sources":[],
        "checks":names.iter().map(|name| json!({"condition":name,"status":status,"evidence":[why]})).collect::<Vec<_>>()})
    };
    let mut forward = group(
        &[
            "production_representation",
            "warehouse_label_noninterference",
            "candidate_and_actual_acceptance",
            "successor_time_delivery_preservation",
        ],
        "unresolved",
        "字段投影及代表接收经实现读取核对；一般真实事件推进到工程闭包的PC-06对应仍缺推导",
    );
    forward["proof_sources"] = json!([proof]);
    json!({"forward_projection":forward,
        "reverse_reconstruction":group(&["reachable_start","fixed_parameters","positive_real_duration","repeated_production",
            "periodic_withdrawal_program","withdrawal_prefix_legality","product_balance","ore_and_other_warehouse_restoration",
            "labels_and_all_effective_state_restoration","operation_precision"],"not_claimed",
            "当前只重放一个条件种子的工程生产前缀；完整真实循环复原逐项另证"),
        "all_reachable_cycles":group(&["all_initial_states","all_fixed_parameters","legal_offline_and_recovery",
            "all_real_cycle_projections","all_positive_duration_cycles"],"not_claimed",
            "单个种子及固定参数的受限运行，未提交全称覆盖证明")})
}

/// 搜索配置只改变存储与重放预算，不改变游戏参数。
#[derive(Clone, Debug)]
pub struct SearchOptions {
    pub checkpoint_interval: usize,
    #[cfg(test)]
    pub replay_limit: usize,
    pub record_path: Option<std::path::PathBuf>,
    #[cfg(test)]
    pub force_collision: bool,
}
impl Default for SearchOptions {
    fn default() -> Self {
        Self {
            checkpoint_interval: 32,
            #[cfg(test)]
            replay_limit: usize::MAX,
            record_path: None,
            #[cfg(test)]
            force_collision: false,
        }
    }
}
fn digest(key: &Value, options: &SearchOptions) -> String {
    #[cfg(test)]
    if options.force_collision {
        return "0".repeat(64);
    }
    let _ = options;
    crate::digest::sha256_bytes(key.to_string().as_bytes())
}
fn restore(input: &Input, state: &State, config: &Config, sweeps: usize) -> Result<Engine> {
    let mut engine = Engine::new_production(checkpoint_input(input, json!(state), config)?)?;
    engine.max_sweeps = sweeps;
    engine.set_cache_enabled(true);
    Ok(engine)
}
/// 输出§5.2：检查点重放到摘要桶内每个候选位置；失败不判周期。
fn restore_position(
    input: &Input,
    checkpoints: &BTreeMap<usize, State>,
    position: usize,
    config: &Config,
    sweeps: usize,
    remaining: &mut usize,
) -> Result<Engine> {
    let (index, state) = checkpoints.range(..=position).next_back().unwrap();
    let mut engine = restore(input, state, config, sweeps)?;
    for _ in *index..position {
        if *remaining == 0 {
            return Err(Stop::new(
                "inconclusive",
                "resource.replay",
                "cycle.collision_replay",
                "检查点消歧重放预算耗尽；未判定键相等",
            ));
        }
        *remaining -= 1;
        engine.step_compact()?;
    }
    Ok(engine)
}
/// 输出§5：默认库调用不写文件，使用无记录证书；CLI可显式保存独立记录。
pub fn run_cycle(
    input: Input,
    config: &Config,
    config_path: &Path,
    max_ticks: usize,
    max_sweeps: usize,
) -> Result<Value> {
    run_cycle_with_options(
        input,
        config,
        config_path,
        max_ticks,
        max_sweeps,
        &SearchOptions::default(),
    )
}
pub fn run_cycle_with_options(
    input: Input,
    config: &Config,
    config_path: &Path,
    max_ticks: usize,
    max_sweeps: usize,
    options: &SearchOptions,
) -> Result<Value> {
    if read_json(&input.path)? != input.raw {
        return Err(Stop::invalid(
            "replay_input_ref",
            "内存输入与持久来源不同；须先保存再产证",
        ));
    }
    let (mut result, record) = search(input, config, config_path, max_ticks, max_sweeps, options)?;
    if let (Some(path), Some(record)) = (&options.record_path, record) {
        crate::cycle_io::write_json(path, &record)?;
        result["run_record_ref"] = crate::cycle_io::artifact_ref(
            path,
            "kernel-output-v4/full_state_each_instant",
            record["producer"].clone(),
        )?;
    }
    Ok(result)
}
/// 不把逐刻记录与完整键留在seen；周期账只在找到完整重键后重建。
pub(crate) fn search(
    input: Input,
    config: &Config,
    config_path: &Path,
    max_ticks: usize,
    max_sweeps: usize,
    options: &SearchOptions,
) -> Result<(Value, Option<Value>)> {
    if max_ticks == 0 || max_sweeps == 0 || options.checkpoint_interval == 0 {
        return Err(Stop::invalid("cycle.budget", "预算及检查点间隔须正"));
    }
    let mut engine = Engine::new_production(input.clone())?;
    engine.max_sweeps = max_sweeps;
    engine.set_cache_enabled(true);
    let seed = engine.state.clone();
    let mut last = seed.clone();
    let mut checks = engine.domain_report("static");
    let mut stop = engine
        .production_domain()
        .err()
        .map(|e| stop_value(&e, engine.t, &[]));
    let mut stopped_in_step = false;
    let mut seen = BTreeMap::<String, Vec<usize>>::new();
    let mut checkpoints = BTreeMap::from([(0, seed.clone())]);
    let mut completed = 0;
    let mut found = None;
    // 故障注入只供回归；公开预算仍恰为契约的ticks/sweeps。
    #[cfg(test)]
    let mut replay_budget = options.replay_limit;
    #[cfg(not(test))]
    let mut replay_budget = usize::MAX;
    if stop.is_none() && seed.semantic_context.judgment_context.value["phase"] == "after_closure" {
        match engine.cycle_key() {
            Ok(k) => {
                seen.insert(digest(&k, options), vec![0]);
            }
            Err(e) => stop = Some(stop_value(&e, engine.t, &[])),
        }
    }
    while stop.is_none() && completed < max_ticks {
        if let Err(e) = engine.step_compact() {
            stopped_in_step = true;
            stop = Some(stop_value(&e, engine.t, &engine.records));
            break;
        }
        completed += 1;
        last = engine.state.clone();
        let key = match engine.cycle_key() {
            Ok(k) => k,
            Err(e) => {
                stop = Some(stop_value(&e, engine.t, &[]));
                break;
            }
        };
        let hash = digest(&key, options);
        if let Some(positions) = seen.get(&hash) {
            for position in positions {
                let restored = match restore_position(
                    &input,
                    &checkpoints,
                    *position,
                    config,
                    max_sweeps,
                    &mut replay_budget,
                ) {
                    Ok(e) => e,
                    Err(e) => {
                        stop = Some(stop_value(&e, engine.t, &[]));
                        break;
                    }
                };
                let candidate = restored.cycle_key()?;
                if candidate == key {
                    found = Some((restored.state, *position, candidate, key.clone()));
                    break;
                }
            }
        }
        if stop.is_some() || found.is_some() {
            break;
        }
        seen.entry(hash).or_default().push(completed);
        if completed % options.checkpoint_interval == 0 {
            checkpoints.insert(completed, last.clone());
        }
    }
    let mut cycle = Value::Null;
    let status = if let Some((start, index, start_key, end_key)) = found {
        let mut replay = restore(&input, &start, config, max_sweeps)?;
        let a = replay.t;
        let b = engine.t;
        let period = difference(b, a, "cycle.period")?;
        if period <= 0 || period as usize != completed - index {
            return Err(Stop::invalid("cycle.period", "端点与周期段不符"));
        }
        let mut ledger = Vec::new();
        let mut accept = Vec::new();
        let mut combined = crate::ledger::empty_ledger();
        for _ in index..completed {
            replay.step_compact()?;
            for f in FLOWS {
                combined[f]
                    .as_array_mut()
                    .unwrap()
                    .extend(replay.ledger[f].as_array().unwrap().iter().cloned());
            }
            ledger.push(json!({"time":tv(replay.t),"warehouse_ledger":replay.ledger}));
            accept.push(acceptance(&replay)?);
        }
        if json!(replay.state) != json!(last) {
            return Err(Stop::invalid("cycle.replay", "检查点重放完整终态不同"));
        }
        let totals = crate::ledger::totals(&combined)?;
        let rates:Vec<_>=PRODUCTS.iter().zip([(3i64,5i64),(11,20)]).map(|(item,(n,d))|{
            let inbound=totals.as_array().unwrap().iter().find(|r|r["item"]==*item).map(|r|num(&r["actual_inbound"],"rate")).transpose()?.unwrap_or(0);
            let cmp=(inbound as i128*d as i128).cmp(&(period as i128*n as i128));
            let comparison=match cmp{std::cmp::Ordering::Less=>"lt",std::cmp::Ordering::Equal=>"eq",std::cmp::Ordering::Greater=>"gt"};
            Ok(json!({"item":item,"inbound":q(inbound),"period":q(period),"average":{"value":rational(&format!("{inbound}/{period}"))?,"category":"算术推论"},"target":{"value":format!("{n}/{d}"),"category":"条文直引"},"comparison":comparison}))
        }).collect::<Result<_>>()?;
        let definition = config_path
            .parent()
            .unwrap()
            .join("受限转移定义.md")
            .canonicalize()
            .map_err(|e| Stop::invalid("normalization", e.to_string()))?;
        let mapping = mapping_source()?;
        cycle = json!({"period":q(period),"start_time":tv(a),"end_time":tv(b),"start_state":start,"end_state":last,"start_key":start_key,"end_key":end_key,
            "normalization":{"schema":"cycle-normalization-v2","definition":{"path":definition,"sha256":sha256(&definition)?},"basis":["受限转移定义§6.1–6.4：D域商转移及入库率保持"],"domain_checks":["D.1","D.2","D.3","D.4","D.5"],"mapping_proof":mapping},"ledger":ledger,"totals":totals,"rates":rates,"acceptance":accept,"reception_scope":reception_scope(a,b,&mapping),"correspondence":correspondence(&mapping)});
        checks = engine.domain_report("cycle");
        for row in checks.as_array_mut().unwrap() {
            row["evidence"].as_array_mut().unwrap().push(json!(format!(
                "已从原种子推进{completed}刻，且从周期起点独立重跑{period}刻；期间D守卫无停止"
            )));
        }
        // PC-06真实调度对应仍开放；即使工程率够高，也只交诊断周期。
        "diagnostic_cycle"
    } else if let Some(s) = &stop {
        if s["kind"] == "resource" {
            "inconclusive"
        } else if s["kind"] == "invalid_input" {
            "invalid_input"
        } else {
            "stopped"
        }
    } else {
        stop = Some(
            json!({"kind":"resource","axis":"resource.ticks","event":null,"time":last.environment.time,"reason":"时刻预算耗尽，未发现重键；不证明无循环","partial_events":[]}),
        );
        "inconclusive"
    };
    if cycle.is_null() && (completed > 0 || stopped_in_step) {
        checks = engine.domain_report("executed_prefix");
        if let Some(info) = &stop {
            for row in checks.as_array_mut().unwrap() {
                let number = row["condition"].as_str().unwrap().replace('.', "");
                if info["axis"].as_str().is_some_and(|s| s.ends_with(&number))
                    || (row["condition"] == "D.4"
                        && info["axis"]
                            .as_str()
                            .is_some_and(|s| s.starts_with("damping.")))
                {
                    row["status"] = json!(if info["kind"] == "unresolved" {
                        "unresolved"
                    } else {
                        "fail"
                    });
                    row["locations"] = json!([info["event"]]);
                    row["evidence"] = json!([info["reason"]]);
                }
            }
        }
    }
    let record = if options.record_path.is_some() {
        let mut replay = restore(&input, &seed, config, max_sweeps)?;
        replay.max_sweeps = max_sweeps;
        let mut record = output::run_record(
            replay,
            config,
            config_path,
            completed + usize::from(stopped_in_step),
            "full_state_each_instant",
            1,
        )?;
        if completed == 0 && !stopped_in_step {
            if let Some(s) = &stop {
                record["status"] = json!(if s["kind"] == "resource" {
                    "inconclusive"
                } else {
                    s["kind"].as_str().unwrap()
                });
                record["open_items"]
                    .as_array_mut()
                    .unwrap()
                    .push(json!(s["reason"]));
            }
        }
        Some(record)
    } else {
        None
    };
    let current = input.parameters.current();
    let mut axes = serde_json::Map::new();
    for (axis, row) in &config.axes {
        if row.disposition == Disposition::Input {
            axes.insert(axis.name().into(), current[axis.name()].0.clone());
        }
    }
    let reference = crate::cycle_io::artifact_ref(
        &input.path,
        "kernel-input-v3",
        crate::cycle_io::input_producer(),
    )?;
    let sources = output::fingerprints(&input, config_path, &[])?;
    let scope = output::evidence_scope("diagnostic", "diagnostic", &sources);
    Ok((
        json!({"schema":"kernel-cycle-v3","evidence_scope":scope,"environment_assumption":"仓库收得下成品。","result_id":format!("cycle:{}:{max_ticks}:{max_sweeps}",input.path.file_stem().and_then(|s|s.to_str()).unwrap_or("input")),"status":status,"level":if cycle.is_null(){Value::Null}else{json!("production_part")},"execution_mode":"production_abstraction","port_meeting":input.parameters.value(Axis::ConnectionPortMeeting)?,
        "seed":{"reachability":input.raw["initial_state"]["reachability"],"source_event":input.raw["initial_state"]["anchor"]["value"]["event"]},"parameter_point":{"assignment":input.raw["parameters"],"input_axes":axes},
        "reading":{"port_meeting":input.parameters.value(Axis::ConnectionPortMeeting)?,"warehouse_acceptance":input.parameters.value(Axis::WarehouseAcceptance)?,"acceptance_quantifier":input.parameters.value(Axis::WarehouseAcceptanceQuantifier)?,"cycle_interpretation":"production_projection","remaining_assumptions":["shared_edge_opposite及kernel_profile_v1固定受限转移","条件种子的可达性证据按输入单列"]},
        "support_domain":{"name":"phase_production_v1","uncovered":["D域外库存抽象","具体完整基地周期复原","种子/参数/读法族全称覆盖"]},"domain_report":checks,"fingerprints":sources,"record_mode":if options.record_path.is_some(){"referenced"}else{"none"},"replay_input_ref":reference,"run_record_ref":null,"last_state":if cycle.is_null(){json!(last)}else{Value::Null},"cycle":cycle,"stop":stop,"budget":{"max_ticks":max_ticks,"max_sweeps":max_sweeps,"completed_ticks":completed},"open_items":["工程生产周期按diagnostic_cycle交付，平均率保留实际计算结果","PC-06：一般双端协调、失败环真实唤醒及关闭intake对应待证明","反向完整周期、全部初态/固定参数/离线恢复与全部可达循环逐项待证","整数固定环境为本次支持域；实数时间有限化仍待证明"]}),
        record,
    ))
}

pub use crate::cycle_io::{attach_load_context, load_stopped_cycle, verify_cycle, verify_cycle_at};
