import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../src/api.js", async (importOriginal) => ({
  ...(await importOriginal()),
  api: { shopping: vi.fn(), check: vi.fn() },
}));
import { api, ApiError } from "../src/api.js";
import Shopping from "../src/pages/Shopping.jsx";

const WEEK = "2026-11-02";
const ITEMS = [
  { key: "tomato|piece", name: "tomato", quantity: 6, unit: "piece", aisle: "produce", checked: false },
  { key: "egg|piece", name: "egg", quantity: 12, unit: "piece", aisle: "dairy", checked: true },
  { key: "brown rice|g", name: "brown rice", quantity: 750, unit: "g", aisle: "pantry", checked: false },
];

beforeEach(() => {
  api.shopping.mockReset();
  api.check.mockReset();
  api.check.mockResolvedValue(null);
});

describe("Shopping", () => {
  it("groups items by aisle with quantities and a progress count", async () => {
    api.shopping.mockResolvedValue({ items: ITEMS });
    render(<Shopping week={WEEK} setWeek={() => {}} />);

    expect(await screen.findByRole("heading", { name: "Fruit & veg" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Dairy & eggs" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Cupboard" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Frozen" })).not.toBeInTheDocument();
    expect(screen.getByText("750 g")).toBeInTheDocument();
    expect(screen.getByText("1 of 3 ticked")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /egg/ })).toBeChecked();
  });

  it("ticks an item instantly and saves it", async () => {
    api.shopping.mockResolvedValue({ items: ITEMS });
    render(<Shopping week={WEEK} setWeek={() => {}} />);
    const box = await screen.findByRole("checkbox", { name: /tomato/ });

    await userEvent.click(box);

    expect(box).toBeChecked();
    expect(screen.getByText("2 of 3 ticked")).toBeInTheDocument();
    expect(api.check).toHaveBeenCalledWith(WEEK, "tomato|piece", true);
  });

  it("falls back to the last list saved on the phone when offline", async () => {
    api.shopping.mockResolvedValueOnce({ items: ITEMS });
    const { unmount } = render(<Shopping week={WEEK} setWeek={() => {}} />);
    await screen.findByText("tomato");
    unmount();

    api.shopping.mockRejectedValue(new ApiError(0, "You appear to be offline."));
    render(<Shopping week={WEEK} setWeek={() => {}} />);

    expect(await screen.findByText("tomato")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("offline");
  });

  it("keeps a tick made offline on screen", async () => {
    api.shopping.mockResolvedValue({ items: ITEMS });
    api.check.mockRejectedValue(new ApiError(0, "offline"));
    render(<Shopping week={WEEK} setWeek={() => {}} />);
    const box = await screen.findByRole("checkbox", { name: /tomato/ });
    await userEvent.click(box);
    await waitFor(() => expect(api.check).toHaveBeenCalled());
    expect(box).toBeChecked();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows a friendly empty state", async () => {
    api.shopping.mockResolvedValue({ items: [] });
    render(<Shopping week={WEEK} setWeek={() => {}} />);
    expect(await screen.findByText(/No list yet/)).toBeInTheDocument();
  });

  it("shows server errors without losing the page", async () => {
    api.shopping.mockRejectedValue(new ApiError(500, "Something went wrong on our side. Please try again."));
    render(<Shopping week={WEEK} setWeek={() => {}} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
  });

  it("changes week with the arrows", async () => {
    api.shopping.mockResolvedValue({ items: [] });
    const setWeek = vi.fn();
    render(<Shopping week={WEEK} setWeek={setWeek} />);
    await userEvent.click(await screen.findByRole("button", { name: "Next week" }));
    expect(setWeek).toHaveBeenCalledWith("2026-11-09");
  });
});
