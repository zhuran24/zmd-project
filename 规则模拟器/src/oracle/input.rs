use crate::{
    Action, Res,
    json::{array, decode},
    model::*,
};
use serde_json::Value as V;

pub(super) fn history(v: &V) -> Res<Vec<Event>> {
    array(v)?
        .iter()
        .map(|v| {
            Ok(match array(v)? {
                [k, u, t] if k == "建成" => Event::Build(decode(u)?, decode(t)?),
                [k, c] if k == "接通" => Event::Connect(decode(c)?),
                [k, c] if k == "重接" => Event::Reconnect(decode(c)?),
                [k, u] if k == "拆除" => Event::Remove(decode(u)?),
                _ => return Err(format!("未知事件或参数错误 {v}")),
            })
        })
        .collect()
}

pub(crate) enum Instruction {
    Walk(u64),
    Apply(Action),
}
impl Instruction {
    pub fn read(v: &V) -> Res<Self> {
        use Action::*;
        let op = match array(v)? {
            [k, n] if k == "走" => return Ok(Self::Walk(decode(n)?)),
            [k, u, x, a, b] if k == "设准入口" => {
                SetGate(decode(u)?, decode(x)?, decode(a)?, decode(b)?)
            }
            [k, u] if k == "重置计数" => ResetCount(decode(u)?),
            [k, u, b] if k == "设储存箱模式" => Storage(decode(u)?, decode(b)?),
            [k, u, i, x] if k == "设取货指向" => Target(decode(u)?, decode(i)?, decode(x)?),
            [k, us, b] if k == "拨开关" => Switch(decode(us)?, decode(b)?),
            [k, u, x, n] if k == "放货" => Put(decode(u)?, decode(x)?, decode(n)?),
            [k, g] if k == "收货" => Collect(Cell::read(g)?),
            [k, x, n] if k == "入库" => Store(decode(x)?, decode(n)?),
            [k, x, n] if k == "出库" => Retrieve(decode(x)?, decode(n)?),
            [k, h] if k == "离线" => Offline(history(h)?),
            _ => return Err(format!("段内不支持的操作或参数个数有误 {v}")),
        };
        Ok(Self::Apply(op))
    }
}
