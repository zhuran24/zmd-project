use num_bigint::BigInt;
use num_rational::BigRational;
use num_traits::{One, Zero};
use serde::{Deserialize, Deserializer};
use std::collections::{BTreeMap, BTreeSet};
use std::str::FromStr;

pub type Rational = BigRational;
fn integer(n: i64) -> Rational {
    Rational::from_integer(n.into())
}
fn parse_rational(s: &str) -> Result<Rational, String> {
    let parts: Vec<_> = s.split('/').collect();
    if parts.is_empty() || parts.len() > 2 {
        return Err("有理数须为整数或分子/分母".into());
    }
    let n = BigInt::from_str(parts[0]).map_err(|_| "分子不是整数")?;
    let d = if parts.len() == 2 {
        BigInt::from_str(parts[1]).map_err(|_| "分母不是整数")?
    } else {
        BigInt::one()
    };
    if d <= BigInt::zero() {
        return Err("分母必须为正".into());
    }
    Ok(Rational::new(n, d))
}
#[derive(Debug, Clone)]
pub struct Quantity {
    pub value: Rational,
    pub category: String,
}
impl<'de> Deserialize<'de> for Quantity {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        #[derive(Deserialize)]
        #[serde(deny_unknown_fields)]
        struct Raw {
            value: String,
            category: String,
        }
        let r = Raw::deserialize(d)?;
        if !["条文直引", "算术推论", "候选", "启发式", "实测"].contains(&r.category.as_str())
        {
            return Err(serde::de::Error::custom("未知数字类别"));
        }
        Ok(Self {
            value: parse_rational(&r.value).map_err(serde::de::Error::custom)?,
            category: r.category,
        })
    }
}
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Plan {
    pub recipe: String,
    pub planned_batch_rate: Quantity,
    pub planned_mean_batch_interval: Quantity,
}
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Multi {
    pub arrival_composition_per_tick: String,
    pub synchronization: String,
    pub same_source: String,
}
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Machine {
    pub id: String,
    pub kind: String,
    pub recipes: Vec<Plan>,
    pub input_ports: Quantity,
    pub output_ports: Quantity,
    pub area: Quantity,
    pub orientation: Option<String>,
    pub multi_material: Option<Multi>,
}
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Identity {
    pub status: String,
    pub kind: Option<String>,
    pub side: Option<String>,
    pub index: Option<Quantity>,
}
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Source {
    pub id: String,
    pub item: String,
    pub identity: Identity,
    pub output_ports: Quantity,
}
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Via {
    pub bridge: Option<bool>,
    pub splitter: Option<bool>,
    pub merger: Option<bool>,
    pub gate: Option<bool>,
}
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LogicalFeed {
    pub id: String,
    pub source: String,
    pub source_recipe: Option<String>,
    pub source_port: String,
    pub target: String,
    pub target_recipe: Option<String>,
    pub target_port: String,
    pub item: String,
    pub planned_rate: Quantity,
    pub planned_full_speed: bool,
    pub proven_actual_rate: Option<Quantity>,
    pub via: Via,
}
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Fanout {
    pub machine: String,
    pub recipe: String,
    pub item: String,
    pub ports: Quantity,
    pub planned_port_rate: Quantity,
    pub planned_mean_batch_interval: Quantity,
    pub batch_size: Quantity,
    pub planned_shape: String,
    pub certification: String,
}
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Domain {
    pub left: Quantity,
    pub bottom: Quantity,
    pub core: Quantity,
    pub all_different: bool,
}
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Core {
    pub id: String,
    pub input_ports: Quantity,
    pub output_ports: Quantity,
    pub orientation: Option<String>,
}
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Contract {
    pub schema: String,
    pub candidate: String,
    pub rate_window: Quantity,
    pub model: String,
    pub planned_absent: Vec<String>,
    pub machines: Vec<Machine>,
    pub sources: Vec<Source>,
    pub logical_feeds: Vec<LogicalFeed>,
    pub fanouts: Vec<Fanout>,
    pub source_domain: Domain,
    pub core: Core,
    pub targets: BTreeMap<String, Quantity>,
}
#[derive(Debug, Deserialize)]
struct Recipe {
    id: String,
    kind: String,
    inputs: BTreeMap<String, Quantity>,
    outputs: BTreeMap<String, Quantity>,
    duration: Quantity,
}
#[derive(Debug, Deserialize)]
struct Rule {
    name: String,
    text: String,
    section: String,
    basis: String,
    obligation: Option<String>,
}
#[derive(Debug, Deserialize)]
struct UnitPorts {
    input_count: Quantity,
    output_count: Quantity,
}
#[derive(Debug, Deserialize)]
struct LowerBounds {
    machines: Quantity,
    input_channels: Quantity,
    output_channels: Quantity,
}
#[derive(Debug, Deserialize)]
struct UnitSpec {
    id: String,
    family: String,
    area: Quantity,
    ports: UnitPorts,
    static_lower_bounds: Option<LowerBounds>,
}
#[derive(Debug, Deserialize)]
struct Catalog {
    recipes: Vec<Recipe>,
    constraints: Vec<Rule>,
    units: Vec<UnitSpec>,
    version: String,
    task: TaskSpec,
    static_checks: StaticChecks,
}
#[derive(Debug, Deserialize)]
struct TaskSpec {
    targets: BTreeMap<String, Quantity>,
}
#[derive(Debug, Deserialize)]
struct Constant {
    quantity: Quantity,
    basis: String,
}
#[derive(Debug, Deserialize)]
struct StaticChecks {
    constants: BTreeMap<String, Constant>,
    material_flow: BTreeMap<String, Quantity>,
}
impl Catalog {
    fn number(&self, key: &str) -> Rational {
        self.static_checks.constants[key].quantity.value.clone()
    }
    fn count(&self, key: &str) -> i64 {
        self.static_checks.constants[key].quantity.as_i64()
    }
}
fn catalog() -> Catalog {
    serde_json::from_str(include_str!("../../../数据/正式静态目录.json")).expect("内置正式目录损坏")
}

