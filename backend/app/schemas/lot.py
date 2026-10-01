from datetime import date

from pydantic import BaseModel, Field


class NewLot(BaseModel):
    """A procurement that is not in the data yet, typed in by the user."""

    subject: str = Field(min_length=3, examples=["Поставка картриджей для принтеров HP"])
    items: list[str] = Field(default=[], description="Item (TRU) names")
    okpd2_codes: list[str] = Field(default=[], examples=[["20.59.12.120"]])
    start_price: float | None = Field(default=None, description="Initial max price, RUB")
    customer_inn: str | None = None
    channel: str | None = Field(default=None, description="«АИС ГЗ» or «ЭМ» (e-shop)")
    is_smp: bool = Field(default=False, description="Only for SMEs")


class LotCard(BaseModel):
    lot_id: int | None = Field(default=None, description="None for a new lot")
    publish_date: date | None = None
    subject: str
    procedure_name: str | None = None
    start_price: float | None = None
    okpd2_codes: list[str] = []
    items: list[str] = []
    customer_inn: str | None = None
    channel: str | None = None
    is_smp: bool = False
    actual_winners: list[str] = Field(
        default=[], description="INNs of the real winners, for lots from the data (demo)"
    )


class LotListItem(BaseModel):
    lot_id: int
    publish_date: date | None = None
    subject: str | None = None
    start_price: float | None = None
    channel: str | None = None
    customer_inn: str | None = None
