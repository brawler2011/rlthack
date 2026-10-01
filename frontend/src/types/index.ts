// Mirrors backend/app/schemas: keep in sync with the API contract (see /docs).

export type SupplierRole = "MANUFACTURER" | "DISTRIBUTOR" | "SUPPLIER" | "UNKNOWN";

export interface NewLot {
  subject: string;
  items?: string[];
  okpd2_codes?: string[];
  start_price?: number | null;
  customer_inn?: string | null;
  channel?: string | null; // «АИС ГЗ» or «ЭМ»
  is_smp?: boolean;
}

export interface LotCard {
  lot_id: number | null;
  publish_date: string | null;
  subject: string;
  procedure_name: string | null;
  start_price: number | null;
  okpd2_codes: string[];
  items: string[];
  customer_inn: string | null;
  channel: string | null;
  is_smp: boolean;
  actual_winners: string[]; // INNs of real winners, for lots from the data
}

export interface LotListItem {
  lot_id: number;
  publish_date: string | null;
  subject: string | null;
  start_price: number | null;
  channel: string | null;
  customer_inn: string | null;
}

export interface XaiFactor {
  name: string;
  impact: number; // SHAP contribution, > 0 pushes the supplier up
  text: string;
}

export interface EvidenceLot {
  lot_id: number;
  publish_date: string | null;
  subject: string | null;
  start_price: number | null;
  won: boolean;
}

export interface Explanation {
  summary: string;
  level: "HIGH" | "MEDIUM" | "LOW";
  factors: XaiFactor[];
  evidence: EvidenceLot[];
}

export interface SupplierRecommendation {
  rank: number;
  inn: string;
  name: string | null;
  role: SupplierRole;
  role_display: string;
  role_reason: string | null;
  score: number; // 0..1 within this result
  win_rate: number | null;
  n_bids: number;
  n_wins: number;
  avg_won_price: number | null;
  region_code: string | null;
  is_spb_lo: boolean;
  is_smp: boolean | null;
  is_actual_winner: boolean;
  explanation: Explanation;
}

export interface NewSupplier {
  inn: string;
  name: string | null;
  role: SupplierRole;
  role_display: string;
  okved_main: string | null;
  okved_name: string | null;
  region_code: string | null;
  msp_category: number | null; // 1 micro, 2 small, 3 medium
  headcount: number | null;
  reason: string;
  score: number;
}

export interface SearchFilters {
  roles?: SupplierRole[] | null;
  only_spb_lo?: boolean;
  only_smp?: boolean;
  min_win_rate?: number | null;
}

export interface SearchRequest {
  lot_id?: number; // either lot_id or lot
  lot?: NewLot;
  filters?: SearchFilters;
  limit?: number;
  new_limit?: number;
}

export interface SearchResponse {
  lot: LotCard;
  items: SupplierRecommendation[];
  new_suppliers: NewSupplier[];
  total_candidates: number;
  timing_ms: number;
}

export interface OkpdExperience {
  prefix: string;
  n_bids: number;
  n_wins: number;
}

export interface SupplierCard {
  inn: string;
  name: string | null;
  role: SupplierRole;
  role_display: string;
  role_reason: string | null;
  okved_main: string | null;
  okved_name: string | null;
  okved_extra: string[];
  region_code: string | null;
  is_spb_lo: boolean | null;
  msp_category: number | null;
  headcount: number | null;
  msp_since: string | null;
  n_bids: number;
  n_wins: number;
  win_rate: number | null;
  avg_won_price: number | null;
  n_customers: number;
  top_okpd2: OkpdExperience[];
  recent_lots: EvidenceLot[];
}
