//! 第五轮K7：物理可动缓存按单位/仓库事务失效；级排序只在图变更时失效。
use crate::{
    engine::{Engine, Route},
    value::*,
};
use std::collections::{BTreeMap, BTreeSet};
pub(crate) type PhysicalResult = (Option<Route>, &'static str);
impl Engine {
    /// 每时刻或图事务全失效，涵盖年龄、预算清零、门原因、级及阻尼路径。
    pub(crate) fn invalidate_all(&self) {
        self.physical_cache.borrow_mut().clear();
        *self.dirty_sides.borrow_mut() = (0..self.memory.sides.len()).collect();
    }
    /// 普通格更改可能改变本单位任一口的同种单格守卫，故按整单位而非单格失效。
    pub(crate) fn invalidate_unit(&self, unit: &str) {
        if !self.cache_enabled {
            return;
        }
        if let Some(edges) = self.dependencies.get(unit) {
            let mut cache = self.physical_cache.borrow_mut();
            let mut dirty = self.dirty_sides.borrow_mut();
            for cid in edges {
                cache.remove(cid);
                let c = &self.input.geometry.channels[cid];
                for (port, side) in [(&c.source_port, "output"), (&c.target_port, "input")] {
                    if let Some(i) = self
                        .side_index
                        .get(&(self.input.geometry.ports[port].unit.clone(), side.into()))
                    {
                        dirty.insert(*i);
                    }
                }
            }
        }
    }
    pub(crate) fn invalidate_slot(&self, slot: &str) {
        self.invalidate_unit(if self.warehouse.contains_key(slot) {
            "@warehouse"
        } else {
            slot.split(':').next().unwrap_or("")
        });
    }
    /// 输入静态派生依赖；仓库身份/O/容量变化失效全部仓库端相关PC。
    pub(crate) fn build_dependencies(&mut self) {
        let mut deps = BTreeMap::<String, BTreeSet<String>>::new();
        for (cid, c) in &self.input.geometry.channels {
            for port in [&c.source_port, &c.target_port] {
                let p = &self.input.geometry.ports[port];
                deps.entry(p.unit.clone()).or_default().insert(cid.clone());
                if self.input.assignments.contains_key(port)
                    || self.input.geometry.units[&p.unit].kind == "协议核心"
                {
                    deps.entry("@warehouse".into())
                        .or_default()
                        .insert(cid.clone());
                }
            }
        }
        self.dependencies = deps;
        self.invalidate_all();
    }
    /// 公共基准/差分开关；启用时清空缓存，关闭时沿用逐次真实计算路径。
    pub fn set_cache_enabled(&mut self, enabled: bool) {
        self.cache_enabled = enabled;
        self.invalidate_all();
    }
    pub(crate) fn cached_physical(&self, cid: &str) -> Result<PhysicalResult> {
        if self.cache_enabled {
            if let Some(v) = self.physical_cache.borrow().get(cid) {
                return Ok(v.clone());
            }
        }
        let result = self.compute_physical(cid)?;
        if self.cache_enabled {
            self.physical_cache
                .borrow_mut()
                .insert(cid.into(), result.clone());
        }
        Ok(result)
    }
}
