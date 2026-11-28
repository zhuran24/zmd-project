use crate::Res;
use serde::{
    Deserialize, Deserializer,
    de::{DeserializeOwned, Error, MapAccess, Visitor},
};
use serde_json::{Map, Value as V, value::RawValue};
use std::fmt;

pub(crate) fn decode<T: DeserializeOwned + serde::Serialize>(v: &V) -> Res<T> {
    let x: T = serde_json::from_value(v.clone()).map_err(|e| e.to_string())?;
    if serde_json::to_value(&x).map_err(|e| e.to_string())? != *v {
        return Err(format!("取值类型或形状错误 {v}"));
    }
    Ok(x)
}
pub(crate) fn array(v: &V) -> Res<&[V]> {
    v.as_array()
        .map(Vec::as_slice)
        .ok_or_else(|| "需要数组".into())
}
pub(crate) fn field<'a>(v: &'a V, k: &str) -> Res<&'a V> {
    v.get(k).ok_or_else(|| format!("缺少字段 {k}"))
}
pub(crate) fn keys(v: &V, names: &[&str]) -> Res<()> {
    for k in v.as_object().ok_or("需要对象")?.keys() {
        if !names.contains(&k.as_str()) {
            return Err(format!("未知字段 {k}"));
        }
    }
    Ok(())
}

// Read the JSON tokens as written. In particular an object can never be
// mistaken for serde_json's private arbitrary-precision number representation.
struct Object(Map<String, V>);
struct ObjectVisitor;
impl<'de> Visitor<'de> for ObjectVisitor {
    type Value = Object;
    fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result {
        f.write_str("JSON 对象")
    }
    fn visit_map<A: MapAccess<'de>>(self, mut map: A) -> Result<Object, A::Error> {
        let mut obj = Map::new();
        while let Some(k) = map.next_key::<String>()? {
            if obj.contains_key(&k) {
                return Err(A::Error::custom(format!("重复的 JSON 键 {k}")));
            }
            let raw = map.next_value::<&RawValue>()?;
            obj.insert(k, parse_raw(raw.get()).map_err(A::Error::custom)?);
        }
        Ok(Object(obj))
    }
}
impl<'de> Deserialize<'de> for Object {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        d.deserialize_map(ObjectVisitor)
    }
}
// Lean.Json.Parser.escapedChar maps an unpaired UTF-16 escape to U+FFFD.
// Normalize only those escapes, before checking uniqueness of decoded keys.
fn unicode_escape(bytes: &[u8]) -> Option<u16> {
    let digits = bytes.strip_prefix(br"\u")?.get(..4)?;
    if !digits.iter().all(u8::is_ascii_hexdigit) {
        return None;
    }
    u16::from_str_radix(std::str::from_utf8(digits).expect("hex digits"), 16).ok()
}
fn string_escapes(input: &str) -> String {
    let mut bytes = input.as_bytes().to_vec();
    let mut quoted = false;
    let mut i = 0;
    while i < bytes.len() {
        match bytes[i] {
            b'"' => {
                quoted = !quoted;
                i += 1
            }
            b'\\' if quoted => match unicode_escape(&bytes[i..]) {
                Some(high)
                    if (0xd800..0xdc00).contains(&high)
                        && unicode_escape(&bytes[i + 6..])
                            .is_some_and(|low| (0xdc00..0xe000).contains(&low)) =>
                {
                    i += 12
                }
                Some(code) if (0xd800..0xe000).contains(&code) => {
                    bytes[i + 2..i + 6].copy_from_slice(b"fffd");
                    i += 6
                }
                Some(_) => i += 6,
                None => i += 2,
            },
            _ => i += 1,
        }
    }
    String::from_utf8(bytes).expect("only ASCII hex digits changed")
}
pub fn parse(input: &str) -> Res<V> {
    let normalized = string_escapes(input);
    let raw: &RawValue = serde_json::from_str(&normalized).map_err(|e| e.to_string())?;
    parse_raw(raw.get())
}
fn parse_raw(raw: &str) -> Res<V> {
    match raw.as_bytes()[0] {
        b'{' => serde_json::from_str::<Object>(raw)
            .map(|o| V::Object(o.0))
            .map_err(|e| e.to_string()),
        b'[' => {
            let parts: Vec<&RawValue> = serde_json::from_str(raw).map_err(|e| e.to_string())?;
            Ok(V::Array(
                parts
                    .iter()
                    .map(|p| parse_raw(p.get()))
                    .collect::<Res<_>>()?,
            ))
        }
        b'-' | b'0'..=b'9' => {
            if !raw.bytes().all(|b| b.is_ascii_digit()) {
                return Err(format!("需要普通十进制非负整数 {raw}"));
            }
            raw.parse::<u64>()
                .map(V::from)
                .map_err(|_| format!("整数超出 u64 范围 {raw}"))
        }
        _ => serde_json::from_str(raw).map_err(|e| e.to_string()),
    }
}
