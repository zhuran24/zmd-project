"""
Semantic validator for canonical rules.
Status: CURRENT_CODE_ALIGNED

目标：执行 JSON Schema 与 Pydantic 模型之外的跨字段校验，拦截违反冻结真理或
破坏 preprocess 真值一致性的静态规则变更。
"""

from __future__ import annotations

from typing import List

from src.rules.models import CanonicalRulesDocument


class SemanticValidationError(ValueError):
    """当静态规则底座违反跨字段业务语义或冻结真理时抛出。"""


class CanonicalSemanticValidator:
    def __init__(self, doc: CanonicalRulesDocument):
        self.doc = doc
        self.errors: List[str] = []

    def validate(self) -> None:
        """执行所有语义级校验。"""
        self.errors.clear()

        self._check_frozen_constants()
        self._check_recipe_template_references()
        self._check_manufacturing_power_requirements()
        self._check_port_rule_dependencies()
        self._check_recipe_io_sanity()
        self._check_production_targets()
        self._check_commodity_metadata()

        if self.errors:
            error_msg = "\n".join([f"  - {err}" for err in self.errors])
            raise SemanticValidationError(
                f"规则字典未通过深层语义校验，发现 {len(self.errors)} 个致命冲突:\n{error_msg}"
            )

    def _check_frozen_constants(self) -> None:
        if self.doc.globals.grid.width != 70 or self.doc.globals.grid.height != 70:
            self.errors.append("违反冻结真理：主基地必须为 70x70 离散网格。")

        if self.doc.globals.time.tick_interval_seconds != 2.0:
            self.errors.append("违反冻结真理：基础时间单位必须为 1 tick = 2.0 秒。")

        bridge = self.doc.routing_rules.bridge_mechanics
        if not bridge.can_overlap_straight_belt:
            self.errors.append(
                "违反冻结真理：物流桥必须允许真三维重叠跨越直线传送带 (can_overlap_straight_belt 必须为 True)。"
            )
        if bridge.can_turn:
            self.errors.append("违反冻结真理：物流桥在空中绝对不可转弯 (can_turn 必须为 False)。")

        for tpl_id, tpl in self.doc.facility_templates.items():
            if tpl.port_rule == "core_specific" and not tpl.rotatable:
                self.errors.append(f"违反冻结真理：协议核心必须可移动、可旋转。模板 '{tpl_id}' 的 rotatable 为 False。")

    def _check_recipe_template_references(self) -> None:
        templates = self.doc.facility_templates
        for recipe_id, recipe in self.doc.recipes.items():
            if recipe.template not in templates:
                self.errors.append(f"外键冲突：配方 '{recipe_id}' 引用了不存在的模板 '{recipe.template}'。")

    def _check_manufacturing_power_requirements(self) -> None:
        templates = self.doc.facility_templates
        for recipe_id, recipe in self.doc.recipes.items():
            tpl = templates.get(recipe.template)
            if tpl and not tpl.needs_power:
                self.errors.append(
                    f"违反冻结真理：配方 '{recipe_id}' 引用的制造设施模板 '{recipe.template}' 被标记为不需要供电 (needs_power=False)。所有制造单位必须供电。"
                )

    def _check_port_rule_dependencies(self) -> None:
        for tpl_id, tpl in self.doc.facility_templates.items():
            if tpl.port_rule == "core_specific":
                if tpl.core_limits is None:
                    self.errors.append(
                        f"字段约束冲突：模板 '{tpl_id}' 指定了 'core_specific' 端口规则，但缺失 'core_limits' 字段。"
                    )
            else:
                if getattr(tpl, "core_limits", None) is not None:
                    self.errors.append(
                        f"字段约束冲突：模板 '{tpl_id}' 的端口规则不是 'core_specific'，但错误地携带了 'core_limits' 字段。"
                    )

            if getattr(tpl, "power_coverage_radius", None) is not None and tpl.needs_power:
                self.errors.append(
                    f"违反冻结真理：模板 '{tpl_id}' 提供了供电半径，但其自身要求供电 (needs_power=True)。供电/物流设施不需要供电。"
                )

            if getattr(tpl, "placement_rule", None) == "left_or_bottom_boundary" and tpl.port_rule != "inward_facing":
                self.errors.append(
                    f"字段约束冲突：模板 '{tpl_id}' 位于边界 (left_or_bottom_boundary)，必须强制配置为向内侧开放端口 (inward_facing)。"
                )

    def _check_recipe_io_sanity(self) -> None:
        for recipe_id, recipe in self.doc.recipes.items():
            if not recipe.outputs:
                self.errors.append(f"配方死环：配方 '{recipe_id}' 没有任何输出，违反了节点连通性。")

            overlap = set(recipe.inputs.keys()).intersection(set(recipe.outputs.keys()))
            if overlap:
                self.errors.append(f"配方死锁：配方 '{recipe_id}' 存在自循环的同名物品 {overlap}，将导致无限死锁。")

    def _check_production_targets(self) -> None:
        if not self.doc.production_targets:
            self.errors.append("production_targets 不能为空。")
            return
        for commodity_id, target in self.doc.production_targets.items():
            if target.final_recipe_id not in self.doc.recipes:
                self.errors.append(
                    f"生产目标冲突：'{commodity_id}' 的 final_recipe_id '{target.final_recipe_id}' 不存在。"
                )
                continue
            final_recipe = self.doc.recipes[target.final_recipe_id]
            if commodity_id not in final_recipe.outputs:
                self.errors.append(
                    f"生产目标冲突：'{commodity_id}' 不是其 final_recipe '{target.final_recipe_id}' 的输出。"
                )

    def _check_commodity_metadata(self) -> None:
        producers: dict[str, list[str]] = {}
        for recipe_id, recipe in self.doc.recipes.items():
            for commodity_id in recipe.outputs:
                producers.setdefault(commodity_id, []).append(recipe_id)

        for commodity_id, meta in self.doc.commodity_metadata.items():
            if meta.source_kind == "cycle_internal" and not meta.cycle_group:
                self.errors.append(
                    f"商品元数据冲突：cycle_internal 商品 '{commodity_id}' 必须声明 cycle_group。"
                )
            if meta.sink_kind == "generic_input" and commodity_id not in self.doc.production_targets:
                self.errors.append(
                    f"商品元数据冲突：generic_input 商品 '{commodity_id}' 必须对应一个 production_target。"
                )

        for commodity_id in self.doc.production_targets:
            meta = self.doc.commodity_metadata.get(commodity_id)
            if meta is None:
                self.errors.append(f"生产目标 '{commodity_id}' 缺少 commodity_metadata。")
            elif meta.sink_kind != "generic_input":
                self.errors.append(
                    f"生产目标 '{commodity_id}' 必须在 commodity_metadata 中声明 sink_kind='generic_input'。"
                )

        for commodity_id, recipe_ids in producers.items():
            meta = self.doc.commodity_metadata.get(commodity_id)
            if meta is not None and meta.cycle_group is None and len(recipe_ids) > 1:
                self.errors.append(
                    f"商品元数据冲突：非 cycle 商品 '{commodity_id}' 不能拥有多个 producer recipes: {', '.join(sorted(recipe_ids))}。"
                )


def validate_canonical_document(doc: CanonicalRulesDocument) -> None:
    validator = CanonicalSemanticValidator(doc)
    validator.validate()
