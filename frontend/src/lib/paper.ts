import type { PaperDay } from "./api";

export type LedgerItem = {
  symbol: string;
  side: string;
  role: string;
  quantity: number;
  price?: string;
  type?: string;
};

export function asItems(items: Record<string, unknown>[]): LedgerItem[] {
  return items as unknown as LedgerItem[];
}

export function describeItem(item: LedgerItem): string {
  const at = item.price ? ` @ ${Number(item.price).toFixed(2)}` : "";
  const kind = item.type ? `${item.role}, ${item.type}` : item.role;
  return `${item.side} ${item.quantity} ${item.symbol}${at} (${kind})`;
}

export function equitySeries(days: PaperDay[], capital: number) {
  return days.map((d) => ({ date: d.day, ret: Number(d.equity) / capital - 1 }));
}
