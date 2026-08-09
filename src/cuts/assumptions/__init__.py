"""Assumption verifier dispatch (cut_lifecycle_v2 v3.2.2 §4 Gap 5).

Phase 1.0 P1.4 — single home for production verifier 实施, separate from
lifecycle.py framework. Future families (Phase 1.1+) register new
verifier per cut_family_specs/* via _register() in verifiers.py.
"""
