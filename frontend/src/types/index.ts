import type { components } from "../contracts/schema";

type Schemas = components["schemas"];

export type SupplierRole = Schemas["SupplierProfile"]["role"];
export type LotInput = Schemas["LotBase"];
export type LotItem = Schemas["LotResponse"];
export type XaiFactor = Schemas["XaiFactor"];
export type SupplierItem = Schemas["SupplierProfile"];
export type SupplierEnrichment = Schemas["SupplierEnrichment"];
export type SearchSuppliersRequest = Schemas["SupplierSearchRequest"];
export type SearchSuppliersResponse = Schemas["SupplierSearchResponse"];
