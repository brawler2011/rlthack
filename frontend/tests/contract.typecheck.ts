import type { components } from "../src/contracts/schema";
import type { LotInput, SupplierItem, SearchSuppliersRequest } from "../src/types";

type Assert<T extends true> = T;
type UndefinedKeys<T> = { [K in keyof T]-?: undefined extends T[K] ? K : never }[keyof T];
type Schemas = components["schemas"];
type InvalidModels = {
  [K in keyof Schemas]: UndefinedKeys<Schemas[K]> extends never ? never : K;
}[keyof Schemas];

export type AllJsonFieldsAreRequired = Assert<InvalidModels extends never ? true : false>;

// @ts-expect-error Unknown name is null, never undefined.
export const undefinedName: SupplierItem["name"] = undefined;
// @ts-expect-error Nullable fields must still be present.
export const missingLotKeys: LotInput = { subject: "Ноутбуки" };
// @ts-expect-error Filters use a list, never null.
export const nullRoleFilter: SearchSuppliersRequest["filters"]["roles"] = null;
// @ts-expect-error The win-rate filter uses a number, never undefined.
export const undefinedWinRate: SearchSuppliersRequest["filters"]["min_win_rate"] = undefined;
// @ts-expect-error Role is a closed enum.
export const invalidRole: SupplierItem["role"] = "OTHER";
