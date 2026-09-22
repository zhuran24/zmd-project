//! 内核输入§1.1、受限转移§1：精确整数、封闭字段与带位置的停止值。
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{collections::BTreeSet, path::Path};

pub type Result<T> = std::result::Result<T, Stop>;
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Stop {
    pub status: String,
    pub axis: String,
    pub location: String,
    pub reason: String,
}
impl Stop {
    /// 受限转移§1：未实现值不能被当成游戏后继。
    pub fn new(
        status: &str,
        axis: &str,
        location: impl Into<String>,
        reason: impl Into<String>,
    ) -> Self {
        Self {
            status: status.into(),
            axis: axis.into(),
            location: location.into(),
            reason: reason.into(),
        }
    }
    /// 受限转移§1：输入冲突与未实现机制分开报告。
    pub fn invalid(location: impl Into<String>, reason: impl Into<String>) -> Self {
        Self::new("invalid_input", "input", location, reason)
    }
    /// 受限转移§1：明确未覆盖轴和首个访问位置。
    pub fn unsupported(axis: &str, location: impl Into<String>, reason: impl Into<String>) -> Self {
        Self::new("unsupported", axis, location, reason)
    }
}
impl std::fmt::Display for Stop {
    /// 内核输出§1：错误文本保留可定位的轴名。
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{} {} @ {}: {}",
            self.status, self.axis, self.location, self.reason
        )
    }
}
impl std::error::Error for Stop {}
/// 内核输入§1.2：未知键及缺字段拒收。
pub fn fields(v: &Value, expected: &str, at: &str) -> Result<()> {
    let actual = v.as_object().ok_or_else(|| Stop::invalid(at, "须为对象"))?;
    let keys: BTreeSet<_> = expected.split_whitespace().collect();
    if actual.keys().map(String::as_str).collect::<BTreeSet<_>>() != keys {
        return Err(Stop::invalid(at, format!("字段须恰为 {expected}")));
    }
    Ok(())
}
/// 内核输入§1.1：结构转换不吞 serde 错误。
pub fn decode<T: serde::de::DeserializeOwned>(v: Value, at: &str) -> Result<T> {
    serde_json::from_value(v).map_err(|e| Stop::invalid(at, e.to_string()))
}
/// 内核输入§1.1：读取 JSON，同时拒绝重复键及浮点。
pub fn read_json(path: &Path) -> Result<Value> {
    let bytes = std::fs::read(path)
        .map_err(|e| Stop::invalid(path.display().to_string(), e.to_string()))?;
    let mut de = serde_json::Deserializer::from_slice(&bytes);
    let value = StrictValue::deserialize(&mut de)
        .map_err(|e| Stop::invalid(path.display().to_string(), e.to_string()))?
        .0;
    de.end()
        .map_err(|e| Stop::invalid(path.display().to_string(), e.to_string()))?;
    Ok(value)
}
struct StrictValue(Value);
impl<'de> Deserialize<'de> for StrictValue {
    /// 内核输入§1：JSON 对象身份不允许后键静默覆盖前键。
    fn deserialize<D: serde::Deserializer<'de>>(d: D) -> std::result::Result<Self, D::Error> {
        struct Visitor;
        impl<'de> serde::de::Visitor<'de> for Visitor {
            type Value = StrictValue;
            /// 内核输入§1.1：错误上下文。
            fn expecting(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
                f.write_str("无重复键、无浮点的 JSON")
            }
            /// 内核输入§1.1：空值编码。
            fn visit_unit<E: serde::de::Error>(self) -> std::result::Result<Self::Value, E> {
                Ok(StrictValue(Value::Null))
            }
            /// 内核输入§1.1：布尔编码独立于整数。
            fn visit_bool<E: serde::de::Error>(
                self,
                v: bool,
            ) -> std::result::Result<Self::Value, E> {
                Ok(StrictValue(v.into()))
            }
            /// 内核输入§1.1：表示索引可以是整数。
            fn visit_i64<E: serde::de::Error>(self, v: i64) -> std::result::Result<Self::Value, E> {
                Ok(StrictValue(v.into()))
            }
            /// 内核输入§1.1：表示索引可以是非负整数。
            fn visit_u64<E: serde::de::Error>(self, v: u64) -> std::result::Result<Self::Value, E> {
                Ok(StrictValue(v.into()))
            }
            /// 内核输入§1.1：字符串原样保存。
            fn visit_str<E: serde::de::Error>(
                self,
                v: &str,
            ) -> std::result::Result<Self::Value, E> {
                Ok(StrictValue(v.into()))
            }
            /// 内核输入§1.1：数组顺序保留，不隐式变成语义优先序。
            fn visit_seq<A: serde::de::SeqAccess<'de>>(
                self,
                mut a: A,
            ) -> std::result::Result<Self::Value, A::Error> {
                let mut v = Vec::new();
                while let Some(x) = a.next_element::<StrictValue>()? {
                    v.push(x.0)
                }
                Ok(StrictValue(v.into()))
            }
            /// 内核输入§1.2：对象键必须唯一。
            fn visit_map<A: serde::de::MapAccess<'de>>(
                self,
                mut a: A,
            ) -> std::result::Result<Self::Value, A::Error> {
                let mut v = serde_json::Map::new();
                while let Some((k, x)) = a.next_entry::<String, StrictValue>()? {
                    if v.insert(k, x.0).is_some() {
                        return Err(serde::de::Error::custom("重复 JSON 键"));
                    }
                }
                Ok(StrictValue(v.into()))
            }
        }
        d.deserialize_any(Visitor)
    }
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Quantity {
    pub value: String,
    pub category: String,
}
impl Quantity {
    /// 内核输入§1.1：用整数运算解释有理字符串；本版只运行整数域。
    pub fn integer(&self, at: &str) -> Result<i64> {
        if !["条文直引", "算术推论", "候选", "启发式", "实测"].contains(&self.category.as_str())
        {
            return Err(Stop::invalid(at, "数字类别非法"));
        }
        let p: Vec<_> = self.value.split('/').collect();
        if p.is_empty() || p.len() > 2 {
            return Err(Stop::invalid(at, "有理数格式非法"));
        }
        let parse = |s: &str| -> Result<i128> {
            if s.is_empty()
                || !s
                    .trim_start_matches('-')
                    .bytes()
                    .all(|c| c.is_ascii_digit())
                || s == "-"
            {
                return Err(Stop::invalid(at, "非法整数字符串"));
            }
            s.parse().map_err(|_| {
                Stop::new(
                    "inconclusive",
                    "resource.integer",
                    at,
                    "整数超出 i128 解析域",
                )
            })
        };
        let n = parse(p[0])?;
        let d = if p.len() == 2 { parse(p[1])? } else { 1 };
        if d <= 0 {
            return Err(Stop::invalid(at, "分母须为正"));
        }
        if n % d != 0 {
            return Err(Stop::unsupported(
                "time.domain",
                at,
                "本配置只支持整数数量/时刻",
            ));
        }
        i64::try_from(n / d).map_err(|_| {
            Stop::new(
                "inconclusive",
                "resource.integer",
                at,
                "整数超出 i64 运行域",
            )
        })
    }
    /// 受限转移§4：运算所得物理量明确标为算术推论。
    pub fn calc(n: i64) -> Self {
        Self {
            value: n.to_string(),
            category: "算术推论".into(),
        }
    }
    /// 内核输入§1.1：回放时刻延续参考输出的候选分类。
    pub fn candidate(n: i64) -> Self {
        Self {
            value: n.to_string(),
            category: "候选".into(),
        }
    }
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Time {
    pub kind: String,
    pub value: Quantity,
}
impl Time {
    /// 受限转移§2.1：拒绝符号及非整数运行时刻。
    pub fn integer(&self, at: &str) -> Result<i64> {
        if self.kind != "rational" {
            return Err(Stop::unsupported("time.domain", at, "时刻未解释"));
        }
        self.value.integer(at)
    }
    /// 受限转移§2.1：整数时钟输出，无浮点。
    pub fn at(t: i64) -> Self {
        Self {
            kind: "rational".into(),
            value: Quantity::candidate(t),
        }
    }
}
/// 受限转移§1、§5.2：数值资源耗尽不能溢出成合法后继。
pub fn add(a: i64, b: i64, at: &str) -> Result<i64> {
    a.checked_add(b)
        .ok_or_else(|| Stop::new("inconclusive", "resource.integer", at, "整数加法溢出"))
}
/// 内核输入§1.1：JSON Quantity 到整数的统一入口。
pub fn num(v: &Value, at: &str) -> Result<i64> {
    decode::<Quantity>(v.clone(), at)?.integer(at)
}
/// 内核输入§1.1：JSON Time 到整数的统一入口。
pub fn instant(v: &Value, at: &str) -> Result<i64> {
    decode::<Time>(v.clone(), at)?.integer(at)
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Decision {
    pub status: String,
    pub value: Value,
    pub basis: Vec<String>,
}
impl Decision {
    /// 内核输入§1.1：派生量不得由 unresolved 偷填默认。
    pub fn resolved(&self, at: &str, nullable: bool) -> Result<&Value> {
        if self.basis.is_empty() || self.basis.iter().any(String::is_empty) {
            return Err(Stop::invalid(at, "Decision 缺依据"));
        }
        if !["specified", "derived"].contains(&self.status.as_str()) {
            return Err(Stop::unsupported(
                "initialization.other_inventory",
                at,
                "Decision 未解或不适用",
            ));
        }
        if self.value.is_null() && !nullable {
            return Err(Stop::invalid(at, "Decision 缺具体值"));
        }
        Ok(&self.value)
    }
    /// 内核输出§2：保存算得状态及其条款依据。
    pub fn specified(value: Value, basis: &str) -> Self {
        Self {
            status: "specified".into(),
            value,
            basis: vec![basis.into()],
        }
    }
}
/// 内核输入§1.1：遍历封套，检查不参与本次守卫的状态亦不放过。
pub fn validate_tree(v: &Value, path: &str) -> Result<()> {
    if let Some(o) = v.as_object() {
        if o.contains_key("status")
            && (o.contains_key("value") || o.contains_key("basis"))
            && !path.contains(".bridge_axes.")
        {
            let d: Decision = decode(v.clone(), path)?;
            if d.basis.is_empty() || d.basis.iter().any(String::is_empty) {
                return Err(Stop::invalid(path, "Decision 缺依据"));
            }
            match d.status.as_str() {
                "unresolved" | "not_applicable" => {
                    if !d.value.is_null() {
                        return Err(Stop::invalid(path, "未解封套带值"));
                    }
                }
                "specified" | "derived" => {
                    if d.value.is_null() && !path.ends_with("empty_identity") {
                        return Err(Stop::invalid(path, "已解封套无值"));
                    }
                }
                _ => return Err(Stop::invalid(path, "未知 Decision 状态")),
            }
        }
        for (k, x) in o {
            validate_tree(x, &format!("{path}.{k}"))?
        }
    } else if let Some(a) = v.as_array() {
        for (i, x) in a.iter().enumerate() {
            validate_tree(x, &format!("{path}[{i}]"))?
        }
    } else if v.is_f64() {
        return Err(Stop::invalid(path, "禁止浮点"));
    }
    Ok(())
}
/// 内核输出§2：通用状态数值编码。
pub fn q(n: i64) -> Value {
    json!(Quantity::calc(n))
}
/// 内核输出§2：通用时刻编码。
pub fn tv(n: i64) -> Value {
    json!(Time::at(n))
}
