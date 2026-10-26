import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import MacroChips from "../components/MacroChips.jsx";
import { addDays, cap, dayLabel, formatMinutes, weekLabel } from "../format.js";

export function WeekNav({ week, setWeek }) {
  return (
    <div className="weeknav">
      <button aria-label="Previous week" onClick={() => setWeek(addDays(week, -7))}>‹</button>
      <strong>{weekLabel(week)}</strong>
      <button aria-label="Next week" onClick={() => setWeek(addDays(week, 7))}>›</button>
    </div>
  );
}

function PortionSheet({ member, portion, onClose, onSet }) {
  const servings = portion.servings;
  const step = (delta) => onSet({ servings: Math.min(4, Math.max(0.25, servings + delta)) });
  return (
    <div className="sheet" role="dialog" aria-modal="true" aria-label={`${member.name}'s portion`}>
      <div className="stack">
        <div className="row space">
          <h3>{member.name}'s portion</h3>
          <button onClick={onClose} aria-label="Close">✕</button>
        </div>
        <div className="row space">
          <button aria-label="Smaller portion" onClick={() => step(-0.25)} disabled={portion.skipped}>−</button>
          <strong aria-live="polite">{portion.skipped ? "Skipping" : `${servings} serving${servings === 1 ? "" : "s"}`}</strong>
          <button aria-label="Bigger portion" onClick={() => step(0.25)} disabled={portion.skipped}>+</button>
        </div>
        <div className="row">
          {portion.skipped ? (
            <button onClick={() => onSet({ skipped: false })}>Eat this meal</button>
          ) : (
            <button onClick={() => onSet({ skipped: true })}>Skip this meal</button>
          )}
          <button className="primary" onClick={onClose}>Done</button>
        </div>
      </div>
    </div>
  );
}

