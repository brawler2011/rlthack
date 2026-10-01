import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  ArrowRight,
  Check,
  ChevronDown,
  FileText,
  LoaderCircle,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { searchLots } from "../services/api";
import { errorMessage, money, roles } from "../utils/format";
import type { LotItem } from "../types";
import { emptyFilters } from "../utils/filters";
import type { Filters } from "../utils/filters";

interface Props {
  filters: Filters;
  onFiltersChange: (filters: Filters) => void;
  onSearch: (lot: LotItem) => void;
  onDraftChange: () => void;
  onCancel: () => void;
  loading: boolean;
}

function LotPicker({ onSelect }: { onSelect: (lot: LotItem | null) => void }) {
  const [query, setQuery] = useState("");
  const [lots, setLots] = useState<LotItem[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);

  async function findLots(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    setStatus("loading");
    setSelected(null);
    onSelect(null);
    try {
      const response = await searchLots(query.trim(), current.signal);
      if (current.signal.aborted) return;
      setLots(response);
      setStatus("success");
    } catch (err) {
      if (current.signal.aborted) return;
      setError(errorMessage(err));
      setStatus("error");
    }
  }

  return (
    <div className="lot-picker">
      <form onSubmit={findLots}>
        <label className="field-label" htmlFor="notice-query">
          Найдите извещение
        </label>
        <div className="notice-search">
          <Search size={17} aria-hidden="true" />
          <input
            id="notice-query"
            type="search"
            placeholder="Предмет закупки или код ОКПД2"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            maxLength={300}
          />
          <button
            className="icon-button"
            type="submit"
            aria-label="Найти извещения"
            disabled={status === "loading"}
          >
            {status === "loading" ? (
              <LoaderCircle size={17} className="spin" />
            ) : (
              <ArrowRight size={17} />
            )}
          </button>
        </div>
        <p className="field-hint">Можно оставить поле пустым, чтобы увидеть доступные закупки.</p>
      </form>
      <div className="notice-list" aria-live="polite" aria-busy={status === "loading"}>
        {status === "idle" && (
          <p className="notice-message">
            <FileText size={22} />
            Найдите закупку, чтобы использовать её параметры.
          </p>
        )}
        {status === "loading" && (
          <p className="notice-message">
            <LoaderCircle size={22} className="spin" />
            Ищем извещения…
          </p>
        )}
        {status === "error" && (
          <p className="inline-error" role="alert">
            {error}
          </p>
        )}
        {status === "success" && lots.length === 0 && (
          <p className="notice-message">
            <Search size={22} />
            Извещений не найдено. Измените запрос или создайте новую закупку.
          </p>
        )}
        {status === "success" &&
          lots.map((lot, index) => (
            <button
              key={lot.lot_id ?? index}
              type="button"
              className={`notice-option ${selected === index ? "selected" : ""}`}
              aria-pressed={selected === index}
              onClick={() => {
                setSelected(index);
                onSelect(lot);
              }}
            >
              <span className="notice-option-top">
                <span>{lot.lot_id ? `№ ${lot.lot_id}` : lot.procedure_name}</span>
                <span className="selection-circle">
                  {selected === index && <Check size={12} />}
                </span>
              </span>
              <strong>{lot.subject}</strong>
              <span className="notice-option-meta">
                {money(lot.start_price)}
                <span>ОКПД2 {lot.okpd2_code || "не указан"}</span>
              </span>
            </button>
          ))}
      </div>
    </div>
  );
}

