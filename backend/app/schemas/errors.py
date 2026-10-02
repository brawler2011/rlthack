from app.schemas.base import ContractModel


class ValidationIssue(ContractModel):
    loc: list[str | int]
    msg: str
    type: str


class ValidationErrorResponse(ContractModel):
    detail: list[ValidationIssue]
