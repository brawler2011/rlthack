import type { SupplierEnrichment } from "../types";
import { money, number } from "../utils/format";

const statusNames: Record<string, string> = {
  ACTIVE: "Действующая компания",
  INACTIVE: "Компания прекратила деятельность",
  LIQUIDATION_STAGE: "Компания в процессе ликвидации",
  BANKRUPTCY_STAGE: "Процедура банкротства",
  REORGANIZATION_STAGE: "Компания в процессе реорганизации",
};

function registrationDate(value: string | null) {
  if (!value) return "Нет данных";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Нет данных";
  return new Intl.DateTimeFormat("ru-RU", { timeZone: "UTC" }).format(date);
}

export default function CompanyTrustDetails({
  trust,
}: {
  trust: NonNullable<SupplierEnrichment["trust"]>;
}) {
  return (
    <dl className="enrichment-list trust-details">
      <div>
        <dt>Статус</dt>
        <dd>
          {trust.status === null
            ? "Нет данных"
            : statusNames[trust.status] || "Статус не распознан"}
        </dd>
      </div>
      <div>
        <dt>Дата регистрации</dt>
        <dd>{registrationDate(trust.registered)}</dd>
      </div>
      <div>
        <dt>Доходы за последний год</dt>
        <dd>{money(trust.revenue)}</dd>
      </div>
      <div>
        <dt>Расходы за последний год</dt>
        <dd>{money(trust.expenses)}</dd>
      </div>
      <div>
        <dt>Уплаченные налоги и взносы</dt>
        <dd>{money(trust.taxes_paid)}</dd>
      </div>
      <div>
        <dt>Налоговая задолженность</dt>
        <dd>{money(trust.tax_debt)}</dd>
      </div>
      <div>
        <dt>Численность сотрудников по данным ФНС</dt>
        <dd>{trust.headcount === null ? "Нет данных" : number(trust.headcount)}</dd>
      </div>
    </dl>
  );
}
