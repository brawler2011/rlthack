from pydantic import BaseModel


class XaiFactor(BaseModel):
    factor_name: str
    shap_value: float
    description: str


class XaiReport(BaseModel):
    summary: str
    factors: list[XaiFactor]
    recommendation_level: str  # HIGH, MEDIUM, LOW
