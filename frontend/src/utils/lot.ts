import type { LotInput } from "../types";

export function toLotInput(lot: LotInput): LotInput {
  return {
    procedure_name: lot.procedure_name,
    subject: lot.subject,
    start_price: lot.start_price,
    okpd2_code: lot.okpd2_code,
    is_smp: lot.is_smp,
    customer_inn: lot.customer_inn,
    customer_kpp: lot.customer_kpp,
  };
}
