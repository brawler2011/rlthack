import { useEffect, useRef, useState } from "react";
import ProcurementForm from "./components/ProcurementForm";
import { emptyFilters } from "./utils/filters";
import type { Filters } from "./utils/filters";
import ResultsPanel from "./components/ResultsPanel";
import type { SearchState } from "./components/ResultsPanel";
import SupplierDialog from "./components/SupplierDialog";
import { searchSuppliers } from "./services/api";
import { errorMessage } from "./utils/format";
import type { Procurement, SelectedSupplier } from "./types";
import CsvPage from "./components/CsvPage";
import HomePage from "./components/HomePage";
import { toSearchLot } from "./utils/lot";

function SingleLotPage() {
  const [filters, setFilters] = useState<Filters>({ ...emptyFilters });
  const [state, setState] = useState<SearchState>({ status: "idle" });
  const [dirty, setDirty] = useState(false);
  const [selected, setSelected] = useState<SelectedSupplier | null>(null);
  const controller = useRef<AbortController | null>(null);

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
            only_reliable: filters.onlyReliable,
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
      <main id="main" className="main-content">
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

export default function App() {
  const path = window.location.pathname.replace(/\/$/, "") || "/";
  const page = path === "/single" ? "Подбор одного лота" : path === "/csv" ? "Подбор по CSV" : null;
  return (
    <>
      <header className="site-header">
        <a className="site-brand" href="/">
          Подбор поставщиков<span>Закупки · Контрагенты · Обоснования</span>
        </a>
        {page && (
          <nav aria-label="Навигация">
            <a href="/">Все сценарии</a>
            <span>/</span>
            <span aria-current="page">{page}</span>
          </nav>
        )}
      </header>
      {path === "/" ? (
        <HomePage />
      ) : path === "/single" ? (
        <SingleLotPage />
      ) : path === "/csv" ? (
        <CsvPage />
      ) : (
        <main className="scenario-page">
          <h1>Страница не найдена</h1>
          <a href="/">На главную</a>
        </main>
      )}
    </>
  );
}
