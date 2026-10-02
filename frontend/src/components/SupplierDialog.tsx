import { useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUp, Building2, LoaderCircle, MapPin, ShieldCheck, X } from "lucide-react";
import { getSupplierEnrichment } from "../services/api";
import { errorMessage, money, number, percent, roleNames } from "../utils/format";
import type { SupplierEnrichment, SupplierItem } from "../types";

interface Props {
  supplier: SupplierItem;
  onClose: () => void;
}

type EnrichmentState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; data: SupplierEnrichment };

const factorNames: Record<string, string> = {
  win_rate: "Доля побед",
  win_rate_smoothed: "Доля побед с учётом объёма истории",
  contracts_count: "Опыт исполнения контрактов",
  n_wins: "Количество побед",
  n_bids: "Участие в закупках",
  is_spb_lo: "Близость к заказчику",
  is_smp: "Статус МСП",
  avg_contract_price: "Средняя стоимость контракта",
  avg_won_price: "Средняя стоимость выигранных закупок",
  semantic_similarity: "Соответствие предмету закупки",
  okpd2_match: "Опыт по коду ОКПД2",
};

export default function SupplierDialog({ supplier, onClose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [enrichment, setEnrichment] = useState<EnrichmentState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const factors = supplier.explanation?.factors ?? [];
  const maxImpact = Math.max(...factors.map((factor) => Math.abs(factor.impact)), 0.001);

  useEffect(() => {
    const element = dialog.current;
    const overflow = document.body.style.overflow;
    const previousFocus =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    element?.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      element?.close();
      document.body.style.overflow = overflow;
      previousFocus?.focus({ preventScroll: true });
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    getSupplierEnrichment(supplier.inn, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setEnrichment({ status: "success", data });
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setEnrichment({ status: "error", message: errorMessage(error) });
      });
    return () => controller.abort();
  }, [supplier.inn, attempt]);

  return (
    <dialog
      ref={dialog}
      className="supplier-dialog"
      aria-labelledby="supplier-dialog-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        const bounds = event.currentTarget.getBoundingClientRect();
        if (
          event.clientX < bounds.left ||
          event.clientX > bounds.right ||
          event.clientY < bounds.top ||
          event.clientY > bounds.bottom
        )
          onClose();
      }}
    >
      <div className="dialog-top">
        <span className="eyebrow">Карточка контрагента</span>
        <button
          type="button"
          className="icon-button close-dialog"
          aria-label="Закрыть карточку"
          onClick={onClose}
          autoFocus
        >
          <X size={20} />
        </button>
      </div>
      <div className="dialog-body">
        <div className="company-icon">
          <Building2 size={28} strokeWidth={1.5} />
        </div>
        <h2 id="supplier-dialog-title">{supplier.name || "Наименование не указано"}</h2>
        <p className="company-identifiers">ИНН {supplier.inn}</p>
        <div className="company-badges">
          <span className={`role-badge role-${supplier.role.toLowerCase()}`}>
            {supplier.role_display || roleNames[supplier.role]}
          </span>
          {supplier.is_smp && <span className="small-badge">Субъект МСП</span>}
          {supplier.is_spb_lo && (
            <span className="location-badge">
              <MapPin size={12} />
              СПб / Ленобласть
            </span>
          )}
        </div>
        <dl className="company-metrics">
          <div>
            <dt>Контрактов</dt>
            <dd>{number(supplier.n_wins)}</dd>
          </div>
          <div>
            <dt>Доля побед</dt>
            <dd>{percent(supplier.win_rate)}</dd>
          </div>
          <div>
            <dt>Балл подбора</dt>
            <dd className="accent-text">{number(supplier.score, 3)}</dd>
          </div>
        </dl>
        <div className="average-contract">
          <span>Средняя стоимость контракта</span>
          <strong>{money(supplier.avg_won_price)}</strong>
        </div>

        <section className="dialog-section" aria-labelledby="explanation-heading">
          <div className="dialog-section-heading">
            <h3 id="explanation-heading">Почему рекомендован</h3>
            <span className="explanation-dot" />
          </div>
          {supplier.explanation?.summary ? (
            <p className="xai-summary">{supplier.explanation.summary}</p>
          ) : (
            <p className="data-unavailable">Сервис пока не предоставил объяснение рекомендации.</p>
          )}
          {factors.length > 0 && (
            <div className="xai-factors">
              <div className="factor-legend">
                <span>Влияние на результат</span>
                <span>
                  <i />
                  Повышает
                  <span className="negative-key">
                    <i />
                    Снижает
                  </span>
                </span>
              </div>
              {factors.map((factor, index) => (
                <div className="xai-factor" key={`${factor.name}-${index}`}>
                  <div className="factor-label">
                    <strong>{factorNames[factor.name] || factor.name}</strong>
                    <span
                      className={
                        factor.impact > 0
                          ? "positive-impact"
                          : factor.impact < 0
                            ? "negative-impact"
                            : ""
                      }
                    >
                      {factor.impact > 0 ? (
                        <ArrowUp size={12} />
                      ) : factor.impact < 0 ? (
                        <ArrowDown size={12} />
                      ) : null}
                      {factor.impact > 0 ? "+" : ""}
                      {number(factor.impact, 3)}
                    </span>
                  </div>
                  <div className="factor-track" aria-hidden="true">
                    <span
                      className={factor.impact < 0 ? "negative" : ""}
                      style={{ width: `${(Math.abs(factor.impact) / maxImpact) * 100}%` }}
                    />
                  </div>
                  {factor.text && <p>{factor.text}</p>}
                </div>
              ))}
              <p className="factor-footnote">
                Вклад факторов в балл подбора, а не вероятность победы.
              </p>
            </div>
          )}
        </section>

        <section
          className="dialog-section"
          aria-labelledby="enrichment-heading"
          aria-busy={enrichment.status === "loading"}
        >
          <div className="dialog-section-heading">
            <h3 id="enrichment-heading">Сведения о компании</h3>
            <ShieldCheck size={17} />
          </div>
          <div aria-live="polite">
            {enrichment.status === "loading" && (
              <p className="enrichment-loading">
                <LoaderCircle size={16} className="spin" />
                Загружаем данные обогащения…
              </p>
            )}
            {enrichment.status === "error" && (
              <div className="enrichment-error">
                <p role="alert">{enrichment.message}</p>
                <button
                  className="text-button"
                  type="button"
                  onClick={() => {
                    setEnrichment({ status: "loading" });
                    setAttempt((value) => value + 1);
                  }}
                >
                  Повторить запрос
                </button>
              </div>
            )}
            {enrichment.status === "success" && (
              <>
                <dl className="enrichment-list">
                  <div>
                    <dt>Категория МСП</dt>
                    <dd>
                      {enrichment.data.msp_category === null
                        ? "Нет данных"
                        : (
                            {
                              1: "Микропредприятие",
                              2: "Малое предприятие",
                              3: "Среднее предприятие",
                            } as Record<number, string>
                          )[enrichment.data.msp_category] || "Нет данных"}
                    </dd>
                  </div>
                  <div>
                    <dt>Основной ОКВЭД</dt>
                    <dd>{enrichment.data.okved_main || "Нет данных"}</dd>
                  </div>
                  <div>
                    <dt>Роль по данным обогащения</dt>
                    <dd>{enrichment.data.role ? roleNames[enrichment.data.role] : "Нет данных"}</dd>
                  </div>
                  <div>
                    <dt>Численность сотрудников</dt>
                    <dd>
                      {enrichment.data.headcount === null
                        ? "Нет данных"
                        : number(enrichment.data.headcount)}
                    </dd>
                  </div>
                </dl>
                <p className="factor-footnote">
                  {enrichment.data.role_reason || "Роль компании определена по данным реестра МСП."}
                </p>
              </>
            )}
          </div>
        </section>
      </div>
    </dialog>
  );
}
