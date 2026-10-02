import {
  ArrowDownRight,
  ArrowUpRight,
  Building2,
  Check,
  ChevronRight,
  Clock3,
  FileText,
  Search,
  TriangleAlert,
} from "lucide-react";
import { money, number, percent, roleNames } from "../utils/format";
import type {
  Procurement,
  SearchSuppliersResponse,
  SupplierItem,
  SelectedSupplier,
} from "../types";
import NewCompanies from "./NewCompanies";
import ReliabilityWarnings from "./ReliabilityWarnings";
import ProfileFitDetails from "./ProfileFitDetails";
import type { Filters } from "../utils/filters";

export type SearchState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; response: SearchSuppliersResponse; lot: Procurement; filters: Filters };

interface Props {
  state: SearchState;
  dirty: boolean;
  onSelect: (supplier: SelectedSupplier) => void;
}

function MatchingIllustration() {
  return (
    <div className="matching-illustration" aria-hidden="true">
      <div className="illustration-orbit orbit-one" />
      <div className="illustration-orbit orbit-two" />
      <svg className="illustration-lines" viewBox="0 0 360 208">
        <path d="M180 104 68 61M180 104 290 60M180 104 263 165" />
        <circle cx="180" cy="104" r="3" />
      </svg>
      <div className="illustration-center">
        <FileText size={28} strokeWidth={1.5} />
        <span className="illustration-center-dot" />
      </div>
      <div className="illustration-company company-one">
        <Building2 size={19} strokeWidth={1.5} />
        <span>
          <i />
          <i />
        </span>
        <Check size={12} />
      </div>
      <div className="illustration-company company-two">
        <Building2 size={19} strokeWidth={1.5} />
        <span>
          <i />
          <i />
        </span>
      </div>
      <div className="illustration-company company-three">
        <Building2 size={19} strokeWidth={1.5} />
        <span>
          <i />
          <i />
        </span>
        <Check size={12} />
      </div>
    </div>
  );
}

export function SupplierRow({
  supplier,
  index,
  onSelect,
}: {
  supplier: SupplierItem;
  index: number;
  onSelect: () => void;
}) {
  const summary = supplier.explanation?.summary;
  return (
    <button
      type="button"
      className="supplier-row"
      onClick={onSelect}
      aria-label={`Открыть карточку ${supplier.name || `ИНН ${supplier.inn}`}`}
    >
      <span className="supplier-rank">{String(index + 1).padStart(2, "0")}</span>
      <div className="supplier-info">
        <div className="supplier-name-line">
          <h3>{supplier.name || `Компания · ИНН ${supplier.inn}`}</h3>
          <ArrowUpRight size={17} />
        </div>
        <div className="supplier-meta">
          <span>ИНН {supplier.inn}</span>
          <span className={`role-badge role-${supplier.role.toLowerCase()}`}>
            {supplier.role_display || roleNames[supplier.role]}
          </span>
          {supplier.is_smp && <span className="small-badge">МСП</span>}
          {supplier.is_spb_lo && <span className="small-badge">СПб / ЛО</span>}
          {supplier.is_actual_winner && <span className="winner-badge">Реальный победитель</span>}
        </div>
        <div className="supplier-stats">
          <span>
            <strong>{number(supplier.n_wins)}</strong> контрактов
          </span>
          <span>
            <strong>{percent(supplier.win_rate)}</strong> побед
          </span>
          <span>
            Средний контракт <strong>{money(supplier.avg_won_price)}</strong>
          </span>
        </div>
        {summary && (
          <p className="supplier-explanation">
            <span className="explanation-dot" />
            {summary}
          </p>
        )}
        <ProfileFitDetails fit={supplier.profile_fit} compact />
        <ReliabilityWarnings warnings={supplier.warnings} />
      </div>
      <div className="supplier-score">
        <strong>{number(supplier.score, 3)}</strong>
        <span>балл подбора</span>
        <span className="details-link">
          Подробнее <ChevronRight size={13} />
        </span>
      </div>
    </button>
  );
}