function SwapSheet({ day, slot, limits, onClose, onPick }) {
  const [options, setOptions] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api
      .recipes({ meal_type: slot.meal, difficulty: limits.difficulty, max_minutes: limits.minutes })
      .then((list) => setOptions(list.filter((r) => r.complete && r.id !== slot.recipe.id)))
      .catch((e) => setError(e.message));
  }, [slot, limits]);
  return (
    <div className="sheet" role="dialog" aria-modal="true" aria-label={`Swap ${slot.meal}`}>
      <div className="stack">
        <div className="row space">
          <h3>Swap {slot.meal} on {dayLabel(day)}</h3>
          <button onClick={onClose} aria-label="Close">✕</button>
        </div>
        {error && <p className="error" role="alert">{error}</p>}
        {options === null && <p className="muted">Loading…</p>}
        {options?.length === 0 && <p className="muted">No other recipes fit your limits.</p>}
        {options?.map((r) => (
          <button key={r.id} style={{ textAlign: "left", height: "auto", padding: 12 }} onClick={() => onPick(r.id)}>
            <strong>{r.title}</strong>
            <div className="badge-row">
              <span className={`chip ${r.difficulty}`}>{cap(r.difficulty)}</span>
              <span className="chip">⏱ {formatMinutes(r.total_minutes)}</span>
              <MacroChips macros={r.macros_per_serving} />
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function Day({ day, members, onPortion, onSwap }) {
  const byId = Object.fromEntries(members.map((m) => [m.id, m]));
  return (
    <section className="card day" aria-label={dayLabel(day.date)}>
      <h3>
        <span>{dayLabel(day.date)}</span>
        <span className="row">
          {day.slots.length > 0 && <span className="chip">⏱ {formatMinutes(day.cooking_minutes)}</span>}
          {day.off_target && <span className="chip warn" title="At least one person is more than 10% from their calorie target">Off target</span>}
        </span>
      </h3>
      {day.slots.length === 0 && <p className="muted small">Nothing planned.</p>}
      {day.slots.map((slot) => (
        <div className="slot" key={slot.meal}>
          <div className="row space">
            <span className="meal">{slot.meal}</span>
            <button className="link" onClick={() => onSwap(day.date, slot)}>Swap</button>
          </div>
          <strong>{slot.recipe.title}</strong>
          <div className="badge-row">
            <span className={`chip ${slot.recipe.difficulty}`}>{cap(slot.recipe.difficulty)}</span>
            <span className="chip">⏱ {formatMinutes(slot.recipe.total_minutes)}</span>
            <MacroChips macros={slot.recipe.macros_per_serving} />
          </div>
          <div className="badge-row" aria-label="Portions">
            {slot.portions.map((p) => (
              <button key={p.member_id} className="chip" onClick={() => onPortion(day.date, slot, byId[p.member_id], p)}
                aria-label={`${byId[p.member_id]?.name}: ${p.skipped ? "skipping" : `${p.servings} servings`}`}>
                {byId[p.member_id]?.name}: {p.skipped ? "skip" : `${p.servings}×`}
              </button>
            ))}
          </div>
        </div>
      ))}
      {day.totals.length > 0 && (
        <div className="totals">
          {day.totals.map((t) => {
            const m = byId[t.member_id];
            const pct = t.target_kcal ? Math.min(100, Math.round((t.kcal / t.target_kcal) * 100)) : 0;
            const off = t.error !== null && t.error > 0.1;
            return (
              <div key={t.member_id}>
                {m?.name}: {t.kcal}{t.target_kcal ? ` / ${t.target_kcal}` : ""} kcal · P {t.protein} · C {t.carbs} · F {t.fat}
                <div className={`bar ${off ? "off" : ""}`}><span style={{ width: `${pct}%` }} /></div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

export default function Plan({ week, setWeek }) {
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [difficulty, setDifficulty] = useState("easy");
  const [minutes, setMinutes] = useState(60);
  const [portionEdit, setPortionEdit] = useState(null); // {day, slot, member, portion}
  const [swap, setSwap] = useState(null); // {day, slot}

  const load = useCallback(() => {
    setError("");
    api.plan(week).then(setPlan).catch((e) => setError(e.message));
  }, [week]);
  useEffect(() => { load(); }, [load]);

  async function generate() {
    setBusy(true);
    setError("");
    try {
      setPlan(await api.generate({ week_start: week, max_difficulty: difficulty, max_minutes_per_day: Number(minutes) }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function setPortion(patch) {
    const { day, slot, member } = portionEdit;
    try {
      const next = await api.setPortion(day, slot.meal, { member_id: member.id, ...patch });
      setPlan(next);
      const fresh = next.days.find((d) => d.date === day).slots.find((s) => s.meal === slot.meal);
      setPortionEdit({ day, slot: fresh, member, portion: fresh.portions.find((p) => p.member_id === member.id) });
    } catch (e) {
      setError(e.message);
    }
  }

  async function pickSwap(recipeId) {
    try {
      setPlan(await api.swap(swap.day, swap.slot.meal, recipeId));
      setSwap(null);
    } catch (e) {
      setError(e.message);
    }
  }

  const planned = plan?.days.some((d) => d.slots.length > 0);

  return (
    <div className="stack">
      <h2>Weekly plan</h2>
      <WeekNav week={week} setWeek={setWeek} />
      <section className="card" aria-label="Plan limits">
        <div className="grid2">
          <div>
            <label htmlFor="pd">Recipes up to</label>
            <select id="pd" value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
              <option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option>
            </select>
          </div>
          <div>
            <label htmlFor="pm">Cooking per day</label>
            <select id="pm" value={minutes} onChange={(e) => setMinutes(e.target.value)}>
              <option value="30">30 min</option><option value="45">45 min</option><option value="60">1 hour</option>
              <option value="90">1.5 hours</option><option value="120">2 hours</option>
            </select>
          </div>
        </div>
        <button className="primary" style={{ width: "100%", marginTop: 12 }} disabled={busy} onClick={generate}>
          {busy ? "Planning…" : planned ? "Plan this week again" : "Plan this week"}
        </button>
      </section>
      {error && <p className="error" role="alert">{error}</p>}
      {plan && planned && (
        <p className="small muted">Total cooking this week: <strong>{formatMinutes(plan.weekly_cooking_minutes)}</strong>. Tap a name to change a portion.</p>
      )}
      {plan && !planned && !error && <p className="card muted">Nothing planned yet. Add family members, then plan the week.</p>}
      {plan?.days.map((d) => (
        <Day key={d.date} day={d} members={plan.members}
          onPortion={(day, slot, member, portion) => setPortionEdit({ day, slot, member, portion })}
          onSwap={(day, slot) => setSwap({ day, slot })} />
      ))}
      {portionEdit && (
        <PortionSheet member={portionEdit.member} portion={portionEdit.portion} onClose={() => setPortionEdit(null)} onSet={setPortion} />
      )}
      {swap && <SwapSheet day={swap.day} slot={swap.slot} limits={{ difficulty, minutes }} onClose={() => setSwap(null)} onPick={pickSwap} />}
    </div>
  );
}
