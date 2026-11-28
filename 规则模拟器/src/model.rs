use crate::{
    Res,
    json::{array, decode},
};
use serde::{Deserialize, Serialize};
use serde_json::{Value as V, json};

/// 仓库每种物品的上限（协议核心每格 80000）。
pub const WAREHOUSE_CAP: usize = 80000;
/// 协议核心的取货端口数。
pub const CORE_OUTLETS: usize = 6;
pub type Id = u64;
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub struct Channel(pub Id, pub Id);

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum Item {
    源矿,
    源石粉末,
    致密源石粉末,
    蓝铁矿,
    蓝铁块,
    蓝铁粉末,
    致密蓝铁粉末,
    钢块,
    钢质瓶,
    钢制零件,
    荞花种子,
    荞花,
    荞花粉末,
    细磨荞花粉末,
    砂叶种子,
    砂叶,
    砂叶粉末,
    高容谷地电池,
    精选荞愈胶囊,
}
use Item::*;
pub const ITEMS: [Item; 19] = [
    源矿,
    源石粉末,
    致密源石粉末,
    蓝铁矿,
    蓝铁块,
    蓝铁粉末,
    致密蓝铁粉末,
    钢块,
    钢质瓶,
    钢制零件,
    荞花种子,
    荞花,
    荞花粉末,
    细磨荞花粉末,
    砂叶种子,
    砂叶,
    砂叶粉末,
    高容谷地电池,
    精选荞愈胶囊,
];

const _: () = {
    let mut i = 0;
    while i < ITEMS.len() {
        assert!(ITEMS[i] as usize == i);
        i += 1;
    }
};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Kind {
    传送带,
    分流器,
    汇流器,
    物品准入口,
    桥接器格,
    协议储存箱,
    协议核心,
    仓库取货口,
    粉碎机,
    精炼炉,
    研磨机,
    塑形机,
    配件机,
    种植机,
    采种机,
    封装机,
    灌装机,
}
use Kind::*;
impl Kind {
    pub fn ports(self) -> (usize, usize) {
        match self {
            传送带 | 物品准入口 | 桥接器格 => (1, 1),
            分流器 => (1, 3),
            汇流器 => (3, 1),
            协议储存箱 => (3, 3),
            协议核心 => (14, 6),
            仓库取货口 => (0, 1),
            粉碎机 | 精炼炉 | 配件机 | 塑形机 => (3, 3),
            采种机 | 种植机 => (5, 5),
            研磨机 | 封装机 | 灌装机 => (6, 6),
        }
    }
    pub fn stock_slots(self) -> usize {
        match self {
            研磨机 | 封装机 | 灌装机 => 2,
            粉碎机 | 精炼炉 | 配件机 | 塑形机 | 种植机 | 采种机 => 1,
            传送带 | 分流器 | 汇流器 | 物品准入口 | 桥接器格 | 协议储存箱 | 协议核心
            | 仓库取货口 => 0,
        }
    }
    pub fn transport(self) -> bool {
        match self {
            传送带 | 分流器 | 汇流器 | 物品准入口 | 桥接器格 => true,
            协议储存箱 | 协议核心 | 仓库取货口 | 粉碎机 | 精炼炉 | 配件机 | 塑形机 | 种植机
            | 采种机 | 研磨机 | 封装机 | 灌装机 => false,
        }
    }
    pub fn outlets(self) -> usize {
        match self {
            协议核心 => CORE_OUTLETS,
            仓库取货口 => 1,
            传送带 | 分流器 | 汇流器 | 物品准入口 | 桥接器格 | 协议储存箱 | 粉碎机 | 精炼炉
            | 配件机 | 塑形机 | 种植机 | 采种机 | 研磨机 | 封装机 | 灌装机 => {
                0
            }
        }
    }
}

