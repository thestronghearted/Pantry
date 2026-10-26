import { useCallback, useEffect, useState } from "react";
import { api, getTraceId, onTraceId } from "./api.js";
import { mondayOf } from "./format.js";
import Auth from "./pages/Auth.jsx";
import Family from "./pages/Family.jsx";
import Plan from "./pages/Plan.jsx";
import Recipes from "./pages/Recipes.jsx";
import Shopping from "./pages/Shopping.jsx";

const TABS = [
  ["plan", "Plan", "🗓"],
  ["recipes", "Recipes", "🍳"],
  ["shopping", "Shopping", "🛒"],
  ["family", "Family", "👨‍👩‍👧"],
];

export default function App() {
  const [session, setSession] = useState(undefined); // undefined = loading, null = signed out
  const [tab, setTab] = useState("plan");
  const [week, setWeek] = useState(() => mondayOf());
  const [trace, setTrace] = useState(getTraceId());

  useEffect(() => onTraceId(setTrace), []);

  useEffect(() => {
    api
      .me()
      .then(setSession)
      .catch(() => setSession(null)); // 401 or offline: show the sign-in screen
  }, []);

  const signOut = useCallback(async () => {
    await api.logout().catch(() => {});
    setSession(null);
  }, []);

  if (session === undefined) return <p className="center muted">Loading…</p>;
  if (session === null) return <Auth onSignedIn={setSession} />;

  return (
    <div className="app">
      <header className="topbar">
        <h1>Pantry Plan</h1>
        <span className="muted small">{session.household.name}</span>
      </header>
      <main>
        {tab === "plan" && <Plan week={week} setWeek={setWeek} />}
        {tab === "recipes" && <Recipes />}
        {tab === "shopping" && <Shopping week={week} setWeek={setWeek} />}
        {tab === "family" && <Family session={session} onSignOut={signOut} onDeleted={() => setSession(null)} />}
      </main>
      <footer className="trace small muted" aria-label="Support information">
        {trace ? <>Trace id: <code data-testid="trace-id">{trace}</code></> : "Estimates only, not medical advice."}
      </footer>
      <nav className="tabbar" aria-label="Main">
        {TABS.map(([id, label, icon]) => (
          <button key={id} className={tab === id ? "active" : ""} aria-current={tab === id ? "page" : undefined} onClick={() => setTab(id)}>
            <span aria-hidden="true">{icon}</span>
            {label}
          </button>
        ))}
      </nav>
    </div>
  );
}
