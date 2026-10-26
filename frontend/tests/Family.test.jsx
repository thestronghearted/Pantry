import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../src/api.js", async (importOriginal) => ({
  ...(await importOriginal()),
  api: { members: vi.fn(), addMember: vi.fn(), updateMember: vi.fn(), deleteMember: vi.fn(), deleteHousehold: vi.fn() },
}));
import { api, ApiError } from "../src/api.js";
import Family from "../src/pages/Family.jsx";

const NOTICE = "Estimates only, not medical advice. Talk to a doctor before starting a weight-loss plan.";
const ALEX = {
  id: 1, name: "Alex", sex: "male", age: 40, height_cm: 180, weight_kg: 95, activity: "light", goal: "lose",
  kg_per_week: 0.5, custom_kcal: null,
  targets: { kcal: 2100, protein_g: 171, carbs_g: 190, fat_g: 58, effective_kg_per_week: 0.5, adjusted: false, notice: NOTICE },
};
const SESSION = { household: { id: 1, name: "Smiths" }, email: "a@example.com" };

beforeEach(() => Object.values(api).forEach((fn) => fn.mockReset()));

const renderFamily = () => render(<Family session={SESSION} onSignOut={() => {}} onDeleted={() => {}} />);

describe("Family", () => {
  it("shows each member's calorie and macro targets with the medical notice", async () => {
    api.members.mockResolvedValue([ALEX]);
    renderFamily();
    const card = await screen.findByRole("region", { name: "Alex" });
    expect(within(card).getByText("2100")).toBeInTheDocument();
    expect(within(card).getByText("P 171 g")).toBeInTheDocument();
    expect(within(card).getByText("C 190 g")).toBeInTheDocument();
    expect(within(card).getByText("F 58 g")).toBeInTheDocument();
    expect(within(card).getByText(NOTICE)).toBeInTheDocument();
  });

  it("explains when the safety floor changed the goal", async () => {
    const adjusted = { ...ALEX, targets: { ...ALEX.targets, adjusted: true, effective_kg_per_week: 0.3 } };
    api.members.mockResolvedValue([adjusted]);
    renderFamily();
    expect(await screen.findByText(/adjusted to about 0.3 kg per week/)).toBeInTheDocument();
  });

  it("asks to add people when the household is empty", async () => {
    api.members.mockResolvedValue([]);
    renderFamily();
    expect(await screen.findByText(/Add everyone who eats at your table/)).toBeInTheDocument();
  });

  it("forces custom calories for under-18s and sends them", async () => {
    api.members.mockResolvedValue([]);
    api.addMember.mockResolvedValue({ ...ALEX, id: 2, name: "Kit" });
    renderFamily();
    await userEvent.click(await screen.findByRole("button", { name: "Add person" }));

    await userEvent.type(screen.getByLabelText("Name"), "Kit");
    const age = screen.getByLabelText("Age");
    await userEvent.clear(age);
    await userEvent.type(age, "10");

    expect(screen.getByLabelText("Goal")).toBeDisabled();
    expect(screen.getByText(/Adult calorie formulas do not apply under 18/)).toBeInTheDocument();
    const kcal = screen.getByLabelText("Daily calories");
    await userEvent.clear(kcal);
    await userEvent.type(kcal, "1900");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(api.addMember).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Kit", age: 10, goal: "custom", custom_kcal: 1900, kg_per_week: null }),
    );
  });

  it("shows validation errors from the server", async () => {
    api.members.mockResolvedValue([]);
    api.addMember.mockRejectedValue(new ApiError(422, "kg_per_week must be between 0.1 and 1.0"));
    renderFamily();
    await userEvent.click(await screen.findByRole("button", { name: "Add person" }));
    await userEvent.type(screen.getByLabelText("Name"), "Sam");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("kg_per_week must be between 0.1 and 1.0");
  });

  it("requires the password to delete the household", async () => {
    api.members.mockResolvedValue([]);
    api.deleteHousehold.mockResolvedValue(null);
    const onDeleted = vi.fn();
    render(<Family session={SESSION} onSignOut={() => {}} onDeleted={onDeleted} />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete household…" }));
    await userEvent.type(screen.getByLabelText("Confirm with your password"), "correct-horse-battery");
    await userEvent.click(screen.getByRole("button", { name: "Delete everything" }));
    expect(api.deleteHousehold).toHaveBeenCalledWith("correct-horse-battery");
    expect(onDeleted).toHaveBeenCalled();
  });
});
