#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
rustfmt --edition 2021 --config skip_children=true crates/kernel/src/catalog.rs crates/kernel/src/input.rs crates/kernel/src/model.rs crates/kernel/src/engine.rs crates/kernel/src/seed.rs crates/kernel/src/polling.rs crates/kernel/src/cache.rs crates/kernel/src/transition.rs crates/kernel/src/cycle.rs crates/kernel/src/tests_bridge.rs crates/topology/tests/validation.rs
