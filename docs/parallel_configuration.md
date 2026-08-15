# Parallel Configuration Guide

This guide covers runtime resource selection only. It does not change the objective, candidate proof
contract, supervisor authority, artifact identity, or publication gate. Current project state remains
in [`CURRENT.md`](CURRENT.md).

## Configuration source and precedence

The runtime source is `src/models/cp_sat_worker_config.py` together with the command-line and
environment parsing used by the active launcher. Stage-specific worker settings take precedence over
the shared worker setting, which in turn falls back to the implementation default.

Inspect the active interface instead of copying a dated default table:

```bash
python main.py --mode certified_exact --help
```

Launcher scripts are operational wrappers. They do not become proof sources or redefine precedence.

## Process multiplication

Approximate runnable solver pressure is the number of concurrent candidate processes multiplied by
the workers assigned to each active stage. Memory use, thread scheduling, and solver behavior are not
linear in that product, so profile the actual host and artifact set.

A configuration that avoids out-of-memory failure does not establish completeness or certification.
A faster configuration does not authorize a weaker timeout interpretation.

## Sizing procedure

1. Verify the campaign and artifact identity with the registered machine checks.
2. Start from a conservative process count and stage-worker budget.
3. Measure peak RSS, swap activity, stage latency, and worker failures on the target host.
4. Increase one dimension at a time and preserve the checkpoint between trials.
5. Treat memory pressure, worker failure, and budget exhaustion as operational outcomes, not proofs.
6. Record the chosen profile and host facts in the run-specific handoff, not in this living guide.

## Resume and worker consistency

All workers in one campaign must consume the same hash-bound input closure and the same parsed generic
input-slot mapping. Resume compatibility is an atomic implementation check; a scalar shortcut or a
second, independently read plan is not equivalent.

When the inspector reports incompatibility, reset or re-establish the proof chain. Do not use worker
configuration as a waiver.

## Operational entrypoints

- Script roles and wrappers: [`scripts/README.md`](../scripts/README.md)
- Exact campaign procedure: [`exact_campaign_operations.md`](exact_campaign_operations.md)
- Agent, test, and failure protocol: [`AGENT_OPERATIONS.md`](AGENT_OPERATIONS.md)
- Certified authority boundary: [`PROJECT_LOCK.md`](../PROJECT_LOCK.md)

Before changing this document or the runtime resolver, query the effective policy:

```bash
.venv/bin/python devtools/docctl.py context docs/parallel_configuration.md --intent edit
```
