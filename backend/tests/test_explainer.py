import numpy as np
import pytest

from app.ml.candidates import FEATURES
from app.ml.explainer import Facts, explain, plural


@pytest.mark.parametrize(
    ("n", "text"),
    [(1, "1 победа"), (3, "3 победы"), (5, "5 побед"), (11, "11 побед"), (21, "21 победа")],
)
def test_plural(n, text):
    assert plural(n, ("победа", "победы", "побед")) == text


def test_explain_groups_shap_and_words_the_facts():
    shap = np.zeros(len(FEATURES))
    shap[FEATURES.index("customer_score")] = 0.9
    shap[FEATURES.index("customer_rank")] = 0.3
    shap[FEATURES.index("vec_score")] = 0.5
    shap[FEATURES.index("abs_price_gap")] = -0.4
    facts = Facts(
        customer_wins=3,
        customer_bids=4,
        similar_wins=2,
        similar_bids=5,
        typical_check=1_200_000,
        lot_price=900_000,
    )

    explanation = explain(shap, facts, relevance=0.8)

    assert explanation.level == "HIGH"
    assert [f.name for f in explanation.factors] == ["customer", "similar_lots", "price"]
    assert explanation.factors[0].impact == pytest.approx(1.2)
    assert explanation.factors[0].text == "3 победы у этого заказчика из 4 участий"
    assert explanation.factors[2].text == "Типичный чек 1,2 млн ₽ при НМЦК 900 тыс. ₽"
    assert explanation.summary.startswith("3 победы у этого заказчика")


def test_explain_without_positive_factors():
    explanation = explain(np.zeros(len(FEATURES)), Facts(), relevance=0.1)
    assert explanation.level == "LOW"
    assert explanation.factors == []
    assert explanation.summary == "Слабое совпадение с историей"
