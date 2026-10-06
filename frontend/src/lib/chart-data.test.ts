import { describe, expect, it } from "vitest";

import { drawdowns, toReturns } from "./chart-data";

describe("drawdowns", () => {
  it("measures distance below the running peak", () => {
    const result = drawdowns([100, 120, 90, 110, 130]).map((x) => (x ?? 0).toFixed(4));
    expect(result).toEqual(["0.0000", "0.0000", "-0.2500", "-0.0833", "0.0000"]);
  });

  it("skips missing values", () => {
    expect(drawdowns([100, null, 50])).toEqual([0, null, -0.5]);
  });
});

describe("toReturns", () => {
  it("expresses equity as a return from the starting value", () => {
    const [point] = toReturns(
      [{ date: "2026-01-02", equity: "110000.00", benchmark: "95000.00", exposure: 0.5 }],
      100000,
    );
    expect(point.strategy).toBeCloseTo(0.1);
    expect(point.benchmark).toBeCloseTo(-0.05);
  });
});