pub type Stack = (Item, usize);
#[derive(Debug, Serialize, PartialEq, Eq)]
pub struct Recipe {
    #[serde(rename = "单位")]
    pub kind: Kind,
    #[serde(rename = "原料")]
    pub inputs: &'static [Stack],
    #[serde(rename = "产物")]
    pub output: Stack,
    #[serde(rename = "时长")]
    pub ticks: u32,
}
const fn recipe(kind: Kind, inputs: &'static [Stack], output: Stack, ticks: u32) -> Recipe {
    Recipe {
        kind,
        inputs,
        output,
        ticks,
    }
}
pub static RECIPES: [Recipe; 18] = [
    recipe(粉碎机, &[(源矿, 1)], (源石粉末, 1), 1),
    recipe(粉碎机, &[(蓝铁块, 1)], (蓝铁粉末, 1), 1),
    recipe(粉碎机, &[(荞花, 1)], (荞花粉末, 2), 1),
    recipe(粉碎机, &[(砂叶, 1)], (砂叶粉末, 3), 1),
    recipe(精炼炉, &[(蓝铁矿, 1)], (蓝铁块, 1), 1),
    recipe(精炼炉, &[(致密蓝铁粉末, 1)], (钢块, 1), 1),
    recipe(精炼炉, &[(蓝铁粉末, 1)], (蓝铁块, 1), 1),
    recipe(
        研磨机,
        &[(蓝铁粉末, 2), (砂叶粉末, 1)],
        (致密蓝铁粉末, 1),
        1,
    ),
    recipe(
        研磨机,
        &[(源石粉末, 2), (砂叶粉末, 1)],
        (致密源石粉末, 1),
        1,
    ),
    recipe(
        研磨机,
        &[(荞花粉末, 2), (砂叶粉末, 1)],
        (细磨荞花粉末, 1),
        1,
    ),
    recipe(塑形机, &[(钢块, 2)], (钢质瓶, 1), 1),
    recipe(配件机, &[(钢块, 1)], (钢制零件, 1), 1),
    recipe(种植机, &[(荞花种子, 1)], (荞花, 1), 1),
    recipe(种植机, &[(砂叶种子, 1)], (砂叶, 1), 1),
    recipe(采种机, &[(荞花, 1)], (荞花种子, 2), 1),
    recipe(采种机, &[(砂叶, 1)], (砂叶种子, 2), 1),
    recipe(
        封装机,
        &[(钢制零件, 10), (致密源石粉末, 15)],
        (高容谷地电池, 1),
        5,
    ),
    recipe(
        灌装机,
        &[(钢质瓶, 10), (细磨荞花粉末, 10)],
        (精选荞愈胶囊, 1),
        5,
    ),
];

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
/// Declaration order is the canonical slot order. Do not reorder variants.
pub enum Slot {
    Grid(usize),
    Stock(usize),
    Output,
    Cache,
}
impl Slot {
    pub fn read(v: &V) -> Res<Self> {
        match v.as_str() {
            Some("缓存") => Ok(Self::Cache),
            Some("取货") => Ok(Self::Output),
            Some(s) => Err(format!("未知格名 {s}")),
            None => match array(v)? {
                [k, i] if k == "格" => Ok(Self::Grid(decode(i)?)),
                [k, i] if k == "存货" => Ok(Self::Stock(decode(i)?)),
                _ => Err(format!("格名错误 {v}")),
            },
        }
    }
    fn json(&self) -> V {
        match self {
            Self::Grid(i) => json!(["格", i]),
            Self::Stock(i) => json!(["存货", i]),
            Self::Output => json!("取货"),
            Self::Cache => json!("缓存"),
        }
    }
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct Cell(pub Id, pub Slot);
impl Cell {
    pub fn read(v: &V) -> Res<Self> {
        let [u, n] = array(v)? else {
            return Err("格位需要单位号与格名".into());
        };
        Ok(Self(decode(u)?, Slot::read(n)?))
    }
    pub fn json(&self) -> V {
        json!([self.0, self.1.json()])
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Event {
    Build(Id, Kind),
    Connect(Channel),
    Reconnect(Channel),
    Remove(Id),
}
#[derive(Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Counter {
    保留,
    清空,
}
#[derive(Clone, Copy)]
pub struct CounterPolicy {
    pub count: Counter,
    pub quotas: Counter,
}
/// Per-segment external observations and counter policies, also used by LegalBase.
pub struct Parameters {
    pub powered: Vec<Id>,
    pub ports: Vec<(Channel, usize)>,
    pub transfer_after: Vec<(Id, usize)>,
    pub on_change: CounterPolicy,
    pub on_offline: CounterPolicy,
}
