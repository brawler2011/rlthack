import type { SupplierRole } from "../types";

export const roles: { value: SupplierRole; label: string }[] = [
  { value: "MANUFACTURER", label: "Производители" },
  { value: "DISTRIBUTOR", label: "Дистрибьюторы" },
  { value: "SUPPLIER", label: "Поставщики" },
];

export const roleNames: Record<SupplierRole, string> = {
  MANUFACTURER: "Производитель",
  DISTRIBUTOR: "Дистрибьютор",
  SUPPLIER: "Поставщик",
};

export function money(value: number) {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  }).format(value);
}

export function number(value: number, maximumFractionDigits = 0) {
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits }).format(value);
}

export function percent(value: number) {
  return `${number(value * 100, 1)}%`;
}

export function errorMessage(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Не удалось выполнить запрос. Попробуйте ещё раз.";
}
