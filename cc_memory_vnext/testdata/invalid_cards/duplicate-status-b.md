---
id: invalid-status-b
kind: status
title: invalid duplicate status B
scope:
  domains:
    - duplicate-domain
  paths: []
  symbols: []
status: active
priority: P2
triggers:
  intents: []
  keywords:
    - duplicate
  negative_keywords: []
  paths: []
  symbols: []
  error_regex: []
  examples:
    - duplicate status should fail
activation:
  layer_hint: L1
validity:
  state: current
provenance:
  op: record
  reason: invalid test fixture
  evidence:
    - fixture
updated_at: "2026-06-26"
---
This fixture intentionally shares an active status domain with invalid-status-a.
