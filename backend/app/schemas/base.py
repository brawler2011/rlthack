from pydantic import BaseModel, ConfigDict


class ContractModel(BaseModel):
    """JSON contracts have required keys and reject undeclared fields."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
