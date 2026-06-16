const ItemId = {
  ITEM_RAW_ORE: "raw_ore",
  ITEM_IRON_PLATE: "iron_plate",
  ITEM_LIQUID_WATER: "item_liquid_water",
} as const;

type ItemId = (typeof ItemId)[keyof typeof ItemId];

const RecipeId = {
  SMELT_IRON: "smelt_iron",
} as const;

type RecipeId = (typeof RecipeId)[keyof typeof RecipeId];

const FacilityId = {
  ITEM_PORT_FURNANCE_1: "item_port_furnance_1",
} as const;

type FacilityId = (typeof FacilityId)[keyof typeof FacilityId];

export { ItemId, RecipeId, FacilityId };
export type { ItemId, RecipeId, FacilityId };
