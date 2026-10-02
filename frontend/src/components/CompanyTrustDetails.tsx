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

function ReportDate({ value }: { value: string | null | undefined }) {
  return (
    <small className="fns-report-date">
      {value ? `Сведения на ${registrationDate(value)}` : "Дата сведений неизвестна"}
    </small>
  );
}

export default function CompanyTrustDetails({
  trust,
}: {
  trust: NonNullable<SupplierEnrichment["trust"]>;
}) {
  return (
    <>
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
          <dt>Доходы по отчётности</dt>
          <dd>
            {money(trust.revenue)}
            <ReportDate value={trust.revenue_as_of} />
          </dd>
        </div>
        <div>
          <dt>Расходы по отчётности</dt>
          <dd>
            {money(trust.expenses)}
            <ReportDate value={trust.revenue_as_of} />
          </dd>
        </div>
        <div>
          <dt>Уплаченные налоги и взносы</dt>
          <dd>
            {money(trust.taxes_paid)}
            <ReportDate value={trust.taxes_paid_as_of} />
          </dd>
        </div>
        <div>
          <dt>Налоговая задолженность</dt>
          <dd>
            {money(trust.tax_debt)}
            <ReportDate value={trust.tax_debt_as_of} />
          </dd>
        </div>
        <div>
          <dt>Неуплаченные штрафы за налоговые правонарушения</dt>
          <dd>
            {money(trust.tax_fines ?? null)}
            <ReportDate value={trust.tax_fines_as_of} />
          </dd>
        </div>
        <div>
          <dt>Численность сотрудников по данным ФНС</dt>
          <dd>
            {trust.headcount === null ? "Нет данных" : number(trust.headcount)}
            <ReportDate value={trust.headcount_as_of} />
          </dd>
        </div>
      </dl>
      <p className="data-unavailable">
        {trust.refreshed_at && <>Обновлено {registrationDate(trust.refreshed_at)}. </>}
        Задолженность указана на дату сведений ФНС и могла измениться. «Нет данных» означает
        отсутствие сведений в загруженном наборе.
      </p>
      <p className="fns-source-links">
        Источники ФНС:{" "}
        <a
          href="https://www.nalog.gov.ru/opendata/7707329152-debtam/"
          target="_blank"
          rel="noreferrer"
        >
          задолженности
        </a>
        ,{" "}
        <a
          href="https://www.nalog.gov.ru/opendata/7707329152-taxoffence/"
          target="_blank"
          rel="noreferrer"
        >
          правонарушения
        </a>
        ,{" "}
        <a
          href="https://www.nalog.gov.ru/opendata/7707329152-revexp/"
          target="_blank"
          rel="noreferrer"
        >
          доходы и расходы
        </a>
        ,{" "}
        <a
          href="https://www.nalog.gov.ru/opendata/7707329152-paytax/"
          target="_blank"
          rel="noreferrer"
        >
          уплаченные налоги
        </a>
        ,{" "}
        <a
          href="https://www.nalog.gov.ru/opendata/7707329152-sshr2019/"
          target="_blank"
          rel="noreferrer"
        >
          численность
        </a>
        .
      </p>
    </>
  );
}
