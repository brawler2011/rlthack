from pydantic import BaseModel


class LotBase(BaseModel):
    procedure_name: str
    subject: str
    start_price: float
    okpd2_code: str
    is_smp: bool = False
    customer_inn: str | None = None
    customer_kpp: str | None = None


class LotResponse(LotBase):
    lot_id: int | None = None
    publish_date: str | None = None
    procedure_id: int | None = None
