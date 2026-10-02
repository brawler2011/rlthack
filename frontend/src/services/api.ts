import { createApiClient } from "../contracts/client";
import type { CsvBatchUpload, SearchSuppliersRequest } from "../types";

const client = createApiClient();

type ApiResult<T> = { data: T; response: Response } | { error: unknown; response: Response };

function errorDetail(error: unknown): string | null {
  if (typeof error === "object" && error !== null && "detail" in error) {
    return typeof error.detail === "string" ? error.detail : null;
  }
  return null;
}

async function request<T>(
  send: (signal: AbortSignal) => Promise<ApiResult<T>>,
  signal?: AbortSignal,
  timeoutMs = 30_000
): Promise<T> {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  const timeout = globalThis.setTimeout(cancel, timeoutMs);
  signal?.addEventListener("abort", cancel, { once: true });
  if (signal?.aborted) controller.abort();

  try {
    const result = await send(controller.signal);
    if ("data" in result) return result.data;
    const detail = errorDetail(result.error);
    if (result.response.status === 422) {
      throw new Error(detail ?? "Проверьте параметры закупки: сервер не принял запрос.");
    }
    throw new Error(detail ?? "Сервис временно недоступен. Попробуйте ещё раз.");
  } catch (error) {
    if (signal?.aborted) throw error;
    if (controller.signal.aborted) {
      throw Object.assign(
        new Error(`Сервис не ответил за ${timeoutMs / 1000} секунд. Попробуйте ещё раз.`),
        {
          cause: error,
        }
      );
    }
    if (error instanceof TypeError) {
      throw Object.assign(
        new Error("Не удалось связаться с сервисом. Проверьте соединение и повторите запрос."),
        { cause: error }
      );
    }
    throw error;
  } finally {
    globalThis.clearTimeout(timeout);
    signal?.removeEventListener("abort", cancel);
  }
}

export function matchCsvBatch(notices: File, items: File, signal?: AbortSignal) {
  const form = new FormData();
  form.append("notices", notices);
  form.append("items", items);
  return request(
    (requestSignal) =>
      client.POST("/api/v1/batch/csv", {
        // OpenAPI describes binary fields as strings; the browser sends the original files.
        body: form as unknown as CsvBatchUpload,
        bodySerializer: () => form,
        signal: requestSignal,
      }),
    signal,
    300_000
  );
}

export function searchSuppliers(body: SearchSuppliersRequest, signal?: AbortSignal) {
  return request(
    (requestSignal) => client.POST("/api/v1/suppliers/search", { body, signal: requestSignal }),
    signal
  );
}

export function searchLots(query: string, signal?: AbortSignal) {
  return request(
    (requestSignal) =>
      client.GET("/api/v1/lots/search", {
        params: { query: { query, limit: 20 } },
        signal: requestSignal,
      }),
    signal
  );
}

export function getSupplierEnrichment(inn: string, signal?: AbortSignal) {
  return request(
    (requestSignal) =>
      client.GET("/api/v1/enrichment/{inn}", {
        params: { path: { inn } },
        signal: requestSignal,
      }),
    signal
  );
}

export const getSupplierCard = getSupplierEnrichment;

export function getLot(lotId: number, signal?: AbortSignal) {
  return request(
    (requestSignal) =>
      client.GET("/api/v1/lots/{lot_id}", {
        params: { path: { lot_id: lotId } },
        signal: requestSignal,
      }),
    signal
  );
}
