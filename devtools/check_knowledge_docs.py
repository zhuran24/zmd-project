#!/usr/bin/env python3
"""Fail-closed entry point for the repository knowledge-spine checker."""

from __future__ import annotations

from build_knowledge_docs import KnowledgeError, check_repository


def main() -> int:
    try:
        failures = check_repository()
    except KnowledgeError as exc:
        failures = (str(exc),)
    if failures:
        for failure in failures:
            print(f"BLOCK: {failure}")
        return 1
    print("PASS: knowledge spine is internally consistent and generated projections are fresh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
