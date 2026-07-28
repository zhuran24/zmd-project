# Repository Guidelines

## Project Structure & Module Organization

This is a Python 3.13, OR-Tools/CP-SAT project. `main.py` is the local solver entry point. Core code lives under `src/`: `search/` owns orchestration, campaigns, and certification; `models/` contains master, binding, and routing models; `cuts/` manages cut lifecycles; and `io/`, `render/`, and `adapters/` support strict serialization and delivery surfaces. Primary tests are in `src/tests/`; auxiliary memory tests live in `cc_memory/tests/` and `cc_memory_vnext/tests/`.

Canonical inputs and proof metadata live in `rules/` and `data/{preprocessed,proof_obligations,review_gates}`. Operational gates and launchers are in `scripts/`; design and verification material is in `docs/`, `specs/`, `formal/`, and `certside/`. Read `PROJECT_LOCK.md` before proof-sensitive work. When `.codegraph/` exists, use `codegraph explore` before broad text searches, then confirm sensitive conclusions against source.

Repository code-asset classification lives in
`data/repository_governance/code_assets.json`, is constrained by its adjacent schema, and is
validated by `devtools/check_repository_code_assets.py`. Read
`docs/项目说明/24_repository_asset_governance.md` before changing search, import, lint, pytest
discovery, or historical-evidence boundaries. `.rgignore` is a developer-search projection only;
use `git grep` for an all-tracked search.

## Build, Test, and Development Commands

```bash
python -m pip install -r requirements.lock.txt -r requirements-dev.lock.txt
python main.py
python devtools/check_repository_code_assets.py check
python devtools/check_repository_code_assets.py lint --profile developer --format nul \
  | xargs -0 -r python -m ruff check
python -m pytest --repository-workflow=developer src/tests
python scripts/preflight_gate.py --full
python scripts/preflight_gate.py --slow-tests
```

The locked requirements match CI. The developer pytest workflow excludes historical
evidence/replay discovery. For a fast explicit evidence lane, combine
`--repository-workflow=evidence` with `-m "evidence and not replay and not slow"`; for replay use
`--repository-workflow=replay -m "replay and not slow"`. `--full` runs mypy, Ruff, and non-slow
pytest across the authoritative boundary; the slow soundness lane is separate. For a focused
test, use:

```bash
python -m pytest -p no:randomly --basetemp=.pytest_tmp/one path/to/test.py::test_name -q
```

## Coding Style & Naming Conventions

Use four-space indentation, `snake_case` for modules/functions, `CapWords` for classes, and `UPPER_SNAKE_CASE` for constants. Add type annotations on new public surfaces. Ruff targets Python 3.13, checks `E/F/W`, and uses 120 columns as a reference; no formatter is configured. Preserve LF endings, especially for hash-pinned files. Keep `certified_exact` and exploratory behavior strictly isolated.

## Testing Guidelines

Name files `test_*.py` and tests `test_*`. Add regression coverage beside the affected subsystem. Register tests taking about eight seconds or longer in `src/tests/conftest.py`'s centralized slow list. Concurrent pytest sessions must use distinct `--basetemp` directories. Some suites require the external `candidate_placements` artifact. Do not use `.rgignore`, default pytest discovery, or developer lint projection to make a full-repository security, artifact, hash, or proof claim.

## Commit & Pull Request Guidelines

Recent history uses scoped Conventional Commit subjects, often bilingual: `feat(pb): ...`, `fix(cleanroom): ...`, `test(batch4): ...`, or `docs(roadmap): ...`. Keep each commit focused and include verification outcomes when useful. PRs should describe scope, authority or frozen-artifact impact, exact checks run, and any linked issue or owner decision. Include screenshots only for rendered or consumer-facing changes. Never commit generated checkpoints, canonical proof outputs, credentials, or ad hoc `.artifacts/` evidence.
