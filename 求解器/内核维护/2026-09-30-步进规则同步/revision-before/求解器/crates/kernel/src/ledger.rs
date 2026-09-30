//! 内核输出§2.0：事务明细与逐物种仓库守恒，代表调整不算交付。
use crate::{engine::Engine, value::*};
use serde_json::{json, Value};
use std::collections::BTreeMap;

pub const PRODUCTS: [&str; 2] = ["高容谷地电池", "精选荞愈胶囊"];
pub const ORES: [&str; 2] = ["源矿", "蓝铁矿"];
pub const FLOWS: [&str; 6] = [
    "core_inbound",
    "wireless_inbound",
    "port_outbound",
    "external_supply",
    "player_withdrawal",
    "representative_adjustment",
];

/// 输出§2.0：零量数组仍保留，成品总账始终存在。
pub fn empty_ledger() -> Value {
    json!({"core_inbound":[],"wireless_inbound":[],"port_outbound":[],"external_supply":[],"player_withdrawal":[],"representative_adjustment":[],"totals":[]})
}

/// 输出§2.0：从明细重算总账，不从仓库差额反推途径。
pub fn totals(ledger: &Value) -> Result<Value> {
    let mut result: BTreeMap<String, [i64; 6]> =
        PRODUCTS.into_iter().map(|s| (s.into(), [0; 6])).collect();
    for (i, field) in FLOWS.iter().enumerate() {
        for row in ledger[*field]
            .as_array()
            .ok_or_else(|| Stop::invalid(*field, "缺台账数组"))?
        {
            let item = row["item"]
                .as_str()
                .ok_or_else(|| Stop::invalid(*field, "缺物种"))?;
            let n = num(&row["quantity"], field)?;
            if n <= 0 {
                return Err(Stop::invalid(*field, "明细须为正整数"));
            }
            let v = result.entry(item.into()).or_default();
            v[i] = add(v[i], n, field)?;
        }
    }
    Ok(Value::Array(
        result
            .into_iter()
            .map(|(item, values)| {
                let mut row = json!({"item":item});
                for (field, value) in FLOWS.iter().zip(values) {
                    row[*field] = q(value);
                }
                row["actual_inbound"] = q(add(values[0], values[1], "actual_inbound")?);
                Ok(row)
            })
            .collect::<Result<Vec<_>>>()?,
    ))
}

impl Engine {
    /// 转移§2.1：模式已在输入校验，无隐式默认。
    pub fn sufficient(&self) -> bool {
        self.input
            .parameters
            .value(crate::config::Axis::WarehouseExternalSupply)
            .is_ok_and(|v| v["kind"] == "sufficient")
    }
    /// 输出§2.0：台账只在已提交事务后追加。
    pub(crate) fn book(&mut self, flow: &str, row: Value) {
        self.ledger[flow]
            .as_array_mut()
            .expect("固定台账字段")
            .push(row);
    }
    /// 转移§6.1：选择成品零代表，保留历史身份，不执行玩家动作。
    pub(crate) fn represent_products(&mut self) -> Result<()> {
        for i in 0..self.state.warehouse.slots.len() {
            let row = &mut self.state.warehouse.slots[i];
            if row.item.as_deref().is_some_and(|s| PRODUCTS.contains(&s)) {
                let item = row.item.take().unwrap();
                let n = row.quantity.integer(&row.slot)?;
                row.quantity = crate::value::Quantity::calc(0);
                row.empty_identity = crate::value::Decision::specified(
                    json!(item),
                    "受限转移§6.1：生产代表保留身份",
                );
                if n > 0 {
                    self.book(
                        "representative_adjustment",
                        json!({"item":item,"quantity":q(n),"reason":"production_representative"}),
                    );
                }
            }
        }
        Ok(())
    }
}

/// 输出§2.0/§5.3：只读前后完整状态和明细，独立核逐物种仓库守恒。
pub(crate) fn verify_tick(before: &Value, tick: &Value) -> Result<()> {
    fn counts(state: &Value) -> Result<BTreeMap<String, i128>> {
        let mut result = BTreeMap::new();
        for row in state["warehouse"]["slots"]
            .as_array()
            .ok_or_else(|| Stop::invalid("warehouse.slots", "缺仓库数组"))?
        {
            let n = num(&row["quantity"], "warehouse.quantity")?;
            if n < 0 || (row["item"].is_null() && n != 0) {
                return Err(Stop::invalid("warehouse.quantity", "负库存或空身份有数量"));
            }
            if let Some(item) = row["item"].as_str() {
                *result.entry(item.into()).or_default() += i128::from(n);
            }
        }
        result.retain(|_, n| *n != 0);
        Ok(result)
    }
    let ledger = &tick["warehouse_ledger"];
    let totals = totals(ledger)?;
    if totals != ledger["totals"] {
        return Err(Stop::invalid(
            "warehouse_ledger.totals",
            "明细重算与总账不同",
        ));
    }
    let mut expected = counts(before)?;
    for row in totals.as_array().unwrap() {
        let item = row["item"].as_str().unwrap();
        let signed = [
            ("actual_inbound", 1),
            ("external_supply", 1),
            ("port_outbound", -1),
            ("player_withdrawal", -1),
            ("representative_adjustment", -1),
        ];
        for (field, sign) in signed {
            *expected.entry(item.into()).or_default() +=
                i128::from(num(&row[field], field)?) * sign;
        }
    }
    expected.retain(|_, n| *n != 0);
    if expected.values().any(|n| *n < 0) || expected != counts(&tick["state"])? {
        return Err(Stop::invalid(
            "warehouse_ledger",
            "逐物种前后库存与入库/补给/出库/代表调整不守恒",
        ));
    }
    Ok(())
}