pub fn load(text: &str) -> Result<Contract, String> {
    let value: serde_json::Value = serde_json::from_str(text).map_err(|e| e.to_string())?;
    // 空值也必须显式存在，防止把缺字段当成尚未证明。
    fn required(v: &serde_json::Value, fields: &[&str]) -> Result<(), String> {
        for f in fields {
            if v.get(*f).is_none() {
                return Err(format!("缺少必需字段 {f}"));
            }
        }
        Ok(())
    }
    required(
        &value,
        &[
            "schema",
            "candidate",
            "rate_window",
            "model",
            "planned_absent",
            "machines",
            "sources",
            "logical_feeds",
            "fanouts",
            "source_domain",
            "core",
            "targets",
        ],
    )?;
    for c in value["logical_feeds"]
        .as_array()
        .ok_or("logical_feeds 必须为数组")?
    {
        required(
            c,
            &[
                "source_recipe",
                "target_recipe",
                "proven_actual_rate",
                "via",
            ],
        )?;
        required(&c["via"], &["bridge", "splitter", "merger", "gate"])?;
    }
    for m in value["machines"].as_array().ok_or("machines 必须为数组")? {
        required(m, &["orientation", "multi_material"])?;
    }
    for s in value["sources"].as_array().ok_or("sources 必须为数组")? {
        required(&s["identity"], &["status", "kind", "side", "index"])?;
    }
    required(&value["core"], &["orientation"])?;
    serde_json::from_value(value).map_err(|e| e.to_string())
}
#[derive(Debug, PartialEq, Eq, Clone, Copy)]
pub enum Status {
    Pass,
    Fail,
    Unknown,
}
impl Status {
    fn label(self) -> &'static str {
        match self {
            Self::Pass => "能检且通过",
            Self::Fail => "能检且不通过",
            Self::Unknown => "不能静态检",
        }
    }
}
#[derive(Debug)]
pub struct Check {
    pub name: String,
    pub status: Status,
    pub detail: String,
}
#[derive(Debug, Default)]
pub struct Report {
    pub checks: Vec<Check>,
}
impl Report {
    fn check(&mut self, name: impl Into<String>, ok: bool, detail: impl Into<String>) {
        self.checks.push(Check {
            name: name.into(),
            status: if ok { Status::Pass } else { Status::Fail },
            detail: detail.into(),
        });
    }
    fn unknown(&mut self, name: impl Into<String>, detail: impl Into<String>) {
        self.checks.push(Check {
            name: name.into(),
            status: Status::Unknown,
            detail: detail.into(),
        });
    }
    pub fn failures(&self) -> usize {
        self.checks
            .iter()
            .filter(|c| c.status == Status::Fail)
            .count()
    }
    pub fn markdown(&self) -> String {
        let mut s=String::from("# 候选 B 静态校验报告\n\n状态：静态计划检查完成；运行认证未完成。\n\n检查依据为内置《游戏规则》《求解任务》《求解约束》静态目录，目录自带 version、sources 三份正式来源全文与 SHA-256。通过仅表示输入计划满足被列出的算术或结构投影，不代表实际产率、可嵌入性、起动或全部可达循环态达标。数值分类：观测计数、配方运算与条件代入为算术推论（以候选为前提）；正式条文直接给出的阈值为条文直引；候选交接回归的预期值与计划形状算法为候选。归一化制造负荷上限 1、满载等式 1、专用端口双射等式、无箱代入的 η 与接口下限均为算术推论，不是条文原数。逐行说明列出这些例外。\n\n");
        for status in [Status::Pass, Status::Fail, Status::Unknown] {
            let rows: Vec<_> = self.checks.iter().filter(|c| c.status == status).collect();
            s += &format!("## {}（{} 项，算术推论）\n\n", status.label(), rows.len());
            if rows.is_empty() {
                s += "无。\n\n";
                continue;
            }
            s += "| 检查项／据 | 结果与覆盖边界 |\n|---|---|\n";
            for c in rows {
                s += &format!(
                    "| {} | {} |\n",
                    c.name.replace('|', "／"),
                    c.detail.replace('|', "／").replace('\n', " ")
                );
            }
            s += '\n'.to_string().as_str();
        }
        s
    }
}
fn sum<I: Iterator<Item = Rational>>(iter: I) -> Rational {
    iter.fold(Rational::zero(), |a, b| a + b)
}
fn qmap(map: &BTreeMap<String, Rational>, key: &str) -> Rational {
    map.get(key).cloned().unwrap_or_default()
}
fn add(map: &mut BTreeMap<String, Rational>, key: &str, value: Rational) {
    *map.entry(key.into()).or_default() += value;
}
/// 物料需求按制造或外部来源的首次发出计量；箱体中转不是新增物料。
/// 带箱候选仍被当前格式拒绝；此函数仅固定未来分段时不得重复计量的边界。
pub fn material_origin_flow(c: &Contract) -> BTreeMap<String, Rational> {
    let origins: BTreeSet<_> = c
        .machines
        .iter()
        .map(|m| m.id.as_str())
        .chain(c.sources.iter().map(|s| s.id.as_str()))
        .collect();
    let mut flow = BTreeMap::new();
    for e in &c.logical_feeds {
        if origins.contains(e.source.as_str()) {
            add(&mut flow, &e.item, e.planned_rate.value.clone());
        }
    }
    flow
}

fn check_categories(c: &Contract, cat: &Catalog, r: &mut Report) {
    let mut wrong = Vec::new();
    let mut check = |path: String, q: &Quantity, expected: &str| {
        if q.category != expected {
            wrong.push(format!("{path}: {}，应为{expected}", q.category));
        }
    };
    check("rate_window".into(), &c.rate_window, "候选");
    for m in &c.machines {
        if let Some(u) = cat.units.iter().find(|u| u.id == m.kind) {
            check(
                format!("{}/input_ports", m.id),
                &m.input_ports,
                &u.ports.input_count.category,
            );
            check(
                format!("{}/output_ports", m.id),
                &m.output_ports,
                &u.ports.output_count.category,
            );
            check(format!("{}/area", m.id), &m.area, &u.area.category);
        }
        for p in &m.recipes {
            check(
                format!("{}/{}/rate", m.id, p.recipe),
                &p.planned_batch_rate,
                "候选",
            );
            check(
                format!("{}/{}/interval", m.id, p.recipe),
                &p.planned_mean_batch_interval,
                "候选",
            );
        }
    }
    for s in &c.sources {
        check(
            format!("{}/output_ports", s.id),
            &s.output_ports,
            "条文直引",
        );
        if let Some(q) = &s.identity.index {
            check(format!("{}/index", s.id), q, "候选");
        }
    }
    for (name, q) in [
        ("left", &c.source_domain.left),
        ("bottom", &c.source_domain.bottom),
        ("core", &c.source_domain.core),
        ("core/input", &c.core.input_ports),
        ("core/output", &c.core.output_ports),
    ] {
        check(name.into(), q, "条文直引");
    }
    for e in &c.logical_feeds {
        check(format!("{}/planned_rate", e.id), &e.planned_rate, "候选");
        if let Some(q) = &e.proven_actual_rate {
            check(format!("{}/actual_rate", e.id), q, "实测");
        }
    }
    for f in &c.fanouts {
        for (name, q) in [
            ("ports", &f.ports),
            ("rate", &f.planned_port_rate),
            ("interval", &f.planned_mean_batch_interval),
        ] {
            check(format!("{}/{name}", f.machine), q, "候选");
        }
        check(
            format!("{}/batch_size", f.machine),
            &f.batch_size,
            "条文直引",
        );
    }
    for (name, q) in &c.targets {
        check(format!("targets/{name}"), q, "条文直引");
    }
    r.check(
        "契约/数字类别",
        wrong.is_empty(),
        if wrong.is_empty() {
            "各字段类别符合目录属性或契约角色；类别正确不构成运行证据".into()
        } else {
            wrong.join("；")
        },
    );
}
fn spec(cat: &Catalog, kind: &str) -> Option<(i64, i64, i64)> {
    let u = cat
        .units
        .iter()
        .find(|u| u.id == kind && u.family == "manufacturing")?;
    Some((
        u.ports.input_count.as_i64(),
        u.ports.output_count.as_i64(),
        u.area.as_i64(),
    ))
}
impl Quantity {
    fn as_i64(&self) -> i64 {
        assert!(self.value.is_integer(), "目录整数属性不是整数");
        self.value
            .to_integer()
            .to_string()
            .parse()
            .expect("目录整数超界")
    }
}
/// 按非运输端点的不同端口计S、R；输入必须已在每个储存箱处切段。
/// 不统计运输之间的实体通道，也不把缓存内部通道计入S、R。
pub fn feed_interface_counts(feeds: &[LogicalFeed]) -> (usize, usize) {
    let sources: BTreeSet<_> = feeds.iter().map(|e| (&e.source, &e.source_port)).collect();
    let targets: BTreeSet<_> = feeds.iter().map(|e| (&e.target, &e.target_port)).collect();
    (sources.len(), targets.len())
}

