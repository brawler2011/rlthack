import type { SupplierRole } from "../types";

export interface Filters {
  roles: SupplierRole[];
  onlySpb: boolean;
  onlySmp: boolean;
  onlyReliable: boolean;
  minWinRate: number;
}

export const emptyFilters: Filters = {
  roles: [],
  onlySpb: false,
  onlySmp: false,
  onlyReliable: false,
  minWinRate: 0,
};
