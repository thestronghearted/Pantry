import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../src/api.js", async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    api: {
      me: vi.fn(), logout: vi.fn(), plan: vi.fn(), recipes: vi.fn(), shopping: vi.fn(), members: vi.fn(),
      login: vi.fn(), signup: vi.fn(),
    },
  };
});
import { api, ApiError } from "../src/api.js";
import App from "../src/App.jsx";

beforeEach(() => {
  Object.values(api).forEach((fn) => fn.mockReset());
  api.plan.mockResolvedValue({ week_start: "x", members: [], days: [], weekly_cooking_minutes: 0 });
  api.recipes.mockResolvedValue([]);
  api.shopping.mockResolvedValue({ items: [] });
  api.members.mockResolvedValue([]);
});

describe("App", () => {
  it("shows the sign-in screen when there is no session", async () => {
    api.me.mockRejectedValue(new ApiError(401, "Not signed in"));
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Log in" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  });

  it("shows the four tabs once signed in and switches between them", async () => {
    api.me.mockResolvedValue({ household: { id: 1, name: "Smiths" }, email: "a@example.com" });
    render(<App />);
    const nav = within(await screen.findByRole("navigation", { name: "Main" }));
    for (const name of ["Plan", "Recipes", "Shopping", "Family"]) {
      expect(nav.getByRole("button", { name: new RegExp(name) })).toBeInTheDocument();
    }
    expect(nav.getByRole("button", { name: /Plan/ })).toHaveAttribute("aria-current", "page");

    await userEvent.click(nav.getByRole("button", { name: /Shopping/ }));
    expect(await screen.findByRole("heading", { name: "Shopping list" })).toBeInTheDocument();
    expect(nav.getByRole("button", { name: /Shopping/ })).toHaveAttribute("aria-current", "page");

    await userEvent.click(nav.getByRole("button", { name: /Family/ }));
    expect(await screen.findByRole("heading", { name: "Family" })).toBeInTheDocument();
  });

  it("signs out back to the login screen", async () => {
    api.me.mockResolvedValue({ household: { id: 1, name: "Smiths" }, email: "a@example.com" });
    api.logout.mockResolvedValue(null);
    render(<App />);
    const nav = within(await screen.findByRole("navigation", { name: "Main" }));
    await userEvent.click(nav.getByRole("button", { name: /Family/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Log out" }));
    expect(await screen.findByRole("heading", { name: "Log in" })).toBeInTheDocument();
  });
});
