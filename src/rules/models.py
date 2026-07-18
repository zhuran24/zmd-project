"""
Pydantic V2 models for canonical rules and facility templates.
Status: CURRENT_CODE_ALIGNED

目标：提供 `rules/canonical_rules.json` 到 Python 运行时的强类型、不可变映射。
当前 canonical rules 已承载：
- 静态网格 / 物流 / 路由常量
- facility template 真值
- preprocess 真实 recipe truth
- production targets
- commodity metadata

仍然禁止把实例数量推导、启发式参数或运行时状态塞回这里。
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat


class StrictBaseModel(BaseModel):
    """全局基类：严格拒绝未知字段，并保持加载后不可变。"""

    model_config = ConfigDict(extra="forbid", frozen=True)


# -----------------------------------------------------------------------------
# Globals & environment constants
# -----------------------------------------------------------------------------


class GridConfig(StrictBaseModel):
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)


class TimeConfig(StrictBaseModel):
    tick_interval_seconds: PositiveFloat


class LogisticsConfig(StrictBaseModel):
    belt_capacity_per_tick: PositiveFloat
    port_max_throughput_per_tick: PositiveFloat
    machine_min_clearance_cells: int = Field(..., ge=0)


class EmptyRectangleConfig(StrictBaseModel):
    objective: Literal["max_lex_area_min_side"]
    min_side_admissibility: int = Field(..., ge=1)


class GlobalsConfig(StrictBaseModel):
    grid: GridConfig
    empty_rectangle: EmptyRectangleConfig
    time: TimeConfig
    logistics: LogisticsConfig


# -----------------------------------------------------------------------------
# Routing rules
# -----------------------------------------------------------------------------


class LayersConfig(StrictBaseModel):
    ground: Literal[0] = 0
    elevated: Literal[1] = 1


class BridgeMechanicsConfig(StrictBaseModel):
    can_overlap_solid: bool
    can_overlap_straight_belt: bool
    can_overlap_curved_belt: bool
    can_overlap_splitter_merger: bool
    can_turn: bool


class RoutingRulesConfig(StrictBaseModel):
    layers: LayersConfig
    bridge_mechanics: BridgeMechanicsConfig


# -----------------------------------------------------------------------------
# Facility templates
# -----------------------------------------------------------------------------


class Dimensions(StrictBaseModel):
    w: int = Field(..., ge=1)
    h: int = Field(..., ge=1)


class CoreLimits(StrictBaseModel):
    max_outputs: int = Field(..., ge=0)
    max_inputs: int = Field(..., ge=0)


PortRuleType = Literal[
    "opposite_parallel_sides",
    "long_sides",
    "core_specific",
    "none",
    "inward_facing",
]


class FacilityTemplate(StrictBaseModel):
    """实体模板的几何包围盒、供电和端口规则。"""

    dimensions: Dimensions
    rotatable: bool
    needs_power: bool
    is_solid_z: bool
    port_rule: PortRuleType
    core_limits: Optional[CoreLimits] = None
    power_coverage_radius: Optional[int] = Field(default=None, ge=0)
    placement_rule: Optional[Literal["left_or_bottom_boundary"]] = None


# -----------------------------------------------------------------------------
# Preprocess truth carried by canonical rules
# -----------------------------------------------------------------------------


class Recipe(StrictBaseModel):
    """制造配方的理论吞吐周期与 IO 速率。"""

    template: str
    ticks_per_cycle: int = Field(..., ge=1)
    inputs: Dict[str, PositiveFloat] = Field(default_factory=dict)
    outputs: Dict[str, PositiveFloat] = Field(default_factory=dict)


ProductionTargetMode = Literal["equivalent_full_speed_lines", "rate_per_tick"]
CommoditySourceKind = Literal["external_boundary", "cycle_internal", "internal_only"]
CommoditySinkKind = Literal["generic_input", "none"]


class ProductionTarget(StrictBaseModel):
    mode: ProductionTargetMode
    value: PositiveFloat
    final_recipe_id: str


class CommodityMetadata(StrictBaseModel):
    source_kind: Optional[CommoditySourceKind] = None
    sink_kind: Optional[CommoditySinkKind] = None
    cycle_group: Optional[str] = None


# -----------------------------------------------------------------------------
# Root canonical rules document
# -----------------------------------------------------------------------------


class MetadataConfig(StrictBaseModel):
    version: str
    description: str


class CanonicalRulesDocument(StrictBaseModel):
    """`rules/canonical_rules.json` 的根对象。"""

    schema_url: Optional[str] = Field(default=None, alias="$schema")

    metadata: MetadataConfig
    globals: GlobalsConfig
    routing_rules: RoutingRulesConfig
    facility_templates: Dict[str, FacilityTemplate]
    production_targets: Dict[str, ProductionTarget]
    commodity_metadata: Dict[str, CommodityMetadata]
    recipes: Dict[str, Recipe]
    semantics: Optional[Dict[str, Any]] = None
