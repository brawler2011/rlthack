import { TriangleAlert } from "lucide-react";

export default function ReliabilityWarnings({ warnings }: { warnings: readonly string[] }) {
  if (warnings.length === 0) return null;

  return (
    <span className="reliability-warnings" role="list" aria-label="Предупреждения">
      {warnings.map((warning, index) => (
        <span className="reliability-warning" role="listitem" key={`${index}-${warning}`}>
          <TriangleAlert size={15} aria-hidden="true" />
          <span>{warning}</span>
        </span>
      ))}
    </span>
  );
}
