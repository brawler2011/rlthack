export type SupplierRole = "MANUFACTURER" | "DISTRIBUTOR" | "SUPPLIER";

export interface LotItem {
  lot_id?: number | null;
  procedure_name: string;
  subject: string;
  start_price: number;
  okpd2_code: string;
  is_smp: boolean;
  customer_kpp?: string | null;
  customer_inn?: string | null;
  publish_date?: string | null;
  procedure_id?: number | null;
}

export interface XaiFactor {
  factor_name: string;
  shap_value: number;
  description: string;
}

export interface SupplierItem {
  inn: string;
  kpp: string;
  name: string | null;
  role: SupplierRole;
  role_display: string;
  score: number;
  win_rate: number;
  contracts_count: number;
  avg_contract_price: number;
  is_spb_lo: boolean;
  is_smp: boolean;
  xai: {
    summary: string;
    factors: XaiFactor[];
    recommendation_level: string;
  } | null;
}

export interface SupplierEnrichment {
  inn: string;
  role?: SupplierRole | null;
  is_gisp_manufacturer?: boolean | null;
  okved_main?: string | null;
  status?: string | null;
}

export interface SearchSuppliersRequest {
  lot: LotItem;
  role_filter?: SupplierRole[];
  only_spb_lo?: boolean;
  only_smp?: boolean;
  min_win_rate?: number;
  limit?: number;
}

export interface SearchSuppliersResponse {
  total: number;
  items: SupplierItem[];
  inference_time_ms: number;
}