pub fn validate(c: &Contract) -> Report {
    let mut r = Report::default();
    let cat = catalog();
    check_categories(c, &cat, &mut r);
    r.check("目录/版本",true,format!("内置共享目录 {}；指纹、分节与据均在正式静态目录.json；源变动须运行 formal_catalog.py 并重新构建",cat.version));
    for (key, value) in &cat.static_checks.constants {
        r.check(
            format!("目录/阈值/{key}"),
            value.quantity.category == "条文直引",
            format!(
                "{}（条文直引）；据：{}；转录一致性由回源自查验证",
                value.quantity.value, value.basis
            ),
        );
    }
    let port_rate = cat.number("port_rate");
    let core_spec = cat
        .units
        .iter()
        .find(|u| u.id == "协议核心")
        .expect("目录缺核心");
    let recipes: BTreeMap<_, _> = cat.recipes.iter().map(|v| (v.id.as_str(), v)).collect();
    let machines: BTreeMap<_, _> = c.machines.iter().map(|m| (m.id.as_str(), m)).collect();
    let sources: BTreeMap<_, _> = c.sources.iter().map(|s| (s.id.as_str(), s)).collect();
    r.check(
        "契约/版本",
        c.schema == "feeding-v2" && c.candidate == "候选B",
        "只支持 feeding-v2 的候选B；包含候选交接回归，不是通用布局验收器",
    );
    let ids: BTreeSet<_> = c
        .machines
        .iter()
        .map(|m| &m.id)
        .chain(c.sources.iter().map(|s| &s.id))
        .chain(std::iter::once(&c.core.id))
        .collect();
    r.check(
        "契约/唯一身份",
        ids.len() == c.machines.len() + c.sources.len() + 1
            && c.logical_feeds
                .iter()
                .map(|e| &e.id)
                .collect::<BTreeSet<_>>()
                .len()
                == c.logical_feeds.len(),
        "机器、来源、核心与通道身份不可重复",
    );
    r.check(
        "契约/速率窗口",
        c.rate_window.value > Rational::zero(),
        format!(
            "窗口={} tick（候选），未解释为运行周期",
            c.rate_window.value
        ),
    );
    r.check(
        "协议核心/端口",
        c.core.input_ports.value == core_spec.ports.input_count.value
            && c.core.output_ports.value == core_spec.ports.output_count.value,
        "存货端口 14、取货端口 6；据：协议核心",
    );
    let domain = &c.source_domain;
    r.check(
        "出库上限/来源变量域",
        domain.left.value == cat.number("source_per_side")
            && domain.bottom.value == cat.number("source_per_side")
            && domain.core.value == core_spec.ports.output_count.value
            && domain.all_different,
        "来源变量域：左 23、下 23、核心 6，全部互异；未求物理指派",
    );
    let private = c
        .planned_absent
        .iter()
        .map(String::as_str)
        .collect::<BTreeSet<_>>()
        == BTreeSet::from(["splitter", "merger", "gate", "storage"]);
    r.check("契约/受限模型",private,"本版校验器支持无分流、汇流、准入口、储存箱的专用逻辑送料记录；不支持的模型报失败，不外推为物理不可行");
    let mut assigned = BTreeSet::new();
    for s in &c.sources {
        let ident = &s.identity;
        let valid = match ident.status.as_str() {
            "待求" => ident.kind.is_none() && ident.side.is_none() && ident.index.is_none(),
            "已指定" => {
                let max = match (ident.kind.as_deref(), ident.side.as_deref()) {
                    (Some("仓库取货口"), Some("左边界" | "下边界")) => {
                        cat.count("source_per_side")
                    }
                    (Some("协议核心"), None) => core_spec.ports.output_count.as_i64(),
                    _ => 0,
                };
                ident.index.as_ref().is_some_and(|q| {
                    q.value.is_integer()
                        && q.value >= integer(1)
                        && q.value <= integer(max)
                        && assigned.insert(format!("{:?}:{:?}:{}", ident.kind, ident.side, q.value))
                })
            }
            _ => false,
        };
        r.check(
            format!("来源端口身份/{}", s.id),
            valid
                && s.output_ports.value == integer(1)
                && ["源矿", "蓝铁矿"].contains(&s.item.as_str()),
            "待求变量须显式留空；已指定身份须在域内且互异；仅原矿、单取货端口",
        );
    }
    let mut in_ports: BTreeMap<(&str, &str), Rational> = BTreeMap::new();
    let mut out_ports: BTreeMap<(&str, &str), Rational> = BTreeMap::new();
    let mut port_links: BTreeMap<(&str, &str), (&str, &str)> = BTreeMap::new();
    let mut reverse_links: BTreeMap<(&str, &str), (&str, &str)> = BTreeMap::new();
    let mut in_owner: BTreeMap<&str, &str> = BTreeMap::new();
    let mut out_owner: BTreeMap<&str, &str> = BTreeMap::new();
    for e in &c.logical_feeds {
        r.check(
            format!("契约/送料身份/{}", e.id),
            e.id.strip_prefix("LF").is_some_and(|suffix| {
                !suffix.is_empty() && suffix.bytes().all(|b| b.is_ascii_digit())
            }),
            "逻辑送料id须为LF加数字；PC实体通道与BC缓存内部通道不能混用",
        );
        let source_ok = if let Some(m) = machines.get(e.source.as_str()) {
            e.source_recipe.as_ref().is_some_and(|p| {
                m.recipes.iter().any(|a| &a.recipe == p)
                    && recipes
                        .get(p.as_str())
                        .is_some_and(|rr| rr.outputs.contains_key(&e.item))
            })
        } else {
            sources
                .get(e.source.as_str())
                .is_some_and(|s| s.item == e.item)
                && e.source_recipe.is_none()
        };
        let target_ok = if let Some(m) = machines.get(e.target.as_str()) {
            e.target_recipe.as_ref().is_some_and(|p| {
                m.recipes.iter().any(|a| &a.recipe == p)
                    && recipes
                        .get(p.as_str())
                        .is_some_and(|rr| rr.inputs.contains_key(&e.item))
            })
        } else {
            e.target == c.core.id && e.target_recipe.is_none()
        };
        r.check(
            format!("契约/送料引用/{}", e.id),
            source_ok && target_ok,
            "两端存在、配方属于该机、物品匹配配方；外部源无配方",
        );
        r.check(
            format!("满速独占/计划标记/{}", e.id),
            e.planned_full_speed == (e.planned_rate.value == port_rate),
            format!(
                "计划 {} 件/tick；满速标记={}（计划值比较的算术推论）；真实满速及沿途格独占待证",
                e.planned_rate.value, e.planned_full_speed
            ),
        );
        let source_key = (e.source.as_str(), e.source_port.as_str());
        let target_key = (e.target.as_str(), e.target_port.as_str());
        let link_ok = port_links
            .insert(source_key, target_key)
            .is_none_or(|old| old == target_key)
            && reverse_links
                .insert(target_key, source_key)
                .is_none_or(|old| old == source_key);
        let ports_ok = link_ok
            && !e.source_port.is_empty()
            && !e.target_port.is_empty()
            && out_owner
                .insert(&e.source_port, &e.source)
                .is_none_or(|old| old == e.source)
            && in_owner
                .insert(&e.target_port, &e.target)
                .is_none_or(|old| old == e.target);
        r.check(format!("契约/端口身份/{}",e.id),ports_ok,"端口有身份且不跨单位复用；专用通道端点一一对应；同一对端点的多条配方物品记录合计检查容量");
        *out_ports.entry((&e.source, &e.source_port)).or_default() += &e.planned_rate.value;
        *in_ports.entry((&e.target, &e.target_port)).or_default() += &e.planned_rate.value;
        r.check(
            format!("端口速率/记录/{}", e.id),
            e.planned_rate.value > Rational::zero() && e.planned_rate.value <= port_rate,
            format!("计划 {} 件/tick；须大于零且不超过 1", e.planned_rate.value),
        );
        r.check(
            format!("契约/实际速率/{}", e.id),
            e.proven_actual_rate.is_none(),
            "本版不认证执行证书，已证实际速率必须为空",
        );
        r.check(
            format!("契约/运输占位/{}", e.id),
            [e.via.splitter, e.via.merger, e.via.gate]
                .iter()
                .all(|v| v.is_none() || *v == Some(false)),
            "受限模型排除分流、汇流、准入口；储存箱必须成为分段端点且本版不支持，via不允许storage字段；空桥接器栏表示未知",
        );
    }
    for (side, ports) in [("存货", &in_ports), ("取货", &out_ports)] {
        for ((id, p), v) in ports {
            r.check(
                format!("端口速率/{side}/{id}/{p}"),
                v <= &port_rate,
                format!("端口各记录合计 {v} 件/tick ≤1"),
            );
        }
    }
    let incoming = |id: &str| in_ports.keys().filter(|(m, _)| *m == id).count() as i64;
    let outgoing = |id: &str| out_ports.keys().filter(|(m, _)| *m == id).count() as i64;
    let mut production = BTreeMap::new();
    let mut consumption = BTreeMap::new();
    let mut batch_totals = BTreeMap::new();
    for m in &c.machines {
        let Some((cap_in, cap_out, area)) = spec(&cat, &m.kind) else {
            r.check(format!("机型/{}", m.id), false, "未知机型");
            continue;
        };
        r.check(
            format!("端口数/{}", m.id),
            m.input_ports.value == integer(cap_in)
                && m.output_ports.value == integer(cap_out)
                && incoming(&m.id) <= cap_in
                && outgoing(&m.id) <= cap_out,
            format!(
                "存货 {}、取货 {}、存货上限 {cap_in}、取货上限 {cap_out}；据：制造单位",
                incoming(&m.id),
                outgoing(&m.id)
            ),
        );
        r.check(
            format!("占地/{}", m.id),
            m.area.value == integer(area),
            format!("机型面积 {area} 格；非几何摆放检查"),
        );
        r.check(
            format!("契约/配方集/{}", m.id),
            !m.recipes.is_empty()
                && m.recipes
                    .iter()
                    .map(|p| &p.recipe)
                    .collect::<BTreeSet<_>>()
                    .len()
                    == m.recipes.len(),
            "配方集非空且不重复，支持多配方计划",
        );
        let mut busy = Rational::zero();
        let mut multi = m.recipes.len() > 1 || incoming(&m.id) > 1;
        for p in &m.recipes {
            let Some(rec) = recipes.get(p.recipe.as_str()) else {
                r.check(format!("配方/{}", m.id), false, "未知配方");
                continue;
            };
            multi |= rec.inputs.len() > 1;
            r.check(
                format!("配方/{}／{}", m.id, p.recipe),
                rec.kind == m.kind
                    && p.planned_batch_rate.value > Rational::zero()
                    && &p.planned_mean_batch_interval.value * &p.planned_batch_rate.value
                        == Rational::one(),
                "配方机型匹配、计划批次率为正、计划平均批间隔是批次率倒数（不是确定间隔）",
            );
            busy += &p.planned_batch_rate.value * &rec.duration.value;
            add(
                &mut batch_totals,
                &p.recipe,
                p.planned_batch_rate.value.clone(),
            );
            for (side, terms) in [("输入", &rec.inputs), ("输出", &rec.outputs)] {
                for (item, q) in terms {
                    let expected = &p.planned_batch_rate.value * &q.value;
                    let actual = sum(c
                        .logical_feeds
                        .iter()
                        .filter(|e| {
                            if side == "输入" {
                                e.target == m.id
                                    && e.target_recipe.as_ref() == Some(&p.recipe)
                                    && &e.item == item
                            } else {
                                e.source == m.id
                                    && e.source_recipe.as_ref() == Some(&p.recipe)
                                    && &e.item == item
                            }
                        })
                        .map(|e| e.planned_rate.value.clone()));
                    r.check(
                        format!("逐机配方守恒/{}/{}/{side}/{item}", m.id, p.recipe),
                        actual == expected,
                        format!("计划通道合计 {actual}，配方要求 {expected} 件/tick；据：配方"),
                    );
                    add(
                        if side == "输入" {
                            &mut consumption
                        } else {
                            &mut production
                        },
                        item,
                        expected,
                    );
                }
            }
        }
        r.check(
            format!("制造能力/{}", m.id),
            busy <= Rational::one(),
            format!("各配方批次率×耗时之和 {busy} ≤1（单位时间占用上限的算术推论）；据：制造、缓存格、配方"),
        );
        r.check(
            format!("契约/多料栏/{}", m.id),
            if multi {
                m.multi_material.as_ref().is_some_and(|x| {
                    x.arrival_composition_per_tick == "待验"
                        && x.synchronization == "待验"
                        && x.same_source == "待验"
                })
            } else {
                m.multi_material.is_none()
            },
            "多物品输入、多配方或多输入端口任一触发时三栏均须待验；其余为空不免除运行义务",
        );
    }
    let mut external = BTreeMap::new();
    let mut delivered = BTreeMap::new();
    let throughput = material_origin_flow(c);
    for e in &c.logical_feeds {
        if sources.contains_key(e.source.as_str()) {
            add(&mut external, &e.item, e.planned_rate.value.clone());
        }
        if e.target == c.core.id {
            add(&mut delivered, &e.item, e.planned_rate.value.clone());
        }
    }
    for item in production
        .keys()
        .chain(consumption.keys())
        .chain(external.keys())
        .chain(delivered.keys())
        .collect::<BTreeSet<_>>()
    {
        let supply = qmap(&production, item) + qmap(&external, item);
        let demand = qmap(&consumption, item) + qmap(&delivered, item);
        r.check(
            format!("全局守恒/{item}"),
            supply == demand,
            format!("产出+出库 {supply} = 消耗+入库 {demand} 件/tick"),
        );
    }
    for (item, target_q) in &cat.task.targets {
        let target = target_q.value.clone();
        r.check(
            format!("目标/{item}"),
            c.targets.get(item).is_some_and(|v| v.value == target)
                && qmap(&delivered, item) == target,
            format!(
                "计划入库 {}，目标 {target} 件/tick；据：目标、周期倍数",
                qmap(&delivered, item)
            ),
        );
    }
    r.check(
        "目标/项目集",
        c.targets.len() == cat.task.targets.len(),
        "目标恰含两种正式成品",
    );
    let counts = |kind: &str| c.machines.iter().filter(|m| m.kind == kind).count() as i64;
    for unit in cat.units.iter().filter(|u| u.family == "manufacturing") {
        let kind = unit.id.as_str();
        let bounds = unit
            .static_lower_bounds
            .as_ref()
            .expect("制造单位缺少正式下限");
        let (low, inc, outc) = (
            bounds.machines.as_i64(),
            bounds.input_channels.as_i64(),
            bounds.output_channels.as_i64(),
        );
        let ms: Vec<_> = c.machines.iter().filter(|m| m.kind == kind).collect();
        r.check(
            format!("机型下限/{kind}"),
            counts(kind) >= low,
            format!("{} ≥ {low}", counts(kind)),
        );
        let ni: i64 = ms.iter().map(|m| incoming(&m.id)).sum();
        let no: i64 = ms.iter().map(|m| outgoing(&m.id)).sum();
        r.check(
            format!("通道下限/{kind}"),
            ni >= inc && no >= outc,
            format!("存货 {ni} ≥{inc}；取货 {no} ≥{outc}"),
        );
        if ["粉碎机", "精炼炉", "配件机", "种植机", "采种机", "封装机"].contains(&kind)
            && counts(kind) == low
        {
            for m in &ms {
                let load = sum(m.recipes.iter().filter_map(|p| {
                    recipes
                        .get(p.recipe.as_str())
                        .map(|rec| &rec.duration.value * &p.planned_batch_rate.value)
                }));
                r.check(
                    format!("满载配置/计划占用/{}", m.id),
                    load == Rational::one(),
                    format!("计划占用={load}；满载比较 load=1 为归一化算术推论；连续运行待证"),
                );
            }
            if kind == "采种机" {
                r.check(
                    "满载配置/采种混做",
                    ms.iter().any(|m| {
                        m.recipes.iter().any(|p| p.recipe == "采种-荞花")
                            && m.recipes.iter().any(|p| p.recipe == "采种-砂叶")
                    }),
                    "恰下限时须有处理两种植物的计划",
                );
            }
            if kind == "粉碎机" {
                for rid in ["粉碎-荞花", "粉碎-砂叶"] {
                    r.check(
                        format!("满载配置/混做/{rid}"),
                        ms.iter().any(|m| {
                            m.recipes.len() > 1 && m.recipes.iter().any(|p| p.recipe == rid)
                        }),
                        "恰下限时该植物的粉碎机中须有混做计划",
                    );
                }
            }
        }
    }
    let count_in = |kind: &str, n: i64| {
        c.machines
            .iter()
            .filter(|m| m.kind == kind && incoming(&m.id) >= n)
            .count() as i64
    };
    r.check(
        "研磨进料/研磨",
        counts("研磨机") != cat.count("grinder_trigger")
            || count_in("研磨机", cat.count("grinder_inputs")) >= cat.count("grinder_count"),
        format!(
            "至少 {} 输入的研磨机 {}/{}",
            cat.count("grinder_inputs"),
            count_in("研磨机", cat.count("grinder_inputs")),
            counts("研磨机")
        ),
    );
    r.check(
        "研磨进料/塑形",
        counts("塑形机") != cat.count("shaper_trigger")
            || count_in("塑形机", cat.count("shaper_inputs")) >= cat.count("shaper_count"),
        format!(
            "至少 {} 输入的塑形机 {}/{}",
            cat.count("shaper_inputs"),
            count_in("塑形机", cat.count("shaper_inputs")),
            counts("塑形机")
        ),
    );
    r.check(
        "研磨进料/采种",
        counts("采种机") != cat.count("seed_trigger")
            || c.machines
                .iter()
                .filter(|m| m.kind == "采种机")
                .all(|m| outgoing(&m.id) >= cat.count("seed_outputs")),
        "采种恰下限才触发逐机两输出要求",
    );
    for kind in ["封装机", "灌装机"] {
        let ms: Vec<_> = c.machines.iter().filter(|m| m.kind == kind).collect();
        let degree: Vec<_> = ms.iter().map(|m| incoming(&m.id)).collect();
        let valid = if kind == "封装机" {
            degree.iter().all(|v| *v >= cat.count("pack_inputs"))
                && ms.iter().all(|m| {
                    incoming(&m.id) != cat.count("pack_inputs")
                        || in_ports
                            .iter()
                            .filter(|((id, _), _)| *id == m.id)
                            .all(|(_, v)| v == &port_rate)
                })
        } else {
            count_in(kind, cat.count("fill_inputs")) >= cat.count("fill_count")
                && (count_in(kind, cat.count("fill_inputs")) != cat.count("fill_count")
                    || ms
                        .iter()
                        .filter(|m| incoming(&m.id) < cat.count("fill_inputs"))
                        .all(|m| {
                            incoming(&m.id) == cat.count("fill_other_inputs")
                                && in_ports
                                    .iter()
                                    .filter(|((id, _), _)| *id == m.id)
                                    .all(|(_, v)| v == &port_rate)
                        }))
        };
        r.check(
            format!("封装进料/{kind}"),
            counts(kind)
                != cat.count(if kind == "封装机" {
                    "pack_trigger"
                } else {
                    "fill_trigger"
                })
                || valid,
            format!("逐机输入端口数 {degree:?}；满速条款只核计划"),
        );
    }
    if counts("灌装机") == cat.count("fill_trigger")
        && count_in("灌装机", cat.count("fill_inputs")) == cat.count("fill_count")
    {
        r.check(
            "灌装混线/结构",
            false,
            "触发混线前提；本受限模型没有汇流器或储存箱，无法满足正式结构条件",
        );
    } else {
        r.check(
            "灌装混线/结构",
            true,
            "前提不触发：灌装总台数或至少四输入台数不满足条文合取前件；不宣称混线已经认证",
        );
    }
    let ore_ok = c.sources.len() as i64 == cat.count("ore_total")
        && c.sources.iter().all(|s| {
            outgoing(&s.id) == 1
                && c.logical_feeds
                    .iter()
                    .filter(|e| e.source == s.id)
                    .all(|e| e.planned_rate.value == port_rate)
        });
    r.check(
        "取货口配置/计划",
        ore_ok,
        "来源数、逐来源独立端口及计划满速；物理边界身份与运行满速另列待验",
    );
    let mut dedicated = BTreeSet::new();
    let mut ore_valid = true;
    for e in c
        .logical_feeds
        .iter()
        .filter(|e| sources.contains_key(e.source.as_str()))
    {
        let expected = if e.item == "源矿" {
            "粉碎-源矿"
        } else {
            "精炼-蓝铁矿"
        };
        let valid = machines.get(e.target.as_str()).is_some_and(|m| {
            m.recipes.len() == 1
                && m.recipes[0].recipe == expected
                && m.recipes[0].planned_batch_rate.value == Rational::one()
                && incoming(&m.id) == 1
        });
        ore_valid &= valid;
        if valid {
            dedicated.insert(&e.target);
        }
    }
    r.check(
        "矿线专机/计划",
        ore_valid && dedicated.len() as i64 == cat.count("ore_total"),
        "在无分流、无箱的专用通道计划中，每条原矿只进一台对应满批专机，无其他输入；实际运行待证",
    );
    let battery = qmap(&delivered, "高容谷地电池");
    let capsule = qmap(&delivered, "精选荞愈胶囊");
    r.check(
        "单位矿耗/矿石需求",
        qmap(&external, "蓝铁矿")
            == &battery * cat.number("battery_iron") + &capsule * cat.number("capsule_iron")
            && qmap(&external, "源矿") == &battery * cat.number("battery_ore")
            && qmap(&external, "蓝铁矿") == cat.static_checks.material_flow["蓝铁矿"].value
            && qmap(&external, "源矿") == cat.static_checks.material_flow["源矿"].value,
        format!(
            "蓝铁矿={}、源矿={}；分别核 {}×电池+{}×胶囊、{}×电池（系数来自目录条文直引）",
            qmap(&external, "蓝铁矿"),
            qmap(&external, "源矿"),
            cat.number("battery_iron"),
            cat.number("capsule_iron"),
            cat.number("battery_ore")
        ),
    );
    for plant in ["荞花", "砂叶"] {
        let seed = qmap(&batch_totals, &format!("采种-{plant}"));
        let crush = qmap(&batch_totals, &format!("粉碎-{plant}"));
        let grow = qmap(&batch_totals, &format!("种植-{plant}"));
        let plant_store = qmap(&delivered, plant);
        let seed_store = qmap(&delivered, &format!("{plant}种子"));
        r.check(format!("回路守恒/种子自给/{plant}"),seed==crush+&plant_store+&seed_store&&grow==&seed*&recipes[format!("采种-{plant}").as_str()].outputs[&format!("{plant}种子")].value-seed_store,format!("采种 {seed}、种植 {grow} 批/tick；核采种=粉碎+两类入库，种植=两倍采种−种子入库；不验证起动与库存"));
    }
    for (item, min_q) in &cat.static_checks.material_flow {
        let min = &min_q.value;
        r.check(
            format!("物料流量/{item}"),
            &qmap(&throughput, item) >= min,
            format!(
                "首次来源流量 {} ≥ {min} 件/tick；箱体普通端口外送不重复计入物料需求；据：物料流量",
                qmap(&throughput, item)
            ),
        );
    }
    r.check(
        "矿系不入库/计划",
        c.logical_feeds
            .iter()
            .filter(|e| e.target == c.core.id)
            .all(|e| {
                cat.task.targets.contains_key(&e.item)
                    || (counts("种植机") != cat.count("plant_trigger")
                        && [
                            "荞花",
                            "砂叶",
                            "荞花种子",
                            "砂叶种子",
                            "荞花粉末",
                            "砂叶粉末",
                            "细磨荞花粉末",
                        ]
                        .contains(&e.item.as_str()))
            }),
        format!(
            "种植机 {} 台；仅在台数等于正式下限时禁止植物系入库；无箱计划；据：矿系不入库",
            counts("种植机")
        ),
    );
    let core_in = incoming(&c.core.id);
    let product_core_inputs: BTreeSet<_> = c
        .logical_feeds
        .iter()
        .filter(|e| e.target == c.core.id && cat.task.targets.contains_key(&e.item))
        .map(|e| &e.target_port)
        .collect();
    let product_k = product_core_inputs.len() as i64;
    let product_sources: BTreeSet<_> = c
        .logical_feeds
        .iter()
        .filter(|e| e.target == c.core.id && cat.task.targets.contains_key(&e.item))
        .map(|e| &e.source)
        .collect();
    r.check(
        "成品汇入/通道下限/入库途径",
        product_k >= cat.count("product_inputs")
            && core_in <= core_spec.ports.input_count.as_i64()
            && product_sources.len() as i64 >= cat.count("product_sources")
            && product_k >= cat.count("product_sources"),
        format!(
            "成品核心输入 K={product_k}；成品来源={}；B=C=0（候选），K≥6 是成品汇入的条件代入（算术推论），不是一般形式",
            product_sources.len()
        ),
    );
    let (source_interfaces, target_interfaces) = feed_interface_counts(&c.logical_feeds);
    let s = source_interfaces as i64;
    let rr = target_interfaces as i64;
    r.check(
        "运输端口收支/可知投影",
        s >= cat.count("transport_s") && rr >= cat.count("transport_r"),
        format!("S={s}、R={rr}；分别比较目录中的正式 S、R 下限（条文直引）"),
    );
    r.check("契约/专用端口双射恒等式", s == rr,
        "端口身份检查通过时 S=R 恒成立（算术推论）；这是专用契约结构的冗余自查，不是对分流或汇流配置的独立守卫");
    let transport_min = s.max(rr);
    r.unknown("运输端口收支/派生运输下限",format!(
        "若本计划 D=M=0 且接口身份、正流量检查通过，则 T+b≥max(S,R)+E={transport_min}+E≥{transport_min}（算术推论，E≥0）；实体 T、b、E 未提供，尚不能比较实际容量；据：运输端口收支"));
    let h = cat.count("box_h");
    let eta = (h - cat.count("box_eta_h_offset"))
        .max(cat.count("box_eta_m_base"))
        .max(cat.count("box_eta_h_factor") * h - cat.count("box_eta_h_subtract"));
    let interface_min = cat.count("box_base") + eta;
    r.check("箱体接口/已知计数投影", s+rr >= interface_min,
        format!("B0=B1=D=M=0（候选）代入 H={h}、η={eta}，S+R={}≥{interface_min}（阈值为算术推论）；含 T 的比较未执行",s+rr));
    let n_ore = c
        .machines
        .iter()
        .filter(|m| {
            m.recipes.iter().any(|p| {
                recipes.get(p.recipe.as_str()).is_some_and(|q| {
                    q.inputs.contains_key("源矿") || q.inputs.contains_key("蓝铁矿")
                })
            })
        })
        .count();
    r.check(
        "矿石分流与专机/定义计数",
        private
            && n_ore as i64 <= cat.count("ore_total")
            && dedicated.len() as i64 >= cat.count("ore_total"),
        format!(
            "D矿=B矿=0（候选）；N矿={n_ore}；满足专机配方、满批及独占输入条件者 C矿={}（算术计数）",
            dedicated.len()
        ),
    );
    let flow_min = cat.number("flow_total").ceil();
    r.check("箱体过站/已知流量投影", private && dedicated.len() as i64 >= cat.count("ore_total"),
        format!("无箱计划 Q=0、D矿=0，核 Q≥52−C矿；C矿={}；另导出 T+b≥⌈305.65+Q⌉={flow_min}（算术推论），运输端口收支给更强下限 {transport_min}；均未检查实体容量",dedicated.len()));
    let plant_area = sum(c
        .machines
        .iter()
        .filter(|m| {
            ["种植机", "采种机"].contains(&m.kind.as_str())
                || m.recipes
                    .iter()
                    .any(|p| ["粉碎-荞花", "粉碎-砂叶"].contains(&p.recipe.as_str()))
        })
        .filter_map(|m| spec(&cat, &m.kind).map(|(_, _, a)| integer(a))));
    let plant_transport_min = (cat.number("plant_area") - &plant_area).max(Rational::zero());
    r.unknown("回路转弯/占格条件投影",format!("按计划配方逐机去重的相关制造占格={plant_area}；故相关运输占格≥max(0,1378−{plant_area})={plant_transport_min}（算术推论），不证明转弯、布局或起动；据：回路转弯"));
    let full: Vec<_> = c
        .logical_feeds
        .iter()
        .filter(|e| e.planned_rate.value == port_rate)
        .collect();
    let ore_full = full
        .iter()
        .filter(|e| sources.contains_key(e.source.as_str()))
        .count();
    r.check("满速独占/计划适用集合",c.logical_feeds.iter().all(|e|e.planned_full_speed==(e.planned_rate.value==port_rate)),
        format!("计划满速记录 {} 条，其中矿石来源 {ore_full}、非矿石 {}（算术推论）；逐条 LF 标记见本表。在无分流汇流计划中，若实际逐 tick 满速成立，则到下一个非运输端点的沿途物品格每 tick 恰进出一件，不得与其它流共用该格；桥接器另一轴仍受跨格唯一性等规则约束。计划平均满速不构成实际满速证书。",full.len(),full.len()-ore_full));
    for plant in ["荞花", "砂叶"] {
        let seed = format!("{plant}种子");
        let mut graph: BTreeMap<&str, Vec<&str>> = BTreeMap::new();
        for edge in &c.logical_feeds {
            if edge.item == plant || edge.item == seed {
                graph.entry(&edge.source).or_default().push(&edge.target);
            }
        }
        let has_cycle = graph.keys().any(|start| {
            let mut visited = BTreeSet::new();
            let mut stack = graph.get(start).cloned().unwrap_or_default();
            while let Some(node) = stack.pop() {
                if node == *start {
                    return true;
                }
                if visited.insert(node) {
                    stack.extend(graph.get(node).into_iter().flatten().copied());
                }
            }
            false
        });
        r.check(format!("回路转弯/仅流图/{plant}"), has_cycle,
            "仅检查植株与种子正计划流图含有向回路；不证明物理转弯数、可起动性或活性，也不缩小运行检查范围");
    }
    let mut shapes = BTreeMap::new();
    let mut expected_fanouts = BTreeSet::new();
    for m in &c.machines {
        if outgoing(&m.id) >= 2 {
            expected_fanouts.insert(m.id.as_str());
        }
    }
    r.check(
        "扇出/完整性",
        c.fanouts
            .iter()
            .map(|f| f.machine.as_str())
            .collect::<BTreeSet<_>>()
            == expected_fanouts
            && c.fanouts.len() == expected_fanouts.len(),
        "多出口机器逐台登记，不漏项、不重复",
    );
    for f in &c.fanouts {
        let es: Vec<_> = c
            .logical_feeds
            .iter()
            .filter(|e| e.source == f.machine)
            .collect();
        let plan = machines.get(f.machine.as_str()).and_then(|m| {
            if m.recipes.len() == 1 {
                m.recipes.first()
            } else {
                None
            }
        });
        let rec = recipes.get(f.recipe.as_str());
        let shape = if es.iter().all(|e| e.planned_rate.value == port_rate) {
            "满速扇出定则型"
        } else if f.planned_mean_batch_interval.value == Rational::one()
            && &f.batch_size.value * integer(2) <= integer(outgoing(&f.machine))
        {
            "轮询均分型"
        } else {
            "两者都不落"
        };
        let ok = plan.is_some_and(|p| {
            p.recipe == f.recipe
                && p.planned_mean_batch_interval.value == f.planned_mean_batch_interval.value
        }) && rec.is_some_and(|rec| {
            rec.outputs.len() == 1
                && rec
                    .outputs
                    .get(&f.item)
                    .is_some_and(|q| q.value == f.batch_size.value)
        }) && f.ports.value == integer(outgoing(&f.machine))
            && es
                .iter()
                .all(|e| e.planned_rate.value == f.planned_port_rate.value && e.item == f.item)
            && f.planned_shape == shape
            && f.certification == "待验";
        r.check(
            format!("扇出/计划分类/{}", f.machine),
            ok,
            format!("计算形状={shape}；比较 2×每批件数≤端口数是候选分类算法，非正式阈值；认证状态必须为待验；满速扇出定则为候选，未审"),
        );
        *shapes.entry(shape).or_insert(0) += 1;
    }
    r.check("候选B/交接件数",c.machines.len()==219&&sum(c.machines.iter().map(|m|m.area.value.clone()))==integer(3325)&&c.logical_feeds.len()==315&&s==315&&rr==315&&count_in("研磨机",3)==31&&count_in("塑形机",2)==5&&c.machines.iter().filter(|m|m.kind=="封装机").all(|m|incoming(&m.id)==5)&&c.machines.iter().filter(|m|m.kind=="灌装机").all(|m|incoming(&m.id)==4)&&core_in==6&&c.machines.iter().filter(|m|m.recipes.iter().any(|p|recipes.get(p.recipe.as_str()).is_some_and(|q|q.inputs.len()>1))).count()==38&&c.machines.iter().filter(|m|m.multi_material.is_some()).count()==43&&shapes.get("满速扇出定则型")==Some(&30)&&shapes.get("轮询均分型")==Some(&2)&&shapes.get("两者都不落")==Some(&1),format!("制造 {} 台、面积 {} 格、逻辑记录 {}；S={s}、R={rr}；到达义务 {}（含多物品配方38与同物品多路5）；扇出 {shapes:?}。本行所有预期件数均为候选，观测为算术推论；不是一般约束",c.machines.len(),sum(c.machines.iter().map(|m|m.area.value.clone())),c.logical_feeds.len(),c.machines.iter().filter(|m|m.multi_material.is_some()).count()));
    // 对正式条目逐条列出未覆盖部分，静态投影通过不掩盖动态缺口。
    for rule in cat.constraints {
        let name = rule.name.as_str();
        let reason=match name {
            "机型下限"|"通道下限"|"单位矿耗"|"矿石需求"|"物料流量"=>"计划算术投影见通过／不通过栏；实际循环态流量尚无证书",
            "端口速率"=>"仅核逻辑记录的非运输端点负荷；运输网络内部端口尚无输入，实际逐 tick 速率也无证书",
            "接通先后"|"分叉分支"|"传输相位"|"判定先后"=>"无运行轨迹、合法取值覆盖与离线承接证明；受限计划排除部分元件不能代替执行认证",
            "轮询均分"=>"计划形状不证明同级、任一路可取、首格仅接本源、每次恰一 tick 排空、实际出货组时刻与首态",
            "满速独占"=>"计划满速 LF 标记及适用集合见专栏；未知沿途物品格与真实逐 tick 满速，不能把候选平均值当作已证前提",
            "矿线专机"|"矿石分流与专机"=>"计划专机条件及定义计数的通过与否见独立行；首遇实体及实际连续制造尚未认证",
            "灌装混线"=>"前提是否触发见本次结构行；周期物品身份与单位设定未建模",
            "准入累计"=>"计划模型排除准入口；实际布局与最终设定未提供，不能检查累计上限或窗口限流",
            "取货口配置"|"出库上限"=>"来源变量域与计划速率已核；左下边界及核心端口身份仍待求，未验证摆放与实际满速",
            "周期倍数"=>"仅核两成品计划速率；速率窗口不证明周期，更不能覆盖全部可达循环态",
            "种子自给"|"回路守恒"=>"计划配方回路守恒已核；逐时刻库存、入库事件及实际自持未检查",
            "运输端口收支"=>"核 S、R 下限并输出 D=M=0 下 T+b≥max(S,R)+E 的条件下界；S=R 是契约双射恒等式；实体运输网络缺失",
            "满载配置"|"封装进料"|"研磨进料"=>"已核机数条件、端口计数与计划速率；逐 tick 连续制造及实际到货仍待证",
            "成品汇入"|"入库途径"|"矿系不入库"=>"已核计划核心入库与来源；实际运输、箱体开关、物品身份轨迹与接收条件未提供",
            "混做清空"=>"多配方计划的相邻批次、清空时刻和逐批顺序没有执行证据；不根据条目名假定输入没有混做",
            "种子起动"=>"没有调试操作与后置状态证明，本步不做起动",
            "回路存量"|"传输箱不满"=>"没有库存状态、缓存格内容、时间平均或逐状态运行证据",
            "端口对接"|"取货分级"|"密集结点"|"来源定序"=>"逻辑边尚未展开为实体端口与运输路径；邻接、阻尼、优先级及定序需求未验证",
            "箱体接口"|"箱体过站"=>"已核无箱计划下可知的 S+R 或 Q 计数投影；T、b、E 等实体运输计数未提供",
            "回路转弯"=>"已输出相关制造占格及运输占格剩余下界；物料图不证明实际转弯、几何及布线",
            _=>"缺少实体运输单位、箱体、供电、坐标或空矩形数据；即使无箱也不能将本条视为自动通过，本步不做几何"
        };
        r.unknown(
            format!("正式条目/{name}"),
            format!(
                "{reason}。分节：{}；义务：{}；条文：{}；据：{}",
                rule.section,
                rule.obligation.as_deref().unwrap_or("按条文前件"),
                rule.text,
                rule.basis
            ),
        );
    }
    r.unknown("多料接口/全称目标","多料三栏全部待验；也不能把单料机或环外机器从活性义务中删去。接收环境、合法可达循环态、全部参数与离线变化均未认证。");
    r
}

