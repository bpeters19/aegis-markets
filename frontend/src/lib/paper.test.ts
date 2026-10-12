import { describe, expect, it } from "vitest";

import type { PaperDay } from "./api";
import { describeItem, equitySeries } from "./paper";

describe("equitySeries", () => {
  it("expresses equity as a return since the start", () => {
    const [point] = equitySeries([{ day: "2026-10-12", equity: "100500.00" } as unknown as PaperDay], 100000);
    expect(point.ret).toBeCloseTo(0.005);
  });
});

describe("describeItem", () => {
  it("formats a fill with its price", () => {
    expect(describeItem({ symbol: "SPY", side: "BUY", role: "entry", quantity: 10, price: "680.5" }))
      .toBe("BUY 10 SPY @ 680.50 (entry)");
  });

  it("formats a queued order with its type", () => {
    expect(describeItem({ symbol: "TLT", side: "SELL", role: "exit", quantity: 5, type: "MARKET" }))
      .toBe("SELL 5 TLT (exit, MARKET)");
  });
});
