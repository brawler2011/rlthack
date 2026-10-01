export type SupplierRole = "MANUFACTURER" | "DISTRIBUTOR" | "SUPPLIER";

export interface LotItem {
  lot_id?: number;
  procedure_name: string;
  subject: string;
  start_price: number;
  okpd2_code: string;
  is_smp: boolean;
  customer_kpp?: string;
  customer_inn?: string;
}

export interface XaiFactor {
  factor_name: string;
  shap_value: number;
  description: string;
}

export interface SupplierItem {
  inn: string;
  kpp: string;
  name: string;
  role: SupplierRole;
  role_display: string;
  score: number;
  win_rate: number;
  contracts_count: number;
  avg_contract_price: number;
  is_spb_lo: boolean;
  is_smp: boolean;
  xai_factors: XaiFactor[];
  xai_summary: string;
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