#[cfg(test)]
mod catalog_tests {
    use super::*;

    #[test]
    fn legacy_machine_constants_equal_catalog() {
        // 第一轮的硬编码仅保留为回归对照，不能作为运行数据源。
        let cat = catalog();
        for (kind, cap, area, low, inc, out) in [
            ("粉碎机", 3, 9, 68, 68, 95),
            ("精炼炉", 3, 9, 51, 51, 51),
            ("研磨机", 6, 24, 32, 95, 32),
            ("塑形机", 3, 9, 6, 11, 6),
            ("配件机", 3, 9, 6, 6, 6),
            ("种植机", 5, 25, 32, 32, 32),
            ("采种机", 5, 25, 16, 16, 32),
            ("封装机", 6, 24, 3, 15, 1),
            ("灌装机", 6, 24, 3, 11, 1),
        ] {
            assert_eq!(spec(&cat, kind), Some((cap, cap, area)));
            let u = cat.units.iter().find(|u| u.id == kind).unwrap();
            assert_eq!(u.ports.output_count.as_i64(), cap);
            let b = u.static_lower_bounds.as_ref().unwrap();
            assert_eq!(
                (
                    b.machines.as_i64(),
                    b.input_channels.as_i64(),
                    b.output_channels.as_i64()
                ),
                (low, inc, out)
            );
        }
    }
}
