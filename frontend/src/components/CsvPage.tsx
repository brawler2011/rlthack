import { useEffect, useRef, useState } from "react";
import { ChevronDown, FileSpreadsheet, LoaderCircle, Upload } from "lucide-react";
import { matchCsvBatch } from "../services/api";
import type { CsvBatchResponse, SelectedSupplier } from "../types";
import { errorMessage, money, number } from "../utils/format";
import NewCompanies from "./NewCompanies";
import { SupplierRow } from "./ResultsPanel";
import SupplierDialog from "./SupplierDialog";

type BatchState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; response: CsvBatchResponse };

export default function CsvPage() {
  const [notices, setNotices] = useState<File | null>(null);
  const [items, setItems] = useState<File | null>(null);
  const [state, setState] = useState<BatchState>({ status: "idle" });
  const [selected, setSelected] = useState<{
    supplier: SelectedSupplier;
    lotId: number | null;
  } | null>(null);
  const controller = useRef<AbortController | null>(null);
  const resultRef = useRef<HTMLElement>(null);
  const loading = state.status === "loading";
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    if (state.status === "success") resultRef.current?.scrollIntoView({ block: "start" });
  }, [state.status]);

  function changeFile(file: File | null, kind: "notices" | "items") {
    if (kind === "notices") setNotices(file);
    else setItems(file);
    setSelected(null);
    if (
      file &&
      (!file.name.toLowerCase().endsWith(".csv") || file.size > 2 * 1024 * 1024 || file.size === 0)
    ) {
      setState({ status: "error", message: "Выберите непустой CSV-файл размером до 2 МБ." });
    } else setState({ status: "idle" });
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!notices || !items || loading) return;
    if (
      [notices, items].some(
        (file) =>
          !file.name.toLowerCase().endsWith(".csv") || file.size > 2 * 1024 * 1024 || !file.size
      )
    ) {
      setState({
        status: "error",
        message: "Оба файла должны быть непустыми CSV размером до 2 МБ каждый.",
      });
      return;
    }
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    setSelected(null);
    setState({ status: "loading" });
    try {
      const response = await matchCsvBatch(notices, items, current.signal);
      if (!current.signal.aborted) setState({ status: "success", response });
    } catch (error) {
      if (!current.signal.aborted) setState({ status: "error", message: errorMessage(error) });
    }
  }

  return (
    <main id="main" className="scenario-page csv-page" aria-label="Подбор по CSV">
      <form className="upload-panel" onSubmit={submit} aria-busy={loading}>
        <div className="upload-grid">
          {(
            [
              {
                kind: "notices",
                title: "Извещения",
                description: "Предмет закупки, НМЦК и заказчик",
                file: notices,
              },
              {
                kind: "items",
                title: "Потоварка",
                description: "Товарные позиции и коды ОКПД2",
                file: items,
              },
            ] as const
          ).map((entry, index) => (
            <label className={`upload-field ${entry.file ? "file-selected" : ""}`} key={entry.kind}>
              <span className="upload-step">0{index + 1}</span>
              <FileSpreadsheet size={28} />
              <strong>{entry.title}</strong>
              <span>{entry.description}</span>
              <input
                className="sr-only"
                type="file"
                accept=".csv,text/csv"
                disabled={loading}
                onChange={(event) => changeFile(event.target.files?.[0] ?? null, entry.kind)}
              />
              <span className="file-picker">
                <Upload size={15} />
                {entry.file ? "Заменить файл" : "Выбрать файл"}
              </span>
              <span className="file-caption">
                {entry.file
                  ? `${entry.file.name} · ${number(entry.file.size / 1024, 1)} КБ`
                  : "Выберите CSV-файл"}
              </span>
            </label>
          ))}
        </div>
        <div className="upload-actions">
          <button type="submit" className="primary-button" disabled={!notices || !items || loading}>
            {loading ? <LoaderCircle className="spin" size={18} /> : <Upload size={18} />}
            {loading ? "Подбираем поставщиков…" : "Подобрать поставщиков"}
          </button>
          {loading && (
            <button
              type="button"
              className="text-button"
              onClick={() => {
                controller.current?.abort();
                setState({ status: "idle" });
              }}
            >
              Отменить
            </button>
          )}
        </div>
        {loading && (
          <p className="batch-status" role="status">
            Проверяем оба файла и готовим рекомендации для всех закупок. Обработка может занять
            несколько минут.
          </p>
        )}
        {state.status === "error" && (
          <p className="inline-error" role="alert">
            {state.message}
          </p>
        )}
      </form>
      {state.status === "success" && (
        <section className="batch-results" ref={resultRef} aria-labelledby="batch-heading">
          <div className="batch-heading">
            <h2 id="batch-heading">Результаты подбора</h2>
            <span>{number(state.response.timing_ms / 1000, 1)} с</span>
          </div>
          <div className="batch-metrics">
            <span>
              <strong>{number(state.response.total_lots)}</strong> закупок
            </span>
            <span>
              <strong>{number(state.response.total_items)}</strong> товарных позиций
            </span>
            <span>
              <strong>{number(state.response.total_recommendations)}</strong> рекомендаций
            </span>
          </div>
          <div className="lot-card-list">
            {state.response.lots.map((result) => (
              <details className="lot-result-card" key={result.lot.lot_id}>
                <summary>
                  <span className="lot-card-main">
                    <span className="eyebrow">Закупка № {result.lot.lot_id}</span>
                    <strong>{result.lot.subject}</strong>
                    <span className="lot-card-meta">
                      НМЦК {money(result.lot.start_price)} · Позиций:{" "}
                      {number(result.lot.items.length)}
                    </span>
                    <span className="lot-supplier-preview">
                      {result.items
                        .slice(0, 3)
                        .map((supplier) => supplier.name || `ИНН ${supplier.inn}`)
                        .join(" · ") || "Поставщики с историей не найдены"}
                    </span>
                  </span>
                  <span className="lot-card-count">
                    <strong>{result.items.length + result.new_suppliers.length}</strong>
                    <span>поставщиков</span>
                    <ChevronDown size={20} />
                  </span>
                </summary>
                <div className="lot-detail">
                  <dl className="lot-facts">
                    <div>
                      <dt>Заказчик · ИНН</dt>
                      <dd>{result.lot.customer_inn || "Не указан"}</dd>
                    </div>
                    <div>
                      <dt>ОКПД2</dt>
                      <dd>{result.lot.okpd2_codes.join(", ")}</dd>
                    </div>
                  </dl>
                  <details className="product-details">
                    <summary>Товарные позиции · {result.lot.items.length}</summary>
                    <ul>
                      {result.lot.items.map((item, index) => (
                        <li key={index}>{item}</li>
                      ))}
                    </ul>
                  </details>
                  <h3 className="known-heading">Поставщики с историей участия</h3>
                  {result.items.length === 0 ? (
                    <p className="data-unavailable">Подходящие поставщики с историей не найдены.</p>
                  ) : (
                    <div className="supplier-list">
                      {result.items.map((supplier, index) => (
                        <SupplierRow
                          key={supplier.inn}
                          supplier={supplier}
                          index={index}
                          onSelect={() => setSelected({ supplier, lotId: result.lot.lot_id })}
                        />
                      ))}
                    </div>
                  )}
                  <NewCompanies
                    suppliers={result.new_suppliers}
                    onSelect={(supplier) => setSelected({ supplier, lotId: result.lot.lot_id })}
                  />
                </div>
              </details>
            ))}
          </div>
        </section>
      )}
      {selected && state.status === "success" && (
        <SupplierDialog
          key={`${selected.lotId}-${selected.supplier.inn}`}
          supplier={selected.supplier}
          details={state.response.supplier_cards[selected.supplier.inn] ?? null}
          onClose={() => setSelected(null)}
        />
      )}
    </main>
  );
}
