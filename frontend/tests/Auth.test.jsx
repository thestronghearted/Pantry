import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../src/api.js", async (importOriginal) => ({
  ...(await importOriginal()),
  api: { login: vi.fn(), signup: vi.fn() },
}));
import { api, ApiError } from "../src/api.js";
import Auth from "../src/pages/Auth.jsx";

beforeEach(() => {
  api.login.mockReset();
  api.signup.mockReset();
});

describe("Auth", () => {
  it("logs in and hands the session to the app", async () => {
    const session = { household: { id: 1, name: "Smiths" }, email: "a@example.com" };
    api.login.mockResolvedValue(session);
    const onSignedIn = vi.fn();
    render(<Auth onSignedIn={onSignedIn} />);

    await userEvent.type(screen.getByLabelText("E-mail"), "a@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "correct-horse-battery");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));

    expect(api.login).toHaveBeenCalledWith({ email: "a@example.com", password: "correct-horse-battery" });
    expect(onSignedIn).toHaveBeenCalledWith(session);
  });

  it("shows the server's message for wrong credentials", async () => {
    api.login.mockRejectedValue(new ApiError(401, "Incorrect e-mail or password"));
    render(<Auth onSignedIn={() => {}} />);
    await userEvent.type(screen.getByLabelText("E-mail"), "a@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "nope");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect e-mail or password");
  });

  it("switches to sign-up and sends the household name", async () => {
    api.signup.mockResolvedValue({ household: { id: 2, name: "Joneses" }, email: "b@example.com" });
    render(<Auth onSignedIn={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: "Create a household" }));

    await userEvent.type(screen.getByLabelText("Household name"), "Joneses");
    await userEvent.type(screen.getByLabelText("E-mail"), "b@example.com");
    await userEvent.type(screen.getByLabelText(/Password/), "a-long-enough-password");
    await userEvent.click(screen.getByRole("button", { name: "Create household" }));

    expect(api.signup).toHaveBeenCalledWith({
      household_name: "Joneses", email: "b@example.com", password: "a-long-enough-password",
    });
  });
});
