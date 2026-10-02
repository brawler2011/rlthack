from pydantic import Field

from app.schemas.base import ContractModel


class LotBase(ContractModel):
    procedure_name: str
    subject: str
    start_price: float = Field(ge=0)
    okpd2_code: str
    is_smp: bool
    customer_inn: str | None
    customer_kpp: str | None


class LotResponse(LotBase):
    lot_id: int | None
    publish_date: str | None
    procedure_id: int | None
