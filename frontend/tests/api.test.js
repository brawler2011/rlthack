import { afterAll, afterEach, beforeEach, expect, spyOn, test } from "bun:test";
import { toSearchLot } from "../src/utils/lot";

const fetchSpy = spyOn(globalThis, "fetch");
const { searchSuppliers, searchLots, getSupplierEnrichment, getLot, matchCsvBatch } =
  await import("../src/services/api");

test("CSV upload sends two unchanged raw files as multipart with a batch timeout", async () => {
  const result = {
    lots: [],
    supplier_cards: {},
    total_lots: 0,
    total_items: 0,
    total_recommendations: 0,
    timing_ms: 0,
    selection_policy: "Правило",
  };
  fetchSpy.mockResolvedValue(Response.json(result));
  const notices = new File(["lot_id;subject\n1;Бумага"], "извещения.csv", { type: "text/csv" });
  const items = new File(["lot_id;product_name\n1;Бумага А4"], "потоварка.csv", {
    type: "text/csv",
  });
  expect(await matchCsvBatch(notices, items)).toEqual(result);
  const [request] = fetchSpy.mock.calls[0];
  expect(new URL(request.url).pathname).toBe("/api/v1/batch/csv");
  expect(request.headers.get("Content-Type")).toContain("multipart/form-data; boundary=");
  const form = await request.formData();
  expect(await form.get("notices").text()).toBe(await notices.text());
  expect(await form.get("items").text()).toBe(await items.text());
});
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
  subject: "Ноутбуки",
  start_price: 100000,
  okpd2_codes: ["26.20"],
  items: [],
  is_smp: false,
  customer_inn: null,
  channel: null,
};
const body = {
  lot_id: null,
  lot,
  filters: {
    roles: [],
    only_spb_lo: false,
    only_smp: false,
    min_win_rate: 0,
    only_reliable: false,
  },
  limit: 20,
  new_limit: 10,
};

test("search sends all required keys, including nulls and disabled filters", async () => {
  const result = { lot, items: [], new_suppliers: [], total_candidates: 0, timing_ms: 0 };
  fetchSpy.mockResolvedValue(Response.json(result));
  expect(await searchSuppliers(body)).toEqual(result);
  const [request] = fetchSpy.mock.calls[0];
  expect(new URL(request.url).pathname).toBe("/api/v1/suppliers/search");
  expect(request.method).toBe("POST");
  expect(request.headers.get("Content-Type")).toBe("application/json");
  expect(await request.json()).toEqual(body);
});

test("search sends the enabled reliability filter and preserves recommendation warnings", async () => {
  const result = {
    lot,
    items: [{ inn: "7802587594", warnings: ["Налоговая задолженность 100 000 ₽"] }],
    new_suppliers: [],
    total_candidates: 1,
    timing_ms: 0,
  };
  fetchSpy.mockResolvedValue(Response.json(result));
  expect(
    await searchSuppliers({ ...body, filters: { ...body.filters, only_reliable: true } })
  ).toEqual(result);
  const sent = await fetchSpy.mock.calls[0][0].json();
  expect(sent.filters.only_reliable).toBe(true);
});

test("historical lot searches by ID without sending response-only fields", async () => {
  const historical = {
    lot_id: 123,
    publish_date: null,
    subject: null,
    start_price: null,
    channel: null,
    customer_inn: null,
  };
  fetchSpy.mockResolvedValue(
    Response.json({ lot, items: [], new_suppliers: [], total_candidates: 0, timing_ms: 0 })
  );
  await searchSuppliers({ ...body, ...toSearchLot(historical) });
  const sent = await fetchSpy.mock.calls[0][0].json();
  expect(sent.lot_id).toBe(123);
  expect(sent.lot).toBeNull();
  expect(sent).not.toHaveProperty("publish_date");
});

test("manual lot projects only the required input fields", async () => {
  fetchSpy.mockResolvedValue(
    Response.json({ lot, items: [], new_suppliers: [], total_candidates: 0, timing_ms: 0 })
  );
  await searchSuppliers({ ...body, ...toSearchLot({ ...lot, actual_winners: [] }) });
  const sent = await fetchSpy.mock.calls[0][0].json();
  expect(sent.lot).toEqual(lot);
  expect(sent.lot_id).toBeNull();
});

test("lot search serializes query parameters and returns historical lots", async () => {
  const result = [
    {
      lot_id: 1,
      publish_date: null,
      subject: null,
      start_price: null,
      channel: null,
      customer_inn: null,
    },
  ];
  fetchSpy.mockResolvedValue(Response.json(result));
  expect(await searchLots("Бумага & картриджи")).toEqual(result);
  const url = new URL(fetchSpy.mock.calls[0][0].url);
  expect(url.pathname).toBe("/api/v1/lots/search");
  expect(url.searchParams.get("query")).toBe("Бумага & картриджи");
  expect(url.searchParams.get("limit")).toBe("20");
});

test("lot card uses the typed path and returns the current contract", async () => {
  const card = {
    ...lot,
    lot_id: 123,
    publish_date: null,
    procedure_name: null,
    actual_winners: [],
  };
  fetchSpy.mockResolvedValue(Response.json(card));
  expect(await getLot(123)).toEqual(card);
  expect(new URL(fetchSpy.mock.calls[0][0].url).pathname).toBe("/api/v1/lots/123");
});

test("enrichment uses the typed path and preserves explicit nulls", async () => {
  const result = {
    inn: "7802587594",
    name: null,
    role: "UNKNOWN",
    role_display: "Роль не определена",
    role_reason: null,
    okved_main: null,
    okved_name: null,
    okved_extra: [],
    region_code: null,
    is_spb_lo: null,
    msp_category: null,
    headcount: null,
    msp_since: null,
    n_bids: 0,
    n_wins: 0,
    win_rate: null,
    avg_won_price: null,
    n_customers: 0,
    top_okpd2: [],
    recent_lots: [],
    trust: null,
  };
  fetchSpy.mockResolvedValue(Response.json(result));
  expect(await getSupplierEnrichment(result.inn)).toEqual(result);
  expect(new URL(fetchSpy.mock.calls[0][0].url).pathname).toBe("/api/v1/enrichment/7802587594");
});

test("enrichment preserves FNS data, zero values and warnings", async () => {
  const result = {
    inn: "7802587594",
    trust: {
      status: "ACTIVE",
      registered: "2020-01-15",
      revenue: 1000000,
      expenses: null,
      taxes_paid: 0,
      tax_debt: 100000,
      headcount: 0,
      warnings: ["Налоговая задолженность 100 000 ₽"],
    },
  };
  fetchSpy.mockResolvedValue(Response.json(result));
  expect(await getSupplierEnrichment(result.inn)).toEqual(result);
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
