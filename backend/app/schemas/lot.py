from datetime import date

from pydantic import Field

from app.schemas.base import ContractModel


class NewLot(ContractModel):
    """A procurement that is not in the data yet, typed in by the user."""

    subject: str = Field(min_length=3, examples=["Поставка картриджей для принтеров HP"])
    items: list[str] = Field(description="Item (TRU) names")
    okpd2_codes: list[str] = Field(examples=[["20.59.12.120"]])
    start_price: float | None = Field(ge=0, description="Initial max price, RUB")
    customer_inn: str | None
    channel: str | None = Field(description="«АИС ГЗ» or «ЭМ» (e-shop)")
    is_smp: bool = Field(description="Only for SMEs")


class LotCard(ContractModel):
    lot_id: int | None = Field(description="None for a new lot")
    publish_date: date | None
    subject: str
    procedure_name: str | None
    start_price: float | None
    okpd2_codes: list[str]
    items: list[str]
    customer_inn: str | None
    channel: str | None
    is_smp: bool
    actual_winners: list[str] = Field(
        description="INNs of the real winners, for lots from the data (demo)"
    )


class LotListItem(ContractModel):
    lot_id: int
    publish_date: date | None
    subject: str | None
    start_price: float | None
    channel: str | None
    customer_inn: str | None
