import type { Procurement, SearchSuppliersRequest } from "../types";

export function toSearchLot(lot: Procurement): Pick<SearchSuppliersRequest, "lot_id" | "lot"> {
  if ("lot_id" in lot) return { lot_id: lot.lot_id, lot: null };
  return {
    lot_id: null,
    lot: {
      subject: lot.subject,
      items: lot.items,
      okpd2_codes: lot.okpd2_codes,
      start_price: lot.start_price,
      is_smp: lot.is_smp,
      customer_inn: lot.customer_inn,
      channel: lot.channel,
    },
  };
}
