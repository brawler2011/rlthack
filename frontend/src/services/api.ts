import type {
  SearchSuppliersRequest,
  SearchSuppliersResponse,
  LotItem,
  SupplierEnrichment,
} from "../types";

const API_BASE = "/api/v1";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  const timeout = window.setTimeout(cancel, 30_000);
  options.signal?.addEventListener("abort", cancel, { once: true });
  if (options.signal?.aborted) controller.abort();

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: controller.signal,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      const detail = typeof body?.detail === "string" ? body.detail : null;
      if (response.status === 422) {
        throw new Error(detail ?? "Проверьте параметры закупки: сервер не принял запрос.");
      }
      throw new Error(detail ?? "Сервис временно недоступен. Попробуйте ещё раз.");
    }
    return await response.json();
  } catch (error) {
    if (options.signal?.aborted) throw error;
    if (controller.signal.aborted) {
      throw Object.assign(new Error("Сервис не ответил за 30 секунд. Попробуйте ещё раз."), {
        cause: error,
      });
    }
    if (error instanceof TypeError) {
      throw Object.assign(
        new Error("Не удалось связаться с сервисом. Проверьте соединение и повторите запрос."),
        { cause: error }
      );
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
    options.signal?.removeEventListener("abort", cancel);
  }
}

export function searchSuppliers(req: SearchSuppliersRequest, signal?: AbortSignal) {
  return request<SearchSuppliersResponse>("/suppliers/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal,
  });
}

export function searchLots(query: string, signal?: AbortSignal) {
  return request<LotItem[]>(`/lots/search?query=${encodeURIComponent(query)}&limit=20`, {
    signal,
  });
}

export function getSupplierEnrichment(inn: string, signal?: AbortSignal) {
  return request<SupplierEnrichment>(`/enrichment/${encodeURIComponent(inn)}`, { signal });
}
