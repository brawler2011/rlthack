import type { EvidenceLot } from "../types";
import { money } from "../utils/format";

export default function EvidenceList({ lots }: { lots: EvidenceLot[] }) {
  return (
    <div className="evidence-list">
      {lots.map((lot, index) => (
        <article className="evidence-card" key={`${lot.lot_id}-${index}`}>
          <div className="evidence-meta">
            <span>Лот № {lot.lot_id}</span>
            <span className={lot.won ? "winner-badge" : "small-badge"}>
              {lot.won ? "Победа" : "Участие"}
            </span>
          </div>
          <h4>{lot.subject || "Предмет закупки не указан"}</h4>
          <p>
            {lot.publish_date &&
              new Date(`${lot.publish_date}T00:00:00`).toLocaleDateString("ru-RU")}
            {lot.publish_date && " · "}
            {money(lot.start_price)}
          </p>
        </article>
      ))}
    </div>
  );
}