export default function ResultsPanel({ state, dirty, onSelect }: Props) {
  const found =
    state.status === "success" &&
    (state.response.items.length > 0 || state.response.new_suppliers.length > 0);
  return (
    <section
      id="results-panel"
      className={`results-panel ${found ? "has-results" : ""}`}
      aria-labelledby="results-heading"
      aria-busy={state.status === "loading"}
    >
      <div className="results-heading">
        <div className="panel-heading">
          <span className="section-index">02</span>
          <h2 id="results-heading">Результаты подбора</h2>
          {found && <span className="result-count">{number(state.response.total_candidates)}</span>}
        </div>
        <span className="results-caption">По релевантности</span>
      </div>
      <div className="results-content" aria-live="polite">
        {state.status === "idle" && (
          <div className="empty-state initial-state">
            <MatchingIllustration />
            <span className="eyebrow">От закупки к контрагенту</span>
            <h3>
              Подходящие компании
              <br />
              начинаются с вашего запроса
            </h3>
            <p>
              Задайте параметры закупки или выберите
              <br className="desktop-break" /> извещение. Мы покажем релевантных
              <br className="desktop-break" /> контрагентов и объясним результат.
            </p>
          </div>
        )}
        {state.status === "loading" && (
          <div className="loading-results" role="status">
            <div className="loading-label">
              <span className="loading-dot" />
              Подбираем подходящие компании…
            </div>
            {[0, 1, 2].map((value) => (
              <div className="skeleton-row" key={value}>
                <span className="skeleton skeleton-rank" />
                <div>
                  <span className="skeleton skeleton-title" />
                  <span className="skeleton skeleton-meta" />
                  <span className="skeleton skeleton-text" />
                </div>
                <span className="skeleton skeleton-score" />
              </div>
            ))}
            <p>Ищем контрагентов и формируем объяснения.</p>
          </div>
        )}
        {state.status === "error" && (
          <div className="empty-state error-state">
            <div className="state-icon">
              <TriangleAlert size={26} strokeWidth={1.5} />
            </div>
            <h3>Подбор не завершён</h3>
            <p role="alert">{state.message}</p>
            <span className="state-footnote">
              Параметры сохранены. Нажмите «Найти контрагентов», чтобы повторить.
            </span>
          </div>
        )}
        {state.status === "success" && (
          <>
            <div className="search-context">
              <FileText size={15} />
              <div>
                <span>{state.response.lot.subject}</span>
                <p>
                  ОКПД2 {state.response.lot.okpd2_codes.join(", ") || "не указан"}
                  <span>·</span>
                  {money(state.response.lot.start_price)}
                </p>
              </div>
              <span className="inference-time">
                <Clock3 size={12} />
                {number(state.response.timing_ms, 1)} мс
              </span>
            </div>
            {(state.filters.roles.length > 0 ||
              state.filters.onlySpb ||
              state.filters.onlySmp ||
              state.filters.onlyReliable ||
              state.filters.minWinRate > 0) && (
              <div className="applied-filters">
                {state.filters.roles.map((role) => (
                  <span key={role}>{roleNames[role]}</span>
                ))}
                {state.filters.onlySpb && <span>СПб и Ленобласть</span>}
                {state.filters.onlySmp && <span>МСП</span>}
                {state.filters.onlyReliable && <span>Только надёжные компании</span>}
                {state.filters.minWinRate > 0 && <span>Победы от {state.filters.minWinRate}%</span>}
              </div>
            )}
            {dirty && (
              <div className="dirty-notice">
                <ArrowDownRight size={15} />
                Параметры изменены. Запустите подбор заново.
              </div>
            )}
            {state.response.items.length === 0 ? (
              <div className="empty-state no-results">
                <div className="state-icon">
                  <Search size={27} strokeWidth={1.5} />
                </div>
                <h3>Пока нет подходящих компаний</h3>
                <p>
                  По этим параметрам сервис не вернул контрагентов.
                  <br />
                  Попробуйте уточнить закупку или ослабить фильтры.
                </p>
              </div>
            ) : (
              <>
                <div className="supplier-list">
                  {state.response.items.map((supplier, index) => (
                    <SupplierRow
                      key={supplier.inn}
                      supplier={supplier}
                      index={index}
                      onSelect={() => onSelect(supplier)}
                    />
                  ))}
                </div>
                <div className="results-footer">
                  <span>
                    Показано {number(state.response.items.length)} из{" "}
                    {number(state.response.total_candidates)}
                  </span>
                </div>
              </>
            )}
            <NewCompanies suppliers={state.response.new_suppliers} onSelect={onSelect} />
          </>
        )}
      </div>
    </section>
  );
}
