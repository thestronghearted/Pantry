import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import { AISLES, formatQuantity } from "../format.js";
import { WeekNav } from "./Plan.jsx";

const cacheKey = (week) => `pantry.shopping.${week}`;

function readCache(week) {
  try {
    return JSON.parse(localStorage.getItem(cacheKey(week)));
  } catch {
    return null;
  }
}
function writeCache(week, data) {
  try {
    localStorage.setItem(cacheKey(week), JSON.stringify(data));
  } catch {
    /* storage full or unavailable: the list still works online */
  }
}

export default function Shopping({ week, setWeek }) {
  const [items, setItems] = useState(null);
  const [offline, setOffline] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    setOffline(false);
    try {
      const data = await api.shopping(week);
      setItems(data.items);
      writeCache(week, data.items);
    } catch (e) {
      const cached = readCache(week);
      if (e.status === 0 && cached) {
        setItems(cached);
        setOffline(true);
      } else {
        setItems([]);
        setError(e.message);
      }
    }
  }, [week]);

  useEffect(() => {
    setItems(null);
    load();
  }, [load]);

  async function toggle(item) {
    const checked = !item.checked;
    const next = items.map((i) => (i.key === item.key ? { ...i, checked } : i));
    setItems(next); // optimistic: ticking must feel instant in the shop
    writeCache(week, next);
    try {
      await api.check(week, item.key, checked);
    } catch (e) {
      if (e.status !== 0) setError(e.message);
    }
  }

  const done = items?.filter((i) => i.checked).length ?? 0;

  return (
    <div className="stack">
      <h2>Shopping list</h2>
      <WeekNav week={week} setWeek={setWeek} />
      {offline && <p className="notice" role="status">You're offline. Showing the last list saved on this phone.</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {items === null && <p className="muted">Loading…</p>}
      {items?.length === 0 && !error && <p className="card muted">No list yet. Plan the week first and everything you need appears here.</p>}
      {items?.length > 0 && <p className="small muted" aria-live="polite">{done} of {items.length} ticked</p>}
      {AISLES.map(([aisle, label]) => {
        const inAisle = items?.filter((i) => i.aisle === aisle) ?? [];
        if (inAisle.length === 0) return null;
        return (
          <section className="aisle" key={aisle} aria-label={label}>
            <h3>{label}</h3>
            {inAisle.map((item) => (
              <label key={item.key} className={`item ${item.checked ? "done" : ""}`} style={{ color: "inherit", fontSize: "1rem" }}>
                <input type="checkbox" checked={item.checked} onChange={() => toggle(item)} />
                <span className="name">{item.name}</span>
                <span className="qty">{formatQuantity(item.quantity, item.unit)}</span>
              </label>
            ))}
          </section>
        );
      })}
    </div>
  );
}
