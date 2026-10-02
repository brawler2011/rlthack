from typing import Literal

from app.schemas.base import ContractModel


class HealthResponse(ContractModel):
    status: Literal["ok"]
    service: Literal["rlthack-recsys-backend"]
