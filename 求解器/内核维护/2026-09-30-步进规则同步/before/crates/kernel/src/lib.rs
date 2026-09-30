//! kernel_profile_v1 有限轨迹内核；不承担全称参数、可达循环或目标认证。
#![forbid(unsafe_code)]
mod cache;
pub mod catalog;
pub mod config;
pub mod cycle;
mod cycle_io;
mod digest;
pub mod engine;
pub mod event_identity;
pub mod input;
mod interfaces;
pub mod ledger;
pub mod model;
pub mod output;
mod polling;
mod seed;
mod transition;
pub mod value;
mod warehouse;
pub use config::Config;
pub use engine::Engine;
pub use input::Input;
pub use value::{Result, Stop};

#[cfg(test)]
mod tests;
