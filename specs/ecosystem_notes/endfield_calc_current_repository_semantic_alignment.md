# endfield-calc -> current_repository_rules semantic alignment

This note records the explicit, build-time-only mapping used to compare the raw
`JamboChen/endfield-calc` snapshot against the repository's frozen
`rules/canonical_rules.json` vocabulary.

Scope:

- partial only
- validated against exact recipe core fields (`facility_type`, `cycle_seconds`,
  `inputs`, `outputs`)
- utilities such as `protocol_core`, `power_pole`, and storage/boundary helpers
  remain unmatched because the upstream `src/data/facilities.ts` surface does not
  expose them

## Item families

| Canonical item | Upstream item |
|---|---|
| `source_ore` | `item_originium_ore` |
| `source_powder` | `item_originium_powder` |
| `dense_source_powder` | `item_originium_enr_powder` |
| `blue_iron_ore` | `item_iron_ore` |
| `blue_iron_block` | `item_iron_nugget` |
| `blue_iron_powder` | `item_iron_powder` |
| `dense_blue_iron_powder` | `item_iron_enr_powder` |
| `steel_block` | `item_iron_enr` |
| `steel_part` | `item_iron_enr_cmpt` |
| `steel_bottle` | `item_iron_enr_bottle` |
| `buckwheat` | `item_plant_moss_1` |
| `buckwheat_seed` | `item_plant_moss_seed_1` |
| `buckwheat_powder` | `item_plant_moss_powder_1` |
| `fine_buckwheat_powder` | `item_plant_moss_enr_powder_1` |
| `sandleaf` | `item_plant_moss_3` |
| `sandleaf_seed` | `item_plant_moss_seed_3` |
| `sandleaf_powder` | `item_plant_moss_powder_3` |
| `valley_battery` | `item_proc_battery_3` |
| `qiaoyu_capsule` | `item_bottled_rec_hp_3` |

## Recipe slice

| Canonical recipe | Upstream recipe | Canonical facility |
|---|---|---|
| `packaging_battery` | `tools_proc_battery_3_1` | `manufacturing_6x4` |
| `filling_capsule` | `filling_bottled_rec_hp_3_1` | `manufacturing_6x4` |
| `parts_maker` | `component_iron_enr_cmpt_1` | `manufacturing_3x3` |
| `molding_bottle` | `shaper_iron_enr_bottle_1` | `manufacturing_3x3` |
| `grinder_dense_source` | `thickener_originium_enr_powder_1` | `manufacturing_6x4` |
| `grinder_fine_buckwheat` | `thickener_plant_moss_enr_powder_1_1` | `manufacturing_6x4` |
| `grinder_dense_blue_iron` | `thickener_iron_enr_powder_1` | `manufacturing_6x4` |
| `refinery_steel` | `furnance_iron_enr_1` | `manufacturing_3x3` |
| `refinery_blue_iron` | `furnance_iron_nugget_1` | `manufacturing_3x3` |
| `crusher_source` | `grinder_originium_powder_1` | `manufacturing_3x3` |
| `crusher_blue_iron` | `grinder_iron_powder_1` | `manufacturing_3x3` |
| `crusher_buckwheat` | `grinder_plant_moss_powder_1_1` | `manufacturing_3x3` |
| `crusher_sandleaf` | `grinder_plant_moss_powder_3_1` | `manufacturing_3x3` |
| `seed_collector_buckwheat` | `seedcollector_plant_moss_1_1` | `manufacturing_5x5` |
| `seed_collector_sandleaf` | `seedcollector_plant_moss_3_1` | `manufacturing_5x5` |
| `planter_buckwheat` | `planter_plant_moss_1_1` | `manufacturing_5x5` |
| `planter_sandleaf` | `planter_plant_moss_3_1` | `manufacturing_5x5` |

## Ambiguity note

The buckwheat / capsule branch has a structurally identical alternate based on
`moss_2` + `bottled_food_3`. The current mapping deliberately chooses the
`moss_1` + `bottled_rec_hp_3` branch because the canonical end-product is a
restorative capsule rather than food.
