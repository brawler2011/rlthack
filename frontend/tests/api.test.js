import { afterAll, afterEach, beforeEach, expect, spyOn, test } from "bun:test";
import { toLotInput } from "../src/utils/lot";

const fetchSpy = spyOn(globalThis, "fetch");
const { searchSuppliers, searchLots, getSupplierEnrichment } = await import("../src/services/api");
let timeoutSpy;
let clearTimeoutSpy;

beforeEach(() => fetchSpy.mockReset());
afterEach(() => {
  timeoutSpy?.mockRestore();
  clearTimeoutSpy?.mockRestore();
  timeoutSpy = undefined;
  clearTimeoutSpy = undefined;
});
afterAll(() => fetchSpy.mockRestore());

const lot = {
  procedure_name: "Ручной подбор",
  subject: "Ноутбуки",
  start_price: 100000,
  okpd2_code: "26.20",
  is_smp: false,
  customer_inn: null,
  customer_kpp: null,
};
const body = {
  lot,
  role_filter: [],
  only_spb_lo: false,
  only_smp: false,
  min_win_rate: 0,
  limit: 20,
};

test("search sends all required keys, including nulls and disabled filters", async () => {
  const result = { total: 0, items: [], inference_time_ms: 0 };
  fetchSpy.mockResolvedValue(Response.json(result));
  expect(await searchSuppliers(body)).toEqual(result);
  const [request] = fetchSpy.mock.calls[0];
  expect(new URL(request.url).pathname).toBe("/api/v1/suppliers/search");
  expect(request.method).toBe("POST");
  expect(request.headers.get("Content-Type")).toBe("application/json");
  expect(await request.json()).toEqual(body);
});

test("historical lot is projected to the input contract before searching", async () => {
  const historical = { ...lot, lot_id: 123, publish_date: null, procedure_id: 456 };
  fetchSpy.mockResolvedValue(Response.json({ total: 0, items: [], inference_time_ms: 0 }));
  await searchSuppliers({ ...body, lot: toLotInput(historical) });
  const sent = await fetchSpy.mock.calls[0][0].json();
  expect(sent.lot).toEqual(lot);
  expect(sent.lot).not.toHaveProperty("lot_id");
  expect(sent.lot).not.toHaveProperty("publish_date");
  expect(sent.lot).not.toHaveProperty("procedure_id");
});

test("lot search serializes query parameters and returns historical lots", async () => {
  const result = [{ ...lot, lot_id: 1, publish_date: null, procedure_id: null }];
  fetchSpy.mockResolvedValue(Response.json(result));
  expect(await searchLots("Бумага & картриджи")).toEqual(result);
  const url = new URL(fetchSpy.mock.calls[0][0].url);
  expect(url.pathname).toBe("/api/v1/lots/search");
  expect(url.searchParams.get("query")).toBe("Бумага & картриджи");
  expect(url.searchParams.get("limit")).toBe("20");
});

test("enrichment uses the typed path and preserves explicit nulls", async () => {
  const result = {
    inn: "7802587594",
    role: null,
    is_gisp_manufacturer: null,
    okved_main: null,
    status: null,
  };
  fetchSpy.mockResolvedValue(Response.json(result));
  expect(await getSupplierEnrichment(result.inn)).toEqual(result);
  expect(new URL(fetchSpy.mock.calls[0][0].url).pathname).toBe("/api/v1/enrichment/7802587594");
});

test("validation errors retain the Russian message", async () => {
  fetchSpy.mockResolvedValue(
    Response.json(
      { detail: [{ loc: ["body", "limit"], msg: "Invalid", type: "greater_than" }] },
      {
        status: 422,
      }
    )
  );
  await expect(searchSuppliers(body)).rejects.toThrow(
    "Проверьте параметры закупки: сервер не принял запрос."
  );
});

test("server detail is displayed when present", async () => {
  fetchSpy.mockResolvedValue(Response.json({ detail: "Попробуйте позже" }, { status: 503 }));
  await expect(searchLots("")).rejects.toThrow("Попробуйте позже");
});

test("non-JSON server errors retain the service-unavailable message", async () => {
  fetchSpy.mockResolvedValue(new Response("<html>Bad gateway</html>", { status: 502 }));
  await expect(searchLots("")).rejects.toThrow("Сервис временно недоступен. Попробуйте ещё раз.");
});

test("network errors retain the connection message", async () => {
  fetchSpy.mockRejectedValue(new TypeError("Failed to fetch"));
  await expect(searchLots("")).rejects.toThrow("Не удалось связаться с сервисом.");
});

function pendingUntilAbort(request) {
  return new Promise((resolve, reject) => {
    const abort = () => reject(new DOMException("Aborted", "AbortError"));
    if (request.signal.aborted) abort();
    else request.signal.addEventListener("abort", abort, { once: true });
  });
}

test("caller cancellation aborts fetch and is not reported as a timeout", async () => {
  fetchSpy.mockImplementation(pendingUntilAbort);
  const controller = new AbortController();
  const pending = searchLots("", controller.signal);
  controller.abort();
  await expect(pending).rejects.toThrow("Aborted");
  expect(fetchSpy.mock.calls[0][0].signal.aborted).toBe(true);
});

test("an already-cancelled request stays cancelled", async () => {
  fetchSpy.mockImplementation(pendingUntilAbort);
  const controller = new AbortController();
  controller.abort();
  await expect(searchLots("", controller.signal)).rejects.toThrow("Aborted");
});

test("30-second timeout aborts fetch and clears the timer", async () => {
  let expire;
  timeoutSpy = spyOn(globalThis, "setTimeout").mockImplementation((callback, delay) => {
    expect(delay).toBe(30_000);
    expire = callback;
    return 123;
  });
  clearTimeoutSpy = spyOn(globalThis, "clearTimeout").mockImplementation(() => {});
  fetchSpy.mockImplementation(pendingUntilAbort);
  const pending = searchLots("");
  expire();
  await expect(pending).rejects.toThrow("Сервис не ответил за 30 секунд.");
  expect(fetchSpy.mock.calls[0][0].signal.aborted).toBe(true);
  expect(clearTimeoutSpy).toHaveBeenCalledWith(123);
});
