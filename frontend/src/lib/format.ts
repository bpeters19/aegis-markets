export function pct(value: number | null | undefined, signed = true): string {
  if (value == null) return "n/a";
  const sign = signed && value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(2)}%`;
}

export function num(value: number | null | undefined, digits = 2): string {
  return value == null ? "n/a" : value.toFixed(digits);
}

/** Display only: the API sends money as exact decimal strings; we convert just to format it. */
export function money(value: string | number | null | undefined): string {
  if (value == null) return "n/a";
  return Number(value).toLocaleString("en-US", { style: "currency", currency: "USD" });
}
