# IndustrialPlanner Export Bundle

When a canonical blueprint is exported for IndustrialPlanner compatibility, the
bundle is written here:

```text
industrial_planner.blueprint.json
industrial_planner.compatibility_manifest.json
```

Generate the bundle with:

```bash
python scripts/export_industrial_planner_bundle.py
```

This directory is additive and postprocess-only. It does not replace the
canonical internal artifact `data/blueprints/optimal_blueprint.json`.
