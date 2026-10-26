import { useState } from "react";
import { api } from "../api.js";

export default function Auth({ onSignedIn }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ household_name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const session =
        mode === "login"
          ? await api.login({ email: form.email, password: form.password })
          : await api.signup(form);
      onSignedIn(session);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app" style={{ paddingBottom: 24 }}>
      <main className="stack">
        <h1 style={{ color: "var(--brand)", marginTop: 32 }}>Pantry Plan</h1>
        <p className="muted">Weekly family meals that fit everyone's calorie goal, with one shopping list.</p>
        <form className="card" onSubmit={submit} aria-label={mode === "login" ? "Log in" : "Create household"}>
          <h2>{mode === "login" ? "Log in" : "Create your household"}</h2>
          {mode === "signup" && (
            <div className="field">
              <label htmlFor="household">Household name</label>
              <input id="household" required maxLength={100} value={form.household_name} onChange={set("household_name")} />
            </div>
          )}
          <div className="field">
            <label htmlFor="email">E-mail</label>
            <input id="email" type="email" autoComplete="email" required value={form.email} onChange={set("email")} />
          </div>
          <div className="field">
            <label htmlFor="password">Password {mode === "signup" && "(at least 10 characters)"}</label>
            <input
              id="password"
              type="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
              minLength={mode === "signup" ? 10 : 1}
              value={form.password}
              onChange={set("password")}
            />
          </div>
          {error && <p className="error" role="alert">{error}</p>}
          <div className="row space field">
            <button className="primary grow" disabled={busy} type="submit">
              {mode === "login" ? "Log in" : "Create household"}
            </button>
          </div>
          <p className="small muted">
            {mode === "login" ? "New here?" : "Already have a household?"}{" "}
            <button type="button" className="link" onClick={() => { setMode(mode === "login" ? "signup" : "login"); setError(""); }}>
              {mode === "login" ? "Create a household" : "Log in"}
            </button>
          </p>
        </form>
      </main>
    </div>
  );
}
