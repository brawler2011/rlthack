import type { SelectedSupplier } from "../types";

export default function ProfileFitDetails({
  fit,
  compact = false,
}: {
  fit: SelectedSupplier["profile_fit"];
  compact?: boolean;
}) {
  if (!fit) return null;
  if (compact) return <span className="new-company-reason">{fit.label}</span>;
  return (
    <section className="dialog-section" aria-labelledby="profile-fit-heading">
      <h3 id="profile-fit-heading">Соответствие профилю лота</h3>
      <p className="xai-summary">{fit.label}</p>
      {fit.evidence.length > 0 && (
        <ul className="profile-evidence-list">
          {fit.evidence.map((evidence, index) => (
            <li key={`${evidence.kind}-${evidence.okpd2_code}-${index}`}>
              <strong>ОКПД2 {evidence.okpd2_code}</strong>
              <p>{evidence.description}</p>
              {evidence.lot_ids.length > 0 && (
                <p>Примеры: лоты № {evidence.lot_ids.join(", № ")}.</p>
              )}
              <small>
                Источник:{" "}
                {evidence.source_url ? (
                  <a href={evidence.source_url} target="_blank" rel="noreferrer">
                    {evidence.source}
                  </a>
                ) : (
                  evidence.source
                )}
              </small>
            </li>
          ))}
        </ul>
      )}
      {fit.missing_codes.length > 0 && (
        <p className="data-unavailable">
          Требуется проверка позиций: {fit.missing_codes.join(", ")}. Данных о заявленной продукции,
          подходящем ОКВЭД или победах этой компании по этим категориям недостаточно.
        </p>
      )}
      <p className="data-unavailable">
        Перед приглашением проверьте характеристики товара, объём поставки и обязательные
        разрешения.
      </p>
    </section>
  );
}
