//! Compatibility with historical observations, including bases with dangling
//! belts and the four discarded explanations for a merger's input decision.
use crate::{
    Res,
    action::Simulation,
    json::{self, array, decode, field, keys},
    model::*,
    step::{MergerRule, Twice},
    topology::{History, Layout, Tables},
};
mod input;
use input::{Instruction, history};
use serde_json::Value as V;
use std::io::Write;

enum OldRule {
    Reject,
    Accept,
    Retry,
    Next,
}
impl OldRule {
    fn read(v: &str) -> Res<Self> {
        match v {
            "不收" => Ok(Self::Reject),
            "都收" => Ok(Self::Accept),
            "再判一次" => Ok(Self::Retry),
            "轮到的那条" => Ok(Self::Next),
            _ => Err(format!("未知的输入判定说法 {v}")),
        }
    }
}
struct Selection {
    chosen: Option<Channel>,
    first: Option<Channel>,
}
impl MergerRule for OldRule {
    type Decision = Selection;
    fn record(&self, order: &[Channel], chosen: Option<Channel>) -> Selection {
        Selection {
            chosen,
            first: order.first().copied(),
        }
    }
    fn accepts(&self, c: &Channel, a: &Selection, b: &Selection) -> bool {
        match &a.chosen {
            Some(chosen) => c == chosen,
            None => match self {
                OldRule::Reject => false,
                OldRule::Accept => true,
                OldRule::Retry => b.chosen.as_ref() == Some(c),
                OldRule::Next => a.first.as_ref() == Some(c),
            },
        }
    }
}
fn waiting(l: &Layout, e: &Id) -> Option<usize> {
    let mut at = *e;
    for n in 1..=l.built.len() + 1 {
        if l.kind(&at) == Kind::分流器 {
            let waits = match l.outgoing(&at).as_slice() {
                [] => true,
                [c] => l.kind(&c.1) == Kind::桥接器格 && l.outgoing(&c.1).is_empty(),
                _ => false,
            };
            return (waits && !l.incoming(&at).is_empty()).then_some(n);
        }
        if l.component(1, &at).as_ref() != Some(&at) {
            return None;
        }
        match l.downstream(&at).as_slice() {
            [next] => at = *next,
            _ => return None,
        }
    }
    None
}

pub struct OracleRunner {
    sim: Simulation,
}
impl OracleRunner {
    fn tables(h: &History) -> Res<Tables> {
        Tables::build(h, waiting, |_| Ok(()))
    }
    fn segment(v: &V, out: &mut impl Write) -> Res<()> {
        keys(
            v,
            &[
                "历史", "供电", "端口", "未定", "状态", "操作", "期望", "备注",
            ],
        )?;
        if let Some(note) = v.get("备注") {
            note.as_str().ok_or("备注需要字符串")?;
        }
        let events = history(field(v, "历史")?)?;
        let policy = field(v, "未定")?;
        keys(
            policy,
            &[
                "改设定后的计数",
                "离线后的计数",
                "传输排在几组之后",
                "输入判定都没货时",
            ],
        )?;
        let rule = field(policy, "输入判定都没货时")?
            .as_str()
            .ok_or("输入判定说法需要字符串")?;
        let counters = |key| {
            let [count, quotas] = decode(field(policy, key)?)?;
            Ok::<_, String>(CounterPolicy { count, quotas })
        };
        let params = Parameters {
            powered: decode(field(v, "供电")?)?,
            ports: decode(field(v, "端口")?)?,
            transfer_after: decode(field(policy, "传输排在几组之后")?)?,
            on_change: counters("改设定后的计数")?,
            on_offline: counters("离线后的计数")?,
        };
        let sim = Simulation::new(events, params, field(v, "状态")?, Self::tables)?;
        let mut runner = Self { sim };
        match rule {
            "每步判两次" => runner.execute(v, out, &Twice),
            old => runner.execute(v, out, &OldRule::read(old)?),
        }
    }
    fn execute(&mut self, v: &V, out: &mut impl Write, rule: &impl MergerRule) -> Res<()> {
        let ops = array(field(v, "操作")?)?;
        let expected = v.get("期望").map(array).transpose()?;
        let mut line = 0;
        let mut emit = |s: &Simulation| -> Res<()> {
            let row = s.state.snapshot().to_string();
            if expected.is_some_and(|xs| {
                xs.get(line).is_none_or(|v| {
                    let mut v = v.clone();
                    v.sort_all_objects();
                    v.to_string().as_bytes() != row.as_bytes()
                })
            }) {
                return Err(format!("第 {} 行与期望不同", line + 1));
            }
            writeln!(out, "{row}").map_err(|e| e.to_string())?;
            line += 1;
            Ok(())
        };
        for (i, op) in ops.iter().enumerate() {
            let pos = |e: String| format!("第 {} 项操作 {e}", i + 1);
            match Instruction::read(op).map_err(pos)? {
                Instruction::Walk(n) => {
                    for _ in 0..n {
                        self.sim
                            .state
                            .step(&self.sim.tables, &self.sim.params, rule);
                        emit(&self.sim)?;
                    }
                }
                Instruction::Apply(action) => {
                    self.sim.apply(&action, Self::tables).map_err(pos)?;
                    emit(&self.sim)?
                }
            }
        }
        if expected.is_some_and(|xs| xs.len() != line) {
            return Err(format!("期望行数应为 {line}"));
        }
        Ok(())
    }
    pub fn run(input: &str, out: &mut impl Write) -> Res<()> {
        let v = json::parse(input)?;
        keys(&v, &["版本", "段"])?;
        if decode::<u64>(field(&v, "版本")?)? != 1 {
            return Err("只支持版本 1".into());
        }
        for (i, s) in array(field(&v, "段")?)?.iter().enumerate() {
            Self::segment(s, out).map_err(|e| format!("第 {} 段 {e}", i + 1))?
        }
        Ok(())
    }
}