export default function ProcurementForm({
  filters,
  onFiltersChange,
  onSearch,
  onDraftChange,
  onCancel,
  loading,
}: Props) {
  const [mode, setMode] = useState<"manual" | "notice">("manual");
  const [subject, setSubject] = useState("");
  const [code, setCode] = useState("");
  const [price, setPrice] = useState("");
  const [smp, setSmp] = useState(false);
  const [notice, setNotice] = useState<LotItem | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const activeFilters =
    filters.roles.length +
    Number(filters.onlySpb) +
    Number(filters.onlySmp) +
    Number(filters.minWinRate > 0);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading) return;
    if (mode === "notice") {
      if (notice) onSearch(notice);
      return;
    }
    const field = event.currentTarget.elements.namedItem("subject") as HTMLTextAreaElement;
    if (!subject.trim()) {
      field.setCustomValidity("Укажите предмет закупки.");
      field.reportValidity();
      return;
    }
    onSearch({
      procedure_name: "Ручной подбор",
      subject: subject.trim(),
      start_price: Number(price),
      okpd2_code: code.trim(),
      is_smp: smp,
    });
  }

  return (
    <section className="procurement-panel" aria-labelledby="procurement-heading">
      <div className="panel-heading">
        <span className="section-index">01</span>
        <h2 id="procurement-heading">Параметры закупки</h2>
      </div>
      <div className="mode-switch" role="group" aria-label="Способ выбора закупки">
        <button
          type="button"
          aria-pressed={mode === "manual"}
          className={mode === "manual" ? "active" : ""}
          disabled={loading}
          onClick={() => {
            if (mode !== "manual") {
              setMode("manual");
              setNotice(null);
              onDraftChange();
            }
          }}
        >
          Новая закупка
        </button>
        <button
          type="button"
          aria-pressed={mode === "notice"}
          className={mode === "notice" ? "active" : ""}
          disabled={loading}
          onClick={() => {
            if (mode !== "notice") {
              setMode("notice");
              setNotice(null);
              onDraftChange();
            }
          }}
        >
          Извещение из базы
        </button>
      </div>

      {mode === "notice" && (
        <fieldset className="plain-fieldset" disabled={loading}>
          <LotPicker
            onSelect={(lot) => {
              setNotice(lot);
              onDraftChange();
            }}
          />
        </fieldset>
      )}

      <form onSubmit={submit}>
        <fieldset className="plain-fieldset" disabled={loading}>
          {mode === "manual" ? (
            <div className="manual-fields">
              <div className="field">
                <label className="field-label" htmlFor="subject">
                  Что нужно закупить <span className="required-mark">*</span>
                </label>
                <textarea
                  id="subject"
                  name="subject"
                  placeholder="Например, поставка ноутбуков для образовательного учреждения"
                  rows={4}
                  required
                  maxLength={2000}
                  value={subject}
                  onChange={(event) => {
                    event.target.setCustomValidity("");
                    setSubject(event.target.value);
                    onDraftChange();
                  }}
                />
              </div>
              <div className="field">
                <label className="field-label" htmlFor="okpd2">
                  Код ОКПД2 <span className="required-mark">*</span>
                </label>
                <input
                  id="okpd2"
                  type="text"
                  inputMode="decimal"
                  placeholder="26.20.11.110"
                  required
                  pattern="[0-9]{2}(\.[0-9]{1,3}){0,4}"
                  title="Код из цифр, разделённых точками, например 26.20.11.110"
                  maxLength={20}
                  value={code}
                  onChange={(event) => {
                    setCode(event.target.value);
                    onDraftChange();
                  }}
                />
                <p className="field-hint">Помогает найти компании с подходящим опытом.</p>
              </div>
              <div className="field">
                <label className="field-label" htmlFor="price">
                  Начальная цена <span className="required-mark">*</span>
                </label>
                <div className="price-input">
                  <input
                    id="price"
                    type="number"
                    placeholder="0"
                    min="0"
                    step="0.01"
                    required
                    value={price}
                    onChange={(event) => {
                      setPrice(event.target.value);
                      onDraftChange();
                    }}
                  />
                  <span aria-hidden="true">₽</span>
                </div>
              </div>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={smp}
                  onChange={(event) => {
                    setSmp(event.target.checked);
                    onDraftChange();
                  }}
                />
                <span>Закупка для субъектов МСП</span>
              </label>
            </div>
          ) : (
            notice && (
              <div className="selected-notice">
                <span className="eyebrow">Выбранная закупка</span>
                <strong>{notice.subject}</strong>
                <div>
                  {money(notice.start_price)}
                  <span>ОКПД2 {notice.okpd2_code || "не указан"}</span>
                </div>
              </div>
            )
          )}

          <div className="filters-section">
            <button
              className="filters-toggle"
              type="button"
              aria-expanded={filtersOpen}
              aria-controls="supplier-filters"
              onClick={() => setFiltersOpen(!filtersOpen)}
            >
              <SlidersHorizontal size={16} />
              <span>Фильтры контрагентов</span>
              {activeFilters > 0 && <span className="filter-count">{activeFilters}</span>}
              <ChevronDown size={16} className={filtersOpen ? "rotated" : ""} />
            </button>
            {filtersOpen && (
              <div id="supplier-filters" className="filters-content">
                <fieldset className="role-filter">
                  <legend className="field-label">Роль компании</legend>
                  <p className="field-hint">Без выбора — все роли</p>
                  <div className="role-options">
                    {roles.map((role) => (
                      <button
                        key={role.value}
                        type="button"
                        aria-pressed={filters.roles.includes(role.value)}
                        className={filters.roles.includes(role.value) ? "selected" : ""}
                        onClick={() =>
                          onFiltersChange({
                            ...filters,
                            roles: filters.roles.includes(role.value)
                              ? filters.roles.filter((value) => value !== role.value)
                              : [...filters.roles, role.value],
                          })
                        }
                      >
                        {role.label}
                        {filters.roles.includes(role.value) && <Check size={12} />}
                      </button>
                    ))}
                  </div>
                </fieldset>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={filters.onlySpb}
                    onChange={(event) =>
                      onFiltersChange({ ...filters, onlySpb: event.target.checked })
                    }
                  />
                  <span>Санкт-Петербург и Ленобласть</span>
                </label>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={filters.onlySmp}
                    onChange={(event) =>
                      onFiltersChange({ ...filters, onlySmp: event.target.checked })
                    }
                  />
                  <span>Только субъекты МСП</span>
                </label>
                <div className="range-field">
                  <label className="field-label" htmlFor="win-rate">
                    Доля побед в закупках <span>от {filters.minWinRate}%</span>
                  </label>
                  <input
                    id="win-rate"
                    type="range"
                    min="0"
                    max="100"
                    step="5"
                    value={filters.minWinRate}
                    onChange={(event) =>
                      onFiltersChange({ ...filters, minWinRate: Number(event.target.value) })
                    }
                  />
                  <div className="range-labels">
                    <span>0%</span>
                    <span>100%</span>
                  </div>
                </div>
                {activeFilters > 0 && (
                  <button
                    className="text-button reset-filters"
                    type="button"
                    onClick={() => onFiltersChange({ ...emptyFilters })}
                  >
                    <X size={13} />
                    Сбросить фильтры
                  </button>
                )}
              </div>
            )}
          </div>
        </fieldset>

        <div className="search-action">
          {loading ? (
            <button
              className="primary-button searching-button"
              type="button"
              onClick={(event) => {
                event.preventDefault();
                onCancel();
              }}
            >
              <LoaderCircle size={17} className="spin" />
              <span>Отменить подбор</span>
              <X size={16} />
            </button>
          ) : (
            <button
              className="primary-button"
              type="submit"
              disabled={mode === "notice" && !notice}
            >
              <span>Найти контрагентов</span>
              <ArrowRight size={17} />
            </button>
          )}
        </div>
      </form>
    </section>
  );
}
