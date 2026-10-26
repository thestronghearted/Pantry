import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../src/api.js", async (importOriginal) => ({
  ...(await importOriginal()),
  api: { createRecipe: vi.fn(), updateRecipe: vi.fn(), searchIngredients: vi.fn(), addIngredient: vi.fn(), recipe: vi.fn() },
}));
import { api } from "../src/api.js";
import RecipeForm from "../src/pages/RecipeForm.jsx";

const COMPLETE = { id: 9, title: "Eggs", complete: true, missing_nutrition: [], macros_per_serving: { kcal: 143, protein: 12, carbs: 1, fat: 9 } };

beforeEach(() => {
  Object.values(api).forEach((fn) => fn.mockReset());
  api.searchIngredients.mockResolvedValue([{ name: "egg" }]);
});

async function fillBasics() {
  await userEvent.type(screen.getByLabelText("Title"), "Eggs");
  await userEvent.type(screen.getByLabelText("Qty"), "2");
  await userEvent.selectOptions(screen.getByLabelText("Unit"), "piece");
  await userEvent.type(screen.getByLabelText("Ingredient"), "egg");
}

describe("RecipeForm", () => {
  it("builds the request from the form, including several ingredient rows", async () => {
    api.createRecipe.mockResolvedValue(COMPLETE);
    const onSaved = vi.fn();
    render(<RecipeForm initial={{}} onSaved={onSaved} onCancel={() => {}} />);

    await fillBasics();
    await userEvent.click(screen.getByRole("button", { name: "+ Add ingredient" }));
    const qty = screen.getAllByLabelText("Qty");
    await userEvent.type(qty[1], "30");
    await userEvent.type(screen.getAllByLabelText("Ingredient")[1], "butter");
    await userEvent.type(screen.getByLabelText(/Method/), "Boil.\nPeel.");
    await userEvent.click(screen.getByRole("button", { name: "Save recipe" }));

    const body = api.createRecipe.mock.calls[0][0];
    expect(body.title).toBe("Eggs");
    expect(body.difficulty).toBe("easy");
    expect(body.meal_types).toEqual(["dinner"]);
    expect(body.ingredients).toEqual([
      { name: "egg", quantity: 2, unit: "piece" },
      { name: "butter", quantity: 30, unit: "g" },
    ]);
    expect(body.steps).toEqual(["Boil.", "Peel."]);
    expect(onSaved).toHaveBeenCalledWith(COMPLETE);
  });

  it("lets the user pick which meals the recipe suits", async () => {
    api.createRecipe.mockResolvedValue(COMPLETE);
    render(<RecipeForm initial={{}} onSaved={() => {}} onCancel={() => {}} />);
    await fillBasics();
    await userEvent.click(screen.getByLabelText("Breakfast"));
    await userEvent.click(screen.getByLabelText("Dinner"));
    await userEvent.click(screen.getByRole("button", { name: "Save recipe" }));
    expect(api.createRecipe.mock.calls[0][0].meal_types).toEqual(["breakfast"]);
  });

  it("asks for nutrition when an ingredient is unknown, then saves it", async () => {
    api.createRecipe.mockResolvedValue({
      id: 10, title: "Gran's stew", complete: false, missing_nutrition: ["grandma sauce"], macros_per_serving: null,
    });
    api.addIngredient.mockResolvedValue({ name: "grandma sauce" });
    api.recipe.mockResolvedValue({ ...COMPLETE, id: 10 });
    const onSaved = vi.fn();
    render(<RecipeForm initial={{}} onSaved={onSaved} onCancel={() => {}} />);

    await userEvent.type(screen.getByLabelText("Title"), "Gran's stew");
    await userEvent.type(screen.getByLabelText("Qty"), "50");
    await userEvent.type(screen.getByLabelText("Ingredient"), "grandma sauce");
    await userEvent.click(screen.getByRole("button", { name: "Save recipe" }));

    expect(await screen.findByText("We don't know these ingredients yet")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("kcal per 100 g"), "120");
    await userEvent.type(screen.getByLabelText("Protein g per 100 g"), "2");
    await userEvent.type(screen.getByLabelText("Carbs g per 100 g"), "15");
    await userEvent.type(screen.getByLabelText("Fat g per 100 g"), "6");
    await userEvent.click(screen.getByRole("button", { name: "Save nutrition" }));

    expect(api.addIngredient).toHaveBeenCalledWith({ name: "grandma sauce", kcal: 120, protein: 2, carbs: 15, fat: 6 });
    await vi.waitFor(() => expect(onSaved).toHaveBeenCalledWith({ ...COMPLETE, id: 10 }));
  });

  it("can skip nutrition and keep the incomplete recipe", async () => {
    const incomplete = { id: 11, title: "Mystery", complete: false, missing_nutrition: ["mystery"], macros_per_serving: null };
    api.createRecipe.mockResolvedValue(incomplete);
    const onSaved = vi.fn();
    render(<RecipeForm initial={{}} onSaved={onSaved} onCancel={() => {}} />);
    await userEvent.type(screen.getByLabelText("Title"), "Mystery");
    await userEvent.type(screen.getByLabelText("Qty"), "1");
    await userEvent.type(screen.getByLabelText("Ingredient"), "mystery");
    await userEvent.click(screen.getByRole("button", { name: "Save recipe" }));
    await userEvent.click(await screen.findByRole("button", { name: "Skip for now" }));
    expect(onSaved).toHaveBeenCalledWith(incomplete);
  });

  it("removes an ingredient row but never the last one", async () => {
    render(<RecipeForm initial={{}} onSaved={() => {}} onCancel={() => {}} />);
    expect(screen.getByRole("button", { name: "Remove ingredient 1" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "+ Add ingredient" }));
    await userEvent.click(screen.getByRole("button", { name: "Remove ingredient 2" }));
    expect(screen.getAllByLabelText("Qty")).toHaveLength(1);
  });

  it("shows server validation errors", async () => {
    api.createRecipe.mockRejectedValue(new Error("servings: Input should be greater than 0"));
    render(<RecipeForm initial={{}} onSaved={() => {}} onCancel={() => {}} />);
    await fillBasics();
    await userEvent.click(screen.getByRole("button", { name: "Save recipe" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("servings");
  });
});
