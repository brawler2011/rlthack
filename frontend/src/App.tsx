import { useEffect, useRef, useState } from "react";
import { ArrowRight, MapPin } from "lucide-react";
import ProcurementForm from "./components/ProcurementForm";
import { emptyFilters } from "./utils/filters";
import type { Filters } from "./utils/filters";
import ResultsPanel from "./components/ResultsPanel";
import type { SearchState } from "./components/ResultsPanel";
import SupplierDialog from "./components/SupplierDialog";
import { searchSuppliers } from "./services/api";
import { errorMessage } from "./utils/format";
import type { Procurement, SupplierItem } from "./types";
import { toSearchLot } from "./utils/lot";

export default function App() {
  const [filters, setFilters] = useState<Filters>({ ...emptyFilters });
  const [state, setState] = useState<SearchState>({ status: "idle" });
  const [dirty, setDirty] = useState(false);
  const [selected, setSelected] = useState<SupplierItem | null>(null);
  const controller = useRef<AbortController | null>(null);
  const phase = state.status === "loading" ? 2 : state.status === "success" && !dirty ? 3 : 1;

  useEffect(() => () => controller.current?.abort(), []);

  useEffect(() => {
    if (state.status === "success" && window.matchMedia("(max-width: 760px)").matches) {
      document.getElementById("results-panel")?.scrollIntoView({ block: "start" });
    }
  }, [state.status]);

  async function search(lot: Procurement) {
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    setState({ status: "loading" });
    setDirty(false);
    try {
      const response = await searchSuppliers(
        {
          ...toSearchLot(lot),
          filters: {
            roles: filters.roles,
            only_spb_lo: filters.onlySpb,
            only_smp: filters.onlySmp,
            min_win_rate: filters.minWinRate / 100,
          },
          limit: 20,
          new_limit: 10,
        },
        current.signal
      );
      if (!current.signal.aborted) setState({ status: "success", response, lot, filters });
    } catch (error) {
      if (!current.signal.aborted) setState({ status: "error", message: errorMessage(error) });
    }
  }

  function draftChanged() {
    if (state.status === "success") setDirty(true);
  }

  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">
        Перейти к подбору
      </a>
      <header className="site-header">
        <div className="header-inner">
          <div className="brand">
            <img src="/favicon.svg" width="35" height="35" alt="" />
            <span>
              росэлторг<span className="brand-caption">Сервис подбора контрагентов</span>
            </span>
          </div>
          <div className="header-location">
            <span className="ais-label">АИС ГЗ</span>
            <span className="header-divider" />
            <span>
              <MapPin size={14} />
              Санкт-Петербург
            </span>
          </div>
        </div>
      </header>
      <main id="main" className="main-content">
        <div className="intro">
          <div>
            <h1>
              Подбор поставщиков<span className="heading-period">.</span>
            </h1>
            <p>Найдите подходящих контрагентов. Узнайте, почему они подходят.</p>
          </div>
          <div className="process-steps" aria-label="Этапы подбора">
            <span
              className={phase === 1 ? "current" : ""}
              aria-current={phase === 1 ? "step" : undefined}
            >
              <i>01</i>Закупка
            </span>
            <ArrowRight size={13} />
            <span
              className={phase === 2 ? "current" : ""}
              aria-current={phase === 2 ? "step" : undefined}
            >
              <i>02</i>Подбор
            </span>
            <ArrowRight size={13} />
            <span
              className={phase === 3 ? "current" : ""}
              aria-current={phase === 3 ? "step" : undefined}
            >
              <i>03</i>Выбор
            </span>
          </div>
        </div>
        <div className="workspace">
          <ProcurementForm
            filters={filters}
            onFiltersChange={(next) => {
              setFilters(next);
              draftChanged();
            }}
            onSearch={search}
            onDraftChange={draftChanged}
            onCancel={() => {
              controller.current?.abort();
              setState({ status: "idle" });
            }}
            loading={state.status === "loading"}
          />
          <ResultsPanel state={state} dirty={dirty} onSelect={setSelected} />
        </div>
      </main>
      {selected && (
        <SupplierDialog key={selected.inn} supplier={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
