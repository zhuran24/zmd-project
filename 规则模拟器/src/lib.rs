//! Slice A reference simulator. LegalBase is the solver entry point.
//! The v1 historical replay interface lives in oracle.
mod action;
mod json;
mod model;
mod movement;
pub mod oracle;
mod snapshot;
mod state;
mod step;
mod topology;

pub use action::Action;
pub use model::{Cell, Channel, Counter, CounterPolicy, Event, Id, Item, Kind, Parameters, Slot};
pub type Res<T> = Result<T, String>;
use action::Simulation;
use serde_json::Value;
use topology::{History, Tables};

/// A base with a compliant event history, port limits at every prefix, and a
/// route to a terminal for every connected transport unit in the final layout.
pub struct LegalBase(Simulation);
impl LegalBase {
    fn tables(h: &History) -> Res<Tables> {
        if !h.legal() {
            return Err("正式基地的历史端口数不合或现布局走不通".into());
        }
        Tables::build(
            h,
            |_, _| None,
            |cs| Err(format!("合法基地的通道组没有级别 {cs:?}")),
        )
    }
    pub fn new(events: &[Event], params: Parameters, snapshot: &Value) -> Res<Self> {
        Ok(Self(Simulation::new(
            events.to_vec(),
            params,
            snapshot,
            Self::tables,
        )?))
    }
    pub fn step(&mut self) {
        self.0
            .state
            .step(&self.0.tables, &self.0.params, &step::Twice)
    }
    pub fn apply(&mut self, action: &Action) -> Res<()> {
        self.0.apply(action, Self::tables)
    }
    /// Current event order, including a successfully applied offline rebuild.
    pub fn history(&self) -> &[Event] {
        &self.0.events
    }
    pub fn snapshot(&self) -> Value {
        self.0.state.snapshot()
    }
}
