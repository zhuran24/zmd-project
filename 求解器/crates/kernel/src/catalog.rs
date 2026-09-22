//! 第四轮§4.1、内核输入§2：正式目录为尺寸、端口、库存和配方的唯一来源。
use crate::{config::Reference, value::*};
use serde_json::Value;
use std::{
    collections::{BTreeMap, BTreeSet},
    path::{Path, PathBuf},
    process::Command,
};
#[derive(Clone, Debug)]
pub struct Kind {
    pub id: String,
    pub family: String,
    pub width: i64,
    pub height: i64,
    pub layouts: Vec<Value>,
    pub slots: Vec<SlotKind>,
    pub functions: Vec<String>,
    pub same_item_unique: bool,
    pub window: i64,
    pub cooldown: i64,
    pub coverage: Option<(i64, i64)>,
}
#[derive(Clone, Debug)]
pub struct SlotKind {
    pub role: String,
    pub count: Option<usize>,
    pub capacity: Option<i64>,
}
#[derive(Clone, Debug)]
pub struct Recipe {
    pub id: String,
    pub kind: String,
    pub inputs: BTreeMap<String, i64>,
    pub outputs: BTreeMap<String, i64>,
    pub duration: i64,
}
#[derive(Clone, Debug)]
pub struct Catalog {
    pub raw: Value,
    pub path: PathBuf,
    pub sha256: String,
    pub kinds: BTreeMap<String, Kind>,
    pub recipes: BTreeMap<String, Recipe>,
    pub warehouse_capacity: i64,
    pub port_rate: i64,
}
/// 内核输出§1：只读原始字节指纹，子进程参数不经 shell。
pub fn sha256(path: &Path) -> Result<String> {
    let out = Command::new("sha256sum")
        .arg("--")
        .arg(path)
        .output()
        .map_err(|e| Stop::invalid(path.display().to_string(), e.to_string()))?;
    if !out.status.success() {
        return Err(Stop::invalid(
            path.display().to_string(),
            "sha256sum 读取失败",
        ));
    }
    let s = String::from_utf8(out.stdout).map_err(|e| Stop::invalid("sha256sum", e.to_string()))?;
    let hash = s
        .split_whitespace()
        .next()
        .ok_or_else(|| Stop::invalid("sha256sum", "无输出"))?;
    if hash.len() != 64 || !hash.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err(Stop::invalid("sha256sum", "散列格式异常"));
    }
    Ok(hash.into())
}
/// 内核输入§1：依赖相对于输入文件解析，先核指纹再消费。
pub fn reference(base: &Path, r: &Reference) -> Result<PathBuf> {
    let p = base
        .join(&r.path)
        .canonicalize()
        .map_err(|e| Stop::invalid(&r.path, e.to_string()))?;
    if sha256(&p)? != r.sha256 {
        return Err(Stop::invalid(&r.path, "源文件指纹不符"));
    }
    Ok(p)
}
impl Catalog {
    /// 第四轮§4.1：实际加载共享目录，不另抄单位或配方常量。
    pub fn load(path: &Path) -> Result<Self> {
        let raw = read_json(path)?;
        let formal: Value = serde_json::from_str(include_str!("../../../数据/正式静态目录.json"))
            .map_err(|e| Stop::invalid("catalog", e.to_string()))?;
        if raw != formal {
            return Err(Stop::invalid(
                "catalog",
                "输入目录不同于本实现编译时登记的正式目录",
            ));
        }
        if raw["schema"] != "static-catalog-v2" {
            return Err(Stop::invalid("catalog.schema", "不支持目录版本"));
        }
        let mut kinds = BTreeMap::new();
        for row in raw["units"]
            .as_array()
            .ok_or_else(|| Stop::invalid("catalog.units", "须为数组"))?
        {
            let id = row["id"]
                .as_str()
                .ok_or_else(|| Stop::invalid("catalog.units.id", "须为字符串"))?
                .to_string();
            let mut slots = Vec::new();
            for s in row["inventory"]
                .as_array()
                .ok_or_else(|| Stop::invalid(&id, "缺库存定义"))?
            {
                slots.push(SlotKind {
                    role: s["role"]
                        .as_str()
                        .ok_or_else(|| Stop::invalid(&id, "缺格角色"))?
                        .into(),
                    count: if s["count"].is_null() {
                        None
                    } else {
                        Some(
                            usize::try_from(num(&s["count"], &id)?)
                                .map_err(|_| Stop::invalid(&id, "负格数"))?,
                        )
                    },
                    capacity: if s["capacity"].is_null() {
                        None
                    } else {
                        Some(num(&s["capacity"], &id)?)
                    },
                })
            }
            let k = Kind {
                id: id.clone(),
                family: row["family"]
                    .as_str()
                    .ok_or_else(|| Stop::invalid(&id, "缺分类"))?
                    .into(),
                width: num(&row["dimensions"]["width"], &id)?,
                height: num(&row["dimensions"]["height"], &id)?,
                layouts: decode(row["ports"]["layouts"].clone(), &id)?,
                slots,
                functions: decode(row["powered_functions"].clone(), &id)?,
                same_item_unique: row["inventory_rules"]["same_item_across_slots"] != "exempt",
                window: if row["settings"]["window_ticks"].is_null() {
                    0
                } else {
                    num(&row["settings"]["window_ticks"], &id)?
                },
                cooldown: if row["transfer"]["cooldown_ticks"].is_null() {
                    0
                } else {
                    num(&row["transfer"]["cooldown_ticks"], &id)?
                },
                coverage: if row["coverage"].is_null() {
                    None
                } else {
                    Some((
                        num(&row["coverage"]["width"], &id)?,
                        num(&row["coverage"]["height"], &id)?,
                    ))
                },
            };
            if kinds.insert(id, k).is_some() {
                return Err(Stop::invalid("catalog.units", "重复单位类型"));
            }
        }
        let mut recipes = BTreeMap::new();
        for r in raw["recipes"]
            .as_array()
            .ok_or_else(|| Stop::invalid("catalog.recipes", "须为数组"))?
        {
            let id = r["id"]
                .as_str()
                .ok_or_else(|| Stop::invalid("catalog.recipes", "缺 id"))?
                .to_string();
            let amounts = |v: &Value| -> Result<BTreeMap<String, i64>> {
                v.as_object()
                    .ok_or_else(|| Stop::invalid(&id, "配方物料须为对象"))?
                    .iter()
                    .map(|(k, v)| Ok((k.clone(), num(v, &id)?)))
                    .collect()
            };
            let recipe = Recipe {
                id: id.clone(),
                kind: r["kind"]
                    .as_str()
                    .ok_or_else(|| Stop::invalid(&id, "缺机型"))?
                    .into(),
                inputs: amounts(&r["inputs"])?,
                outputs: amounts(&r["outputs"])?,
                duration: num(&r["duration"], &id)?,
            };
            if recipe.duration < 1
                || recipe
                    .inputs
                    .values()
                    .chain(recipe.outputs.values())
                    .any(|q| *q <= 0)
            {
                return Err(Stop::invalid(&id, "配方数值非法"));
            }
            if recipes.insert(id, recipe).is_some() {
                return Err(Stop::invalid("catalog.recipes", "重复配方"));
            }
        }
        let warehouse_capacity = kinds
            .values()
            .flat_map(|k| &k.slots)
            .find(|s| s.role == "warehouse")
            .and_then(|s| s.capacity)
            .ok_or_else(|| Stop::invalid("catalog", "缺仓库容量"))?;
        let port_rate = num(
            &raw["static_checks"]["constants"]["port_rate"]["quantity"],
            "port_rate",
        )?;
        Ok(Self {
            sha256: sha256(path)?,
            path: path.to_path_buf(),
            raw,
            kinds,
            recipes,
            warehouse_capacity,
            port_rate,
        })
    }
    /// 内核输入§2.3：目录声明每个单位所有格，桥容量由显式轴补齐。
    pub fn slots(
        &self,
        units: &BTreeMap<String, Unit>,
        bridge_capacity: i64,
    ) -> Result<BTreeMap<String, Option<i64>>> {
        let mut result = BTreeMap::new();
        for (uid, u) in units {
            for s in &self.kinds[&u.kind].slots {
                if s.role == "warehouse" {
                    continue;
                }
                let count = s.count.ok_or_else(|| Stop::invalid(uid, "本地格数未知"))?;
                for i in 0..count {
                    result.insert(
                        format!("{uid}:{}:{i}", s.role),
                        if u.kind == "桥接器" {
                            Some(bridge_capacity)
                        } else {
                            s.capacity
                        },
                    );
                }
            }
        }
        Ok(result)
    }
}
#[derive(Clone, Debug)]
pub struct Unit {
    pub id: String,
    pub kind: String,
    pub x: i64,
    pub y: i64,
    pub width: i64,
    pub height: i64,
    pub turn: u8,
    pub raw: Value,
}
#[derive(Clone, Debug)]
pub struct Port {
    pub unit: String,
    pub role: String,
    pub axis: Option<String>,
    pub cell: (i64, i64),
    pub normal: (i64, i64),
}
#[derive(Clone, Debug, serde::Serialize, serde::Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Channel {
    pub id: String,
    pub source_port: String,
    pub target_port: String,
}
#[derive(Clone, Debug)]
pub struct Geometry {
    pub units: BTreeMap<String, Unit>,
    pub ports: BTreeMap<String, Port>,
    pub channels: BTreeMap<String, Channel>,
    pub buffers: BTreeSet<String>,
    pub powered: BTreeSet<String>,
}
/// 内核输入§2.1：局部格旋转与法向采用同一逆时针编码。
fn rotate(x: i64, y: i64, w: i64, h: i64, t: u8) -> (i64, i64) {
    match t {
        0 => (x, y),
        1 => (h - 1 - y, x),
        2 => (w - 1 - x, h - 1 - y),
        _ => (y, w - 1 - x),
    }
}
impl Geometry {
    /// 内核输入§2.1–§2.3：从目录重建占格、全部 PC、BC 及正面积供电。
    pub fn build(layout: &Value, cat: &Catalog) -> Result<Self> {
        let mut units = BTreeMap::new();
        let mut ports = BTreeMap::new();
        let mut occupied = BTreeSet::new();
        let bw = num(&layout["base"]["width"], "layout.base.width")?;
        let bh = num(&layout["base"]["height"], "layout.base.height")?;
        if bw != 70 || bh != 70 {
            return Err(Stop::invalid("layout.base", "规则基地须为70×70"));
        }
        for row in layout["units"]
            .as_array()
            .ok_or_else(|| Stop::invalid("layout.units", "须为数组"))?
        {
            fields(
                row,
                "id kind origin rotation port_layout bridge_axes occupied_cells",
                "layout.units[]",
            )?;
            let uid = row["id"]
                .as_str()
                .ok_or_else(|| Stop::invalid("unit.id", "须为字符串"))?
                .to_string();
            if uid.is_empty()
                || !uid.as_bytes()[0].is_ascii_alphabetic()
                || !uid.bytes().all(|c| c.is_ascii_alphanumeric() || c == b'_')
            {
                return Err(Stop::invalid(&uid, "单位 id 非法"));
            }
            let kind = row["kind"]
                .as_str()
                .ok_or_else(|| Stop::invalid(&uid, "机型非法"))?
                .to_string();
            let k = cat
                .kinds
                .get(&kind)
                .ok_or_else(|| Stop::invalid(&uid, "未知机型"))?;
            let turn = match row["rotation"].as_str() {
                Some("r0") => 0,
                Some("r90") => 1,
                Some("r180") => 2,
                Some("r270") => 3,
                _ => return Err(Stop::invalid(&uid, "朝向非法")),
            };
            let x = num(&row["origin"][0], &uid)?;
            let y = num(&row["origin"][1], &uid)?;
            let (w, h) = if turn % 2 == 0 {
                (k.width, k.height)
            } else {
                (k.height, k.width)
            };
            if x < 0 || y < 0 || w > bw || h > bh || x > bw - w || y > bh - h {
                return Err(Stop::invalid(&uid, "占格越界"));
            }
            let mut cells = BTreeSet::new();
            for a in x..x + w {
                for b in y..y + h {
                    if !occupied.insert((a, b)) {
                        return Err(Stop::invalid(&uid, "单位重叠"));
                    }
                    cells.insert((a, b));
                }
            }
            if !row["occupied_cells"].is_null() {
                let given: Result<BTreeSet<_>> = row["occupied_cells"]
                    .as_array()
                    .ok_or_else(|| Stop::invalid(&uid, "占格须为数组"))?
                    .iter()
                    .map(|r| Ok((num(&r[0], &uid)?, num(&r[1], &uid)?)))
                    .collect();
                if given? != cells {
                    return Err(Stop::invalid(&uid, "声明占格与目录不符"));
                }
            }
            let edges: Vec<Value> = if kind == "桥接器" {
                if !row["port_layout"].is_null() {
                    return Err(Stop::invalid(&uid, "桥不能任选目录方向型"));
                }
                let mut e = BTreeMap::new();
                for variant in &k.layouts {
                    for edge in variant
                        .as_array()
                        .ok_or_else(|| Stop::invalid("catalog.ports", "型须为数组"))?
                    {
                        let side = edge["side"]
                            .as_str()
                            .ok_or_else(|| Stop::invalid(&uid, "端口边缺失"))?;
                        let axis = edge["axis"]
                            .as_str()
                            .ok_or_else(|| Stop::invalid(&uid, "桥轴缺失"))?;
                        let a = &row["bridge_axes"][axis];
                        let status = a["status"].as_str();
                        if status != Some("resolved") {
                            return Err(Stop::unsupported(
                                "connection.bridge_tie",
                                format!("{uid}.bridge_axes.{axis}"),
                                "桥轴未解",
                            ));
                        }
                        let input = a["input_side"]
                            .as_str()
                            .ok_or_else(|| Stop::invalid(&uid, "桥输入方向缺失"))?;
                        if !(if axis == "vertical" {
                            ["south", "north"].contains(&input)
                        } else {
                            ["west", "east"].contains(&input)
                        }) {
                            return Err(Stop::invalid(&uid, "桥轴输入边不在该轴"));
                        }
                        let mut v = edge.clone();
                        v["role"] =
                            Value::String(if side == input { "input" } else { "output" }.into());
                        e.insert(side.to_string(), v);
                    }
                }
                e.into_values().collect()
            } else {
                if !row["bridge_axes"].is_null() {
                    return Err(Stop::invalid(&uid, "非桥带桥轴"));
                }
                let index = row["port_layout"]
                    .as_u64()
                    .ok_or_else(|| Stop::invalid(&uid, "缺端口型"))?
                    as usize;
                decode(
                    k.layouts
                        .get(index)
                        .ok_or_else(|| Stop::invalid(&uid, "端口型越界"))?
                        .clone(),
                    &uid,
                )?
            };
            if kind == "仓库取货口" && !((turn == 0 && y == 0) || (turn == 3 && x == 0)) {
                return Err(Stop::invalid(&uid, "取货口必须长边贴左/下边且向内"));
            }
            for edge in edges {
                let side = edge["side"]
                    .as_str()
                    .ok_or_else(|| Stop::invalid(&uid, "端口边非法"))?;
                for pos in edge["positions"]
                    .as_array()
                    .ok_or_else(|| Stop::invalid(&uid, "端口位置非法"))?
                {
                    let p = num(pos, &uid)?;
                    let (a, b, dx, dy) = match side {
                        "south" => (p, 0, 0, -1),
                        "north" => (p, k.height - 1, 0, 1),
                        "west" => (0, p, -1, 0),
                        "east" => (k.width - 1, p, 1, 0),
                        _ => return Err(Stop::invalid(&uid, "端口边未知")),
                    };
                    let (a, b) = rotate(a, b, k.width, k.height, turn);
                    let (mut dx, mut dy) = (dx, dy);
                    for _ in 0..turn {
                        (dx, dy) = (-dy, dx)
                    }
                    let pid = format!("{uid}:{side}:{p}");
                    let port = Port {
                        unit: uid.clone(),
                        role: edge["role"]
                            .as_str()
                            .ok_or_else(|| Stop::invalid(&uid, "端口角色非法"))?
                            .into(),
                        axis: edge["axis"].as_str().map(str::to_string),
                        cell: (x + a, y + b),
                        normal: (dx, dy),
                    };
                    if ports.insert(pid, port).is_some() {
                        return Err(Stop::invalid(&uid, "端口重复"));
                    }
                }
            }
            if units
                .insert(
                    uid.clone(),
                    Unit {
                        id: uid.clone(),
                        kind,
                        x,
                        y,
                        width: w,
                        height: h,
                        turn,
                        raw: row.clone(),
                    },
                )
                .is_some()
            {
                return Err(Stop::invalid(uid, "单位重复"));
            }
        }
        if units
            .values()
            .filter(|u| cat.kinds[&u.kind].family == "core")
            .count()
            != 1
        {
            return Err(Stop::invalid("layout.units", "须恰有一个核心"));
        }
        let faces: BTreeMap<_, _> = ports
            .iter()
            .map(|(id, p)| ((p.cell, p.normal), id))
            .collect();
        let mut channels = BTreeMap::new();
        if faces.len() != ports.len() {
            return Err(Stop::invalid("layout.ports", "重复格边端口"));
        }
        for (id, p) in &ports {
            if p.role != "output" {
                continue;
            }
            let key = (
                (p.cell.0 + p.normal.0, p.cell.1 + p.normal.1),
                (-p.normal.0, -p.normal.1),
            );
            if let Some(other) = faces.get(&key) {
                let q = &ports[*other];
                if q.role == "input"
                    && (cat.kinds[&units[&p.unit].kind].family == "transport"
                        || cat.kinds[&units[&q.unit].kind].family == "transport")
                {
                    let c = Channel {
                        id: format!("PC|{id}|{other}"),
                        source_port: id.clone(),
                        target_port: (*other).clone(),
                    };
                    channels.insert(c.id.clone(), c);
                }
            }
        }
        if !layout["physical_channels"].is_null() {
            let rows: Vec<Channel> =
                decode(layout["physical_channels"].clone(), "physical_channels")?;
            let declared: BTreeMap<_, _> = rows.iter().map(|r| (r.id.clone(), r.clone())).collect();
            if declared.len() != rows.len() || declared != channels {
                return Err(Stop::invalid(
                    "layout.physical_channels",
                    "PC 不等于全部几何可能边",
                ));
            }
        }
        let mut buffers = BTreeSet::new();
        for (uid, u) in &units {
            if cat.kinds[&u.kind].family != "manufacturing" {
                continue;
            }
            for sk in &cat.kinds[&u.kind].slots {
                if !["input", "output"].contains(&sk.role.as_str()) {
                    continue;
                }
                for i in 0..sk.count.ok_or_else(|| Stop::invalid(uid, "本地格数未解"))? {
                    buffers.insert(if sk.role == "input" {
                        format!("BC|{uid}:input:{i}|{uid}:buffer:0")
                    } else {
                        format!("BC|{uid}:buffer:0|{uid}:output:{i}")
                    });
                }
            }
        }
        if !layout["buffer_channels"].is_null() {
            let rows = layout["buffer_channels"]
                .as_array()
                .ok_or_else(|| Stop::invalid("buffer_channels", "须为数组"))?;
            let mut given = BTreeSet::new();
            for r in rows {
                fields(r, "id source_slot target_slot", "buffer_channel")?;
                let id = r["id"]
                    .as_str()
                    .ok_or_else(|| Stop::invalid("buffer_channel", "id非法"))?;
                if id
                    != format!(
                        "BC|{}|{}",
                        r["source_slot"].as_str().unwrap_or(""),
                        r["target_slot"].as_str().unwrap_or("")
                    )
                    || !given.insert(id.to_string())
                {
                    return Err(Stop::invalid(id, "BC 编码/重复错误"));
                }
            }
            if given != buffers {
                return Err(Stop::invalid("buffer_channels", "BC 缺失或多余"));
            }
        }
        let mut powered = BTreeSet::new();
        for (uid, u) in &units {
            if cat.kinds[&u.kind].functions.is_empty() {
                continue;
            }
            for p in units.values() {
                if let Some((cw, ch)) = cat.kinds[&p.kind].coverage {
                    let (cx, cy) = (2 * p.x + p.width, 2 * p.y + p.height);
                    if (2 * u.x).max(cx - cw) < (2 * (u.x + u.width)).min(cx + cw)
                        && (2 * u.y).max(cy - ch) < (2 * (u.y + u.height)).min(cy + ch)
                    {
                        powered.insert(uid.clone());
                    }
                }
            }
        }
        Ok(Self {
            units,
            ports,
            channels,
            buffers,
            powered,
        })
    }
}
