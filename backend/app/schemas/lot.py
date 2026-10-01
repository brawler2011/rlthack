from typing import Optional
from pydantic import BaseModel

class LotBase(BaseModel):
    procedure_name: str
    subject: str
    start_price: float
    okpd2_code: str
    is_smp: bool = False
    customer_inn: Optional[str] = None
    customer_kpp: Optional[str] = None

class LotResponse(LotBase):
    lot_id: Optional[int] = None
    publish_date: Optional[str] = None
    procedure_id: Optional[int] = None
