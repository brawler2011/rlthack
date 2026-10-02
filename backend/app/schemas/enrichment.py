from app.schemas.base import ContractModel
from app.schemas.supplier import RoleType


class SupplierEnrichment(ContractModel):
    inn: str
    role: RoleType | None
    is_gisp_manufacturer: bool | None
    okved_main: str | None
    status: str | None
