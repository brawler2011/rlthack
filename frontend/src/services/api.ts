import { LotCard, LotListItem, SearchRequest, SearchResponse, SupplierCard } from "../types";

const API_BASE = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }
  return res.json();
}

export function searchSuppliers(req: SearchRequest): Promise<SearchResponse> {
  return request("/suppliers/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export function searchLots(query: string, limit = 20): Promise<LotListItem[]> {
  const params = new URLSearchParams({ query, limit: String(limit) });
  return request(`/lots/search?${params}`);
}

export function getLot(lotId: number): Promise<LotCard> {
  return request(`/lots/${lotId}`);
}

export function getSupplierCard(inn: string): Promise<SupplierCard> {
  return request(`/enrichment/${inn}`);
}
