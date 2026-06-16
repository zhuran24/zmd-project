import type { Recipe } from "../types";
import { ItemId, RecipeId, FacilityId } from "@/types/constants";

export const recipes: Recipe[] = [
  {
    id: RecipeId.SMELT_IRON,
    inputs: [{ itemId: ItemId.ITEM_RAW_ORE, amount: 2 }],
    outputs: [{ itemId: ItemId.ITEM_IRON_PLATE, amount: 1 }],
    facilityId: FacilityId.ITEM_PORT_FURNANCE_1,
    craftingTime: 3,
  },
];
