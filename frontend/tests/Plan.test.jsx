import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../src/api.js", async (importOriginal) => ({
  ...(await importOriginal()),
  api: { plan: vi.fn(), generate: vi.fn(), swap: vi.fn(), setPortion: vi.fn(), recipes: vi.fn() },
}));
import { api, ApiError } from "../src/api.js";
import Plan from "../src/pages/Plan.jsx";

const WEEK = "2026-11-02";
const macros = { kcal: 420, protein: 30, carbs: 40, fat: 12 };

function planWith({ off = false, skipped = false } = {}) {
  const days = Array.from({ length: 7 }, (_, i) => ({
    date: `2026-11-0${2 + i}`.replace("2026-11-010", "2026-11-10"),
    slots: [],
    cooking_minutes: 0,
    totals: [],
    off_target: false,
  }));
  days[0] = {
    date: WEEK,
    cooking_minutes: 45,
    off_target: off,
    slots: [
      {
        meal: "dinner",
        recipe: { id: 5, title: "Turkey chilli", difficulty: "easy", total_minutes: 45, macros_per_serving: macros },
        portions: [
          { member_id: 1, servings: 1.5, skipped: false, kcal: 630 },
          { member_id: 2, servings: skipped ? 0 : 1, skipped, kcal: 420 },
        ],
      },
    ],
    totals: [
      { member_id: 1, kcal: 630, protein: 45, carbs: 60, fat: 18, target_kcal: 1900, error: 0.05 },
      { member_id: 2, kcal: 420, protein: 30, carbs: 40, fat: 12, target_kcal: 1500, error: off ? 0.2 : 0.02 },
    ],
  };
  return {
    week_start: WEEK,
    members: [{ id: 1, name: "Alex", target_kcal: 1900 }, { id: 2, name: "Sam", target_kcal: 1500 }],
    days,
    weekly_cooking_minutes: 45,
  };
}
const EMPTY = { ...planWith(), days: planWith().days.map((d) => ({ ...d, slots: [], totals: [], cooking_minutes: 0 })), weekly_cooking_minutes: 0 };

beforeEach(() => Object.values(api).forEach((fn) => fn.mockReset()));

describe("Plan", () => {
  it("invites the user to plan when the week is empty", async () => {
    api.plan.mockResolvedValue(EMPTY);
    render(<Plan week={WEEK} setWeek={() => {}} />);
    expect(await screen.findByText(/Nothing planned yet/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Plan this week" })).toBeInTheDocument();
  });

  it("sends the chosen limits when generating", async () => {
    api.plan.mockResolvedValue(EMPTY);
    api.generate.mockResolvedValue(planWith());
    render(<Plan week={WEEK} setWeek={() => {}} />);
    await userEvent.selectOptions(await screen.findByLabelText("Recipes up to"), "medium");
    await userEvent.selectOptions(screen.getByLabelText("Cooking per day"), "90");
    await userEvent.click(screen.getByRole("button", { name: "Plan this week" }));

    expect(api.generate).toHaveBeenCalledWith({ week_start: WEEK, max_difficulty: "medium", max_minutes_per_day: 90 });
    expect(await screen.findByText("Turkey chilli")).toBeInTheDocument();
    expect(screen.getByText(/Total cooking this week/)).toHaveTextContent("45 min");
  });

  it("shows per-member portion chips, cooking time and calories against target", async () => {
    api.plan.mockResolvedValue(planWith());
    render(<Plan week={WEEK} setWeek={() => {}} />);
    const day = await screen.findByRole("region", { name: /Mon/ });
    expect(within(day).getByRole("button", { name: "Alex: 1.5 servings" })).toHaveTextContent("Alex: 1.5×");
    expect(within(day).getByRole("button", { name: "Sam: 1 servings" })).toBeInTheDocument();
    expect(within(day).getByText(/630 \/ 1900 kcal/)).toBeInTheDocument();
    expect(within(day).getAllByText("⏱ 45 min")).toHaveLength(2); // the day total and the recipe itself
    expect(within(day).queryByText("Off target")).not.toBeInTheDocument();
  });

  it("flags days that miss someone's target", async () => {
    api.plan.mockResolvedValue(planWith({ off: true }));
    render(<Plan week={WEEK} setWeek={() => {}} />);
    expect(await screen.findByText("Off target")).toBeInTheDocument();
  });

  it("shows the server's explanation when no recipes fit", async () => {
    api.plan.mockResolvedValue(EMPTY);
    api.generate.mockRejectedValue(new ApiError(422, "No recipes fit those limits. Try allowing harder recipes or more cooking time per day."));
    render(<Plan week={WEEK} setWeek={() => {}} />);
    await userEvent.click(await screen.findByRole("button", { name: "Plan this week" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No recipes fit those limits");
  });

  it("changes a portion through the sheet", async () => {
    api.plan.mockResolvedValue(planWith());
    const updated = planWith();
    updated.days[0].slots[0].portions[0].servings = 1.75;
    api.setPortion.mockResolvedValue(updated);
    render(<Plan week={WEEK} setWeek={() => {}} />);
    await userEvent.click(await screen.findByRole("button", { name: "Alex: 1.5 servings" }));
    await userEvent.click(screen.getByRole("button", { name: "Bigger portion" }));
    expect(api.setPortion).toHaveBeenCalledWith(WEEK, "dinner", { member_id: 1, servings: 1.75 });
    expect(await screen.findByText("1.75 servings")).toBeInTheDocument();
  });

  it("skips a meal for one person", async () => {
    api.plan.mockResolvedValue(planWith());
    api.setPortion.mockResolvedValue(planWith({ skipped: true }));
    render(<Plan week={WEEK} setWeek={() => {}} />);
    await userEvent.click(await screen.findByRole("button", { name: "Sam: 1 servings" }));
    await userEvent.click(screen.getByRole("button", { name: "Skip this meal" }));
    expect(api.setPortion).toHaveBeenCalledWith(WEEK, "dinner", { member_id: 2, skipped: true });
    expect(await screen.findByText("Skipping")).toBeInTheDocument();
  });

  it("swaps a recipe using options that fit the limits", async () => {
    api.plan.mockResolvedValue(planWith());
    api.recipes.mockResolvedValue([
      { id: 5, title: "Turkey chilli", complete: true, difficulty: "easy", total_minutes: 45, macros_per_serving: macros },
      { id: 6, title: "Tofu stir fry", complete: true, difficulty: "easy", total_minutes: 22, macros_per_serving: macros },
    ]);
    api.swap.mockResolvedValue(planWith());
    render(<Plan week={WEEK} setWeek={() => {}} />);
    await userEvent.click(await screen.findByRole("button", { name: "Swap" }));

    expect(api.recipes).toHaveBeenCalledWith({ meal_type: "dinner", difficulty: "easy", max_minutes: 60 });
    const dialog = await screen.findByRole("dialog", { name: /Swap dinner/ });
    expect(within(dialog).queryByText("Turkey chilli")).not.toBeInTheDocument(); // the current recipe is not offered
    await userEvent.click(within(dialog).getByText("Tofu stir fry"));
    expect(api.swap).toHaveBeenCalledWith(WEEK, "dinner", 6);
  });
});
