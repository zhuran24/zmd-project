//! 规则 L32—L33：只在成功移动后更新侧记忆。
use crate::{engine::Engine, graph::*, value::*};
use std::collections::BTreeMap;
impl Engine {
    pub(crate) fn cyclic_order(&self, subject: &Subject, side: &str) -> Vec<String> {
        let graph = &self.input.graph;
        let mut channels = if side == "input" {
            graph.inputs(subject)
        } else {
            graph.outputs(subject)
        }
        .to_vec();
        if channels.len() < 2 {
            return channels;
        }
        let key = format!("{}:{side}", graph.label(subject));
        let last = self.cursor_index.get(&key).and_then(|i| {
            self.state.logistics.poll_state.cursors[*i]
                .last_success
                .as_ref()
        });
        let start = if let Some(last) = last {
            (channels
                .iter()
                .position(|c| c == last)
                .expect("validated cursor")
                + 1)
                % channels.len()
        } else {
            usize::from(
                matches!(subject,Subject::Component(i) if (graph.components[*i].kind==ComponentKind::Splitter && side=="output") || (graph.components[*i].kind==ComponentKind::Merger && side=="input")),
            )
        };
        channels.rotate_left(start);
        channels
    }
    pub(crate) fn nontransport_order(&self, u: &str) -> Vec<String> {
        let graph = &self.input.graph;
        let mut groups = BTreeMap::<String, Vec<String>>::new();
        for ch in &graph.outputs_nt[u] {
            let peer = &graph.receiver[ch];
            let direct = matches!(peer,Receiver::Component(i) if graph.components[*i].kind==ComponentKind::Merger);
            groups
                .entry(if direct { ch.clone() } else { String::new() })
                .or_default()
                .push(ch.clone());
        }
        let mut groups: Vec<_> = groups.into_values().collect();
        groups.sort_by_key(|channels| {
            let layer = channels
                .iter()
                .map(|ch| match graph.receiver[ch] {
                    Receiver::Component(i) => graph.layers[i],
                    _ => 0,
                })
                .max()
                .unwrap_or(0);
            (layer, channels.iter().map(|c| graph.rank[c]).min().unwrap())
        });
        let recency = self
            .recency_index
            .get(u)
            .map(|i| self.state.logistics.poll_state.recency[*i].order.as_slice())
            .unwrap_or(&[]);
        for group in &mut groups {
            group.sort_by_key(|ch| match recency.iter().position(|c| c == ch) {
                None => (0, graph.rank[ch]),
                Some(i) => (1, i),
            });
        }
        groups.into_iter().flatten().collect()
    }
    pub(crate) fn success(&mut self, ch: &str) -> Result<()> {
        let graph = &self.input.graph;
        for (subject, side) in [
            (&graph.sender[ch], "output"),
            (&graph.receiver[ch], "input"),
        ] {
            if side == "output" {
                if let Subject::Unit(u) = subject {
                    if let Some(i) = self.recency_index.get(u) {
                        let order = &mut self.state.logistics.poll_state.recency[*i].order;
                        order.retain(|c| c != ch);
                        order.push(ch.into());
                    }
                    continue;
                }
            }
            let label = format!("{}:{side}", graph.label(subject));
            if let Some(i) = self.cursor_index.get(&label) {
                self.state.logistics.poll_state.cursors[*i].last_success = Some(ch.into());
            }
        }
        Ok(())
    }
}
