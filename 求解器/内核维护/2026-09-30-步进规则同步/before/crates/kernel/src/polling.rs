//! 受限转移§3：物理守卫、级排序、独立授权及事务式图更新。
use crate::{engine::Engine, model::*, value::*};
use std::collections::{BTreeMap, BTreeSet};
impl Engine {
    /// 受限转移§3.1–§3.2：几何 PC 分级，环按接通时刻及独立并列序排列。
    pub(crate) fn group_levels(
        &self,
        active: &BTreeSet<String>,
        retain: bool,
    ) -> Result<Vec<Side>> {
        let mut result = Vec::new();
        let tie: BTreeMap<_, _> = self
            .input
            .tie_order
            .iter()
            .enumerate()
            .map(|(i, c)| (c, i))
            .collect();
        for prior in &self.memory.sides {
            let uid = &prior.unit;
            let side = &prior.side;
            let unit = &self.input.geometry.units[uid];
            let graded =
                side == "input" || self.input.catalog.kinds[&unit.kind].family != "transport";
            let mut groups: BTreeMap<String, Vec<String>> = BTreeMap::new();
            for cid in active {
                let c = &self.input.geometry.channels[cid];
                let (end, peer) = if side == "input" {
                    (&c.target_port, &c.source_port)
                } else {
                    (&c.source_port, &c.target_port)
                };
                if self.input.geometry.ports[end].unit != *uid
                    || self.input.geometry.ports[end].axis != prior.axis
                {
                    continue;
                }
                let peer_kind =
                    &self.input.geometry.units[&self.input.geometry.ports[peer].unit].kind;
                let direct = graded
                    && peer_kind
                        == if side == "input" {
                            "分流器"
                        } else {
                            "汇流器"
                        };
                let category = if direct {
                    format!("direct:{cid}")
                } else if graded {
                    "other".into()
                } else {
                    "ungraded".into()
                };
                groups
                    .entry(if let Some(axis) = &prior.axis {
                        format!("L|{uid}|{axis}|{side}|{category}")
                    } else {
                        format!("L|{uid}|{side}|{category}")
                    })
                    .or_default()
                    .push(cid.clone());
            }
            let mut levels = Vec::new();
            for (id, mut members) in groups {
                members.sort_by_key(|c| (self.input.connection_times[c], tie[c]));
                let special = (unit.kind == "分流器" && side == "output")
                    || (unit.kind == "汇流器" && side == "input");
                let mut cursor = members[usize::from(special && members.len() >= 2)].clone();
                if retain {
                    if let Some(old) = prior.levels.iter().find(|l| l.id == id) {
                        let start = old
                            .members
                            .iter()
                            .position(|c| *c == old.next_channel)
                            .ok_or_else(|| Stop::invalid(&id, "旧游标不在旧环"))?;
                        if let Some(c) = old.members[start..]
                            .iter()
                            .chain(&old.members[..start])
                            .find(|c| members.contains(c))
                        {
                            cursor = c.clone();
                        }
                    }
                }
                levels.push(Level {
                    id,
                    members,
                    next_channel: cursor,
                });
            }
            result.push(Side {
                unit: uid.clone(),
                side: side.clone(),
                axis: prior.axis.clone(),
                graded,
                current_level: None,
                levels,
            });
        }
        Ok(result)
    }
    /// 受限转移§3.1、运行语义§2.2：路径带串计一次，特别运输计一元件，桥只沿本轴。
    pub fn damping(&self, origin: &str) -> Result<i64> {
        self.damping_used.borrow_mut().insert(origin.into());
        let mut current = origin.to_string();
        let mut seen = BTreeSet::new();
        let mut count = 0;
        let mut previous_belt = false;
        loop {
            if !self.active.contains(&current) || !seen.insert(current.clone()) {
                return Err(Stop::new(
                    "unresolved",
                    "damping.no_terminal",
                    origin,
                    "所选路径无下一非运输终点",
                ));
            }
            let c = &self.input.geometry.channels[&current];
            let target = &self.input.geometry.ports[&c.target_port];
            let unit = &self.input.geometry.units[&target.unit];
            let kind = &self.input.catalog.kinds[&unit.kind];
            if kind.family != "transport" {
                return Ok(count);
            }
            let belt = unit.kind == "传送带";
            if belt {
                self.damping_used
                    .borrow_mut()
                    .insert(format!("belt_component:{origin}"));
            }
            if unit.kind == "分流器" {
                self.damping_used
                    .borrow_mut()
                    .insert(format!("branch:{origin}"));
            }
            if !belt || !previous_belt {
                count = add(count, 1, origin)?
            }
            previous_belt = belt;
            let outgoing: Vec<_> = self
                .active
                .iter()
                .filter(|id| {
                    let p =
                        &self.input.geometry.ports[&self.input.geometry.channels[*id].source_port];
                    p.unit == target.unit
                        && (unit.kind != "桥接器"
                            || (p.axis == target.axis
                                && self.input.geometry.channels[*id].source_port != c.target_port))
                })
                .cloned()
                .collect();
            if outgoing.is_empty() {
                return Err(Stop::new(
                    "unresolved",
                    "damping.no_terminal",
                    origin,
                    format!("路径在 {} 无终点", target.unit),
                ));
            }
            current = if unit.kind == "分流器" {
                self.input
                    .branches
                    .get(&(target.unit.clone(), outgoing.clone()))
                    .cloned()
                    .ok_or_else(|| {
                        Stop::new("unresolved", "damping.branch", origin, "缺当前可用集表项")
                    })?
            } else if outgoing.len() == 1 {
                outgoing[0].clone()
            } else {
                return Err(Stop::invalid(origin, "非分流器出现多条同路径出边"));
            };
        }
    }
    /// 受限转移§3.1–§3.2：先计算全部 physical，再选最高可动级，不递归读权限。
    pub(crate) fn refresh(&mut self) -> Result<()> {
        if self.production_abstraction {
            self.check_production_candidates()?;
        }
        let dirty: BTreeSet<usize> = if self.cache_enabled {
            self.dirty_sides.borrow().clone()
        } else {
            (0..self.memory.sides.len()).collect()
        };
        if dirty.is_empty() {
            return Ok(());
        }
        let dynamic_order: BTreeMap<_, _> = if self.cache_enabled {
            BTreeMap::new()
        } else {
            self.state
                .semantic_context
                .arbitration
                .level_order
                .iter()
                .enumerate()
                .map(|(i, l)| (l.clone(), i))
                .collect()
        };
        let order = if self.cache_enabled {
            &self.arbitration_rank
        } else {
            &dynamic_order
        };
        let mut choices = Vec::new();
        let mut ties: Vec<_> = self
            .tie_sides
            .iter()
            .filter(|key| !dirty.iter().any(|i| *key == &self.memory.sides[*i].label()))
            .cloned()
            .collect();
        for (index, s) in self.memory.sides.iter().enumerate() {
            if !dirty.contains(&index) {
                continue;
            }
            let mut movable = BTreeSet::new();
            for l in &s.levels {
                for c in &l.members {
                    if self.physical(c)?.0.is_some() {
                        movable.insert(c.clone());
                    }
                }
            }
            let mut static_keys = BTreeMap::new();
            for l in &s.levels {
                let cached = if self.cache_enabled {
                    self.level_keys.borrow().get(&l.id).copied()
                } else {
                    None
                };
                let key = if let Some(key) = cached {
                    key
                } else {
                    let mut damping = 0;
                    if s.side == "output" && s.levels.len() > 1 {
                        for c in &l.members {
                            damping = damping.max(self.damping(c)?);
                        }
                    }
                    let connected = l
                        .members
                        .iter()
                        .map(|c| self.input.connection_times[c])
                        .min()
                        .ok_or_else(|| Stop::invalid(&l.id, "空级"))?;
                    let key = (damping, connected);
                    if self.cache_enabled {
                        self.level_keys.borrow_mut().insert(l.id.clone(), key);
                    }
                    key
                };
                if s.side == "output" && s.levels.len() > 1 {
                    self.damping_used
                        .borrow_mut()
                        .extend(l.members.iter().cloned());
                }
                static_keys.insert(l.id.clone(), key);
            }
            let eligible: Vec<_> = s
                .levels
                .iter()
                .filter(|l| !s.graded || l.members.iter().any(|c| movable.contains(c)))
                .collect();
            if eligible.is_empty() {
                choices.push((index, None));
                continue;
            }
            if !s.graded {
                if eligible.len() != 1 {
                    return Err(Stop::invalid(&s.unit, "运输取货侧必须恰一环"));
                }
                choices.push((index, Some(eligible[0].id.clone())));
                continue;
            }
            // 受限转移§3.1：仅有一个级无需为比较请求阻尼，悬空单级仍可收货。
            let mut keys = Vec::new();
            for l in &eligible {
                keys.push((static_keys[&l.id], *l));
            }
            let best = keys.iter().map(|(k, _)| *k).min().unwrap();
            let equal: Vec<_> = keys
                .into_iter()
                .filter(|(k, _)| *k == best)
                .map(|(_, l)| l)
                .collect();
            if equal.len() > 1 {
                ties.push(s.label())
            }
            let chosen = equal
                .iter()
                .min_by_key(|l| order.get(&l.id).copied().unwrap_or(usize::MAX))
                .unwrap();
            if !order.contains_key(&chosen.id) {
                return Err(Stop::invalid(&chosen.id, "级仲裁标签缺失"));
            }
            choices.push((index, Some(chosen.id.clone())));
        }
        for (index, c) in choices {
            self.memory.sides[index].current_level = c;
        }
        ties.sort_by_key(|key| {
            self.memory
                .sides
                .iter()
                .position(|s| *key == s.label())
                .unwrap_or(usize::MAX)
        });
        self.tie_sides = ties;
        self.dirty_sides.borrow_mut().clear();
        Ok(())
    }
    /// 受限转移§3.2：分级侧跳过物理不可动成员，不分级侧允许空尝试。
    pub(crate) fn grant(&self, index: usize, cid: &str) -> Result<bool> {
        let s = &self.memory.sides[index];
        let Some(id) = &s.current_level else {
            return Ok(false);
        };
        let l = s
            .levels
            .iter()
            .find(|l| &l.id == id)
            .ok_or_else(|| Stop::invalid(id, "当前级不存在"))?;
        if !s.graded {
            return Ok(l.next_channel == cid);
        }
        let start = l
            .members
            .iter()
            .position(|c| *c == l.next_channel)
            .ok_or_else(|| Stop::invalid(id, "环游标失效"))?;
        for c in l.members[start..].iter().chain(&l.members[..start]) {
            if self.physical(c)?.0.is_some() {
                return Ok(c == cid);
            }
        }
        Ok(false)
    }
    /// 受限转移§3.3：仅判前已授权侧沿完整环前移，失败同样消费权限。
    pub(crate) fn advance(&mut self, index: usize, cid: &str) -> Result<()> {
        let s = &mut self.memory.sides[index];
        let l = s
            .levels
            .iter_mut()
            .find(|l| l.members.iter().any(|c| c == cid))
            .ok_or_else(|| Stop::invalid(cid, "授权边不在环中"))?;
        let i = l.members.iter().position(|c| c == cid).unwrap();
        l.next_channel = l.members[(i + 1) % l.members.len()].clone();
        Ok(())
    }
    /// 受限转移§3.4：完整前图到完整后图只映射一次续接位置。
    pub(crate) fn rebuild_memory(&mut self) -> Result<()> {
        if self.production_abstraction {
            self.check_production_candidates()?;
        }
        self.invalidate_all();
        self.level_keys.borrow_mut().clear();
        self.memory.sides = self.group_levels(&self.active, true)?;
        self.side_index = self
            .memory
            .sides
            .iter()
            .enumerate()
            .map(|(i, s)| ((s.unit.clone(), s.side.clone(), s.axis.clone()), i))
            .collect();
        self.refresh()
    }
    /// 内核输入§5.3、转移§3.4：拟提交图必须保留整段固定表的当前路径语义。
    pub(crate) fn check_branch_graph(&self, active: &BTreeSet<String>) -> Result<()> {
        self.input.validate_branch_paths(active).map_err(|e| {
            Stop::new(
                "unresolved",
                "damping.branch",
                e.location,
                format!("固定表在图变更后失效；KQ-06：{}", e.reason),
            )
        })
    }
    /// 受限转移§3.4：原因集提交后导出实际边，恢复仍用原建造时刻。
    pub(crate) fn rebuild_graph(&mut self) -> Result<()> {
        let blocked: BTreeSet<_> = self
            .input
            .geometry
            .channels
            .values()
            .filter(|c| {
                self.gate_index
                    .get(&self.input.geometry.ports[&c.target_port].unit)
                    .is_some_and(|i| {
                        !self.state.logistics.gate_counters[*i]
                            .blocked_reasons
                            .is_empty()
                    })
            })
            .map(|c| c.id.clone())
            .collect();
        let active = self
            .input
            .geometry
            .channels
            .keys()
            .filter(|c| !blocked.contains(*c))
            .cloned()
            .collect();
        // 内核输入§5.3、转移§3.4：固定表在每个新图仍须成立，失活不能静默换支。
        self.check_branch_graph(&active)?;
        self.active = active;
        self.state.logistics.active_channels = self
            .channel_order
            .iter()
            .filter(|c| self.active.contains(*c))
            .cloned()
            .collect();
        self.state.logistics.blocked_channels = self
            .channel_order
            .iter()
            .filter(|c| blocked.contains(*c))
            .cloned()
            .collect();
        self.rebuild_memory()
    }
    /// 受限转移§2.2/§3.4：从原几何候选重核当前原因，完整前后图一次映射。
    pub(crate) fn maintain_identity(&mut self) -> Result<Option<String>> {
        let mut mismatched = BTreeSet::new();
        for cid in &self.gate_channels {
            let c = &self.input.geometry.channels[cid];
            let uid = &self.input.geometry.ports[&c.target_port].unit;
            let settings = &self.input.gate_settings[uid];
            if !settings["item"].is_null() {
                if let Some((_, content)) = self.source(&c.source_port)? {
                    if settings["item"] != content.item {
                        mismatched.insert(uid.clone());
                    }
                }
            }
        }
        let mut changes = Vec::new();
        let mut next = self.state.logistics.gate_counters.clone();
        for g in &mut next {
            let set = &self.input.gate_settings[&g.unit];
            let before: BTreeSet<_> = g.blocked_reasons.iter().cloned().collect();
            let mut after = BTreeSet::new();
            if mismatched.contains(&g.unit) {
                after.insert("identity_mismatch".to_string());
            }
            for (field, reason, count) in [
                (
                    "total_limit",
                    "total_exhausted",
                    g.total_received.integer(&g.unit)?,
                ),
                (
                    "window_limit",
                    "window_exhausted",
                    g.window_received.integer(&g.unit)?,
                ),
            ] {
                if !set[field].is_null() && count >= num(&set[field], field)? {
                    after.insert(reason.to_string());
                }
            }
            if before != after {
                changes.push(serde_json::json!({"unit":g.unit,"before":before,"after":after}));
                g.blocked_reasons = after.into_iter().collect();
            }
        }
        if changes.is_empty() {
            return Ok(None);
        }
        let active: BTreeSet<_> = self
            .input
            .geometry
            .channels
            .iter()
            .filter(|(_, c)| {
                let uid = &self.input.geometry.ports[&c.target_port].unit;
                next.iter()
                    .find(|g| g.unit == *uid)
                    .is_none_or(|g| g.blocked_reasons.is_empty())
            })
            .map(|(cid, _)| cid.clone())
            .collect();
        self.check_branch_graph(&active)?;
        let removed: Vec<_> = self.active.difference(&active).cloned().collect();
        let restored: Vec<_> = active.difference(&self.active).cloned().collect();
        self.state.logistics.gate_counters = next;
        self.rebuild_graph()?;
        Ok(Some(
            serde_json::json!({
                "gates":changes.iter().map(|c| c["unit"].clone()).collect::<Vec<_>>(),
                "removed_channels":removed,"restored_channels":restored,"reason_changes":changes
            })
            .to_string(),
        ))
    }
}
