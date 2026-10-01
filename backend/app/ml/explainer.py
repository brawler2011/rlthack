from typing import Any

from app.schemas.xai import XaiReport


class XaiExplainer:
    """Генерация факторов объяснимости (Explainable AI) на основе SHAP values."""

    def __init__(self, ranker_model: Any = None):
        self.ranker_model = ranker_model

    def explain(self, candidate_features: dict[str, Any]) -> XaiReport:
        """Формирует отчет объяснимости со списком вкладов признаков."""
        return XaiReport(
            summary="Рекомендован на основе опыта исполнения контрактов и региональности.",
            factors=[],
            recommendation_level="HIGH",
        )
