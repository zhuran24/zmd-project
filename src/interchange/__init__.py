"""Neutral interchange contracts for ecosystem-facing adapters."""

from src.interchange.compatibility_manifest import (
    COMPATIBILITY_MANIFEST_VERSION,
    build_compatibility_manifest,
    build_mapping_entry,
)
from src.interchange.export_registry import ExportRegistry, ExportTargetDefinition
from src.interchange.preprocess_context import (
    PREPROCESS_PLAN_VERSION,
    CommodityRole,
    CycleGroup,
    PreprocessContext,
    PreprocessRecipe,
    ProductionTarget,
    UtilityOperation,
    build_preprocess_context_from_rules_and_plan,
    build_producer_index,
    build_template_mapping,
    load_default_preprocess_context,
    load_preprocess_context_from_paths,
    solve_cycle_group_exact,
    validate_preprocess_context,
)
from src.interchange.normalized_catalog import (
    NORMALIZED_CATALOG_VERSION,
    NormalizedCatalog,
    build_catalog_from_rules_payload,
    build_catalog_metadata,
    catalog_stable_hash,
    normalize_catalog_payload,
)
from src.interchange.target_capabilities import TargetCapabilities, normalize_target_capabilities

__all__ = [
    "PREPROCESS_PLAN_VERSION",
    "CommodityRole",
    "CycleGroup",
    "PreprocessContext",
    "PreprocessRecipe",
    "ProductionTarget",
    "UtilityOperation",
    "COMPATIBILITY_MANIFEST_VERSION",
    "NORMALIZED_CATALOG_VERSION",
    "ExportRegistry",
    "ExportTargetDefinition",
    "NormalizedCatalog",
    "TargetCapabilities",
    "build_preprocess_context_from_rules_and_plan",
    "build_producer_index",
    "build_template_mapping",
    "load_default_preprocess_context",
    "load_preprocess_context_from_paths",
    "solve_cycle_group_exact",
    "validate_preprocess_context",
    "build_catalog_from_rules_payload",
    "build_catalog_metadata",
    "build_compatibility_manifest",
    "build_mapping_entry",
    "catalog_stable_hash",
    "normalize_catalog_payload",
    "normalize_target_capabilities",
]
