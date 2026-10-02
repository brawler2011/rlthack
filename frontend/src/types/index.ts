import type { components } from "../contracts/schema";

type Schemas = components["schemas"];

export type SupplierRole = Schemas["SupplierRecommendation"]["role"];
export type LotInput = Schemas["NewLot"];
export type LotItem = Schemas["LotListItem"];
export type XaiFactor = Schemas["XaiFactor"];
export type SupplierItem = Schemas["SupplierRecommendation"];
export type SupplierEnrichment = Schemas["SupplierCard"];
export type SearchSuppliersRequest = Schemas["SearchRequest"];
export type SearchSuppliersResponse = Schemas["SearchResponse"];
export type Procurement = LotInput | LotItem;
