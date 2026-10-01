import { SearchSuppliersRequest, SearchSuppliersResponse, LotItem } from '../types';

const API_BASE = '/api/v1';

export async function searchSuppliers(req: SearchSuppliersRequest): Promise<SearchSuppliersResponse> {
  const res = await fetch(`${API_BASE}/suppliers/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Search failed: ${res.statusText}`);
  return res.json();
}

export async function searchLots(query: string): Promise<LotItem[]> {
  const res = await fetch(`${API_BASE}/lots/search?query=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error(`Lots fetch failed: ${res.statusText}`);
  return res.json();
}

export async function getSupplierEnrichment(inn: string) {
  const res = await fetch(`${API_BASE}/enrichment/${inn}`);
  if (!res.ok) throw new Error(`Enrichment fetch failed: ${res.statusText}`);
  return res.json();
}
