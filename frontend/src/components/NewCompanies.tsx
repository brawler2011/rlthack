import { Building2, ChevronRight } from "lucide-react";
import type { NewSupplier } from "../types";
import ReliabilityWarnings from "./ReliabilityWarnings";
import ProfileFitDetails from "./ProfileFitDetails";

export default function NewCompanies({
  suppliers,
  onSelect,
}: {
  suppliers: NewSupplier[];
  onSelect: (supplier: NewSupplier) => void;
}) {
  return (
    <section className="new-companies" aria-label="Новые компании из реестра МСП">
      <h3>Новые компании из реестра МСП</h3>
      {suppliers.length === 0 ? (
        <p>Подходящие новые компании не найдены.</p>
      ) : (
        suppliers.map((supplier) => (
          <button
            type="button"
            className="new-company-row"
            key={supplier.inn}
            onClick={() => onSelect(supplier)}
          >
            <Building2 size={20} />
            <span>
              <strong>{supplier.name || `Компания · ИНН ${supplier.inn}`}</strong>
              <span className="new-company-meta">
                ИНН {supplier.inn} · {supplier.role_display}
              </span>
              <span className="new-company-reason">{supplier.reason}</span>
              <ProfileFitDetails fit={supplier.profile_fit} compact />
              <ReliabilityWarnings warnings={supplier.warnings} />
            </span>
            <ChevronRight size={18} />
          </button>
        ))
      )}
    </section>
  );
}
