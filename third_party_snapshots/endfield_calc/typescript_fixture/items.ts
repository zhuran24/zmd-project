import type { Item } from "../types";
import { ItemId } from "@/types/constants";

export const items: Item[] = [
  { id: ItemId.ITEM_RAW_ORE, tier: 1 },
  { id: ItemId.ITEM_IRON_PLATE, tier: 2 },
  { id: ItemId.ITEM_LIQUID_WATER, tier: 1, isLiquid: true },
];
