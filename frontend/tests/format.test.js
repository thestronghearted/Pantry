import { describe, expect, it } from "vitest";
import { addDays, formatMinutes, formatQuantity, mondayOf, parseIso, toIso } from "../src/format.js";

describe("weeks", () => {
  it("finds the Monday of any day", () => {
    expect(mondayOf(new Date(2026, 10, 2))).toBe("2026-11-02"); // Monday
    expect(mondayOf(new Date(2026, 10, 8))).toBe("2026-11-02"); // Sunday belongs to the week before
    expect(mondayOf(new Date(2026, 10, 4))).toBe("2026-11-02");
  });

  it("adds days across month and year boundaries", () => {
    expect(addDays("2026-12-28", 7)).toBe("2027-01-04");
    expect(addDays("2026-11-02", -7)).toBe("2026-10-26");
  });

  it("round-trips ISO dates without time-zone drift", () => {
    expect(toIso(parseIso("2026-03-29"))).toBe("2026-03-29");
  });
});

describe("formatting", () => {
  it("formats minutes", () => {
    expect(formatMinutes(25)).toBe("25 min");
    expect(formatMinutes(60)).toBe("1 h");
    expect(formatMinutes(95)).toBe("1 h 35 min");
  });

  it("formats quantities with units", () => {
    expect(formatQuantity(3, "piece")).toBe("3");
    expect(formatQuantity(450, "g")).toBe("450 g");
    expect(formatQuantity(1.5, "kg")).toBe("1.5 kg");
    expect(formatQuantity(0.333333, "cup")).toBe("0.33 cup");
  });
});
