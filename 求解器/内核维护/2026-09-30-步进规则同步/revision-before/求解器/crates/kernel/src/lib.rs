//! kernel_profile_v2 整数步有限执行；不承担全称参数或可达循环认证。
#![forbid(unsafe_code)]
pub mod catalog;
pub mod config;
pub mod engine;
pub mod graph;
pub mod input;
mod interfaces;
pub mod ledger;
pub mod model;
mod polling;
mod step;
pub mod value;
mod warehouse;
pub use config::Config;
pub use engine::Engine;
pub use input::Input;
pub use model::StepReport;
pub use value::{Result, Stop};

#[cfg(test)]
mod tests_support;

#[cfg(test)]
mod tests_graph;

#[cfg(test)]
mod tests_step;

#[cfg(test)]
mod tests_manufacture;

#[cfg(test)]
mod tests_box_gate;

#[cfg(test)]
mod tests_seed;

#[cfg(test)]
mod tests_warehouse;

#[cfg(test)]
mod tests_config;

pub mod cycle;
mod cycle_io;
mod digest;
pub mod output;
mod seed;

#[cfg(test)]
mod tests_cycle;
#[cfg(test)]
mod tests_output;
