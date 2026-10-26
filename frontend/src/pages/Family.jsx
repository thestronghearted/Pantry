import { useEffect, useState } from "react";
import { api } from "../api.js";

const BLANK = {
  name: "", sex: "female", age: 35, height_cm: 168, weight_kg: 70, activity: "light",
  goal: "lose", kg_per_week: 0.5, custom_kcal: 2000,
};
const ACTIVITY = [
  ["sedentary", "Mostly sitting"],
  ["light", "Light activity (1-3 days/week)"],
  ["moderate", "Moderate (3-5 days/week)"],
  ["active", "Active (6-7 days/week)"],
  ["very_active", "Very active / physical job"],
];

function MemberForm({ initial, onSaved, onCancel }) {
  const [m, setM] = useState({ ...BLANK, ...initial });
  const [error, setError] = useState("");
  const under18 = Number(m.age) < 18;
  const goal = under18 ? "custom" : m.goal;
  const set = (key) => (e) => setM({ ...m, [key]: e.target.value });

  async function save(e) {
    e.preventDefault();
    setError("");
    const body = {
      name: m.name, sex: m.sex, age: Number(m.age), height_cm: Number(m.height_cm), weight_kg: Number(m.weight_kg),
      activity: m.activity, goal,
      kg_per_week: goal === "lose" ? Number(m.kg_per_week) : null,
      custom_kcal: goal === "custom" ? Number(m.custom_kcal) : null,
    };
    try {
      const saved = m.id ? await api.updateMember(m.id, body) : await api.addMember(body);
      onSaved(saved);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form className="card" onSubmit={save} aria-label={m.id ? "Edit member" : "Add member"}>
      <h3>{m.id ? "Edit family member" : "Add a family member"}</h3>
      <div className="field">
        <label htmlFor="m-name">Name</label>
        <input id="m-name" required maxLength={60} value={m.name} onChange={set("name")} />
      </div>
      <div className="grid2">
        <div className="field">
          <label htmlFor="m-sex">Sex (for the calorie formula)</label>
          <select id="m-sex" value={m.sex} onChange={set("sex")}>
            <option value="female">Female</option>
            <option value="male">Male</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="m-age">Age</label>
          <input id="m-age" type="number" inputMode="numeric" min="1" max="110" required value={m.age} onChange={set("age")} />
        </div>
        <div className="field">
          <label htmlFor="m-height">Height (cm)</label>
          <input id="m-height" type="number" inputMode="decimal" min="51" max="259" required value={m.height_cm} onChange={set("height_cm")} />
        </div>
        <div className="field">
          <label htmlFor="m-weight">Weight (kg)</label>
          <input id="m-weight" type="number" inputMode="decimal" min="11" max="399" step="0.1" required value={m.weight_kg} onChange={set("weight_kg")} />
        </div>
      </div>
      <div className="field">
        <label htmlFor="m-activity">Activity</label>
        <select id="m-activity" value={m.activity} onChange={set("activity")}>
          {ACTIVITY.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>
      <div className="field">
        <label htmlFor="m-goal">Goal</label>
        <select id="m-goal" value={goal} disabled={under18} onChange={set("goal")}>
          <option value="lose">Lose weight</option>
          <option value="maintain">Maintain weight</option>
          <option value="custom">Set calories myself</option>
        </select>
        {under18 && <p className="notice">Adult calorie formulas do not apply under 18. Enter a daily calorie target (ask a doctor or dietitian).</p>}
      </div>
      {goal === "lose" && (
        <div className="field">
          <label htmlFor="m-rate">Weight to lose per week (kg, 0.1 to 1.0)</label>
          <input id="m-rate" type="number" inputMode="decimal" step="0.1" min="0.1" max="1" required value={m.kg_per_week} onChange={set("kg_per_week")} />
        </div>
      )}
      {goal === "custom" && (
        <div className="field">
          <label htmlFor="m-kcal">Daily calories</label>
          <input id="m-kcal" type="number" inputMode="numeric" min="800" max="5000" required value={m.custom_kcal} onChange={set("custom_kcal")} />
        </div>
      )}
      {error && <p className="error" role="alert">{error}</p>}
      <div className="row field">
        <button className="primary" type="submit">Save</button>
        <button type="button" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

function Targets({ t }) {
  if (!t) return null;
  return (
    <div>
      <div className="badge-row" aria-label="Daily targets">
        <span className="chip"><strong>{t.kcal}</strong>&nbsp;kcal</span>
        <span className="chip">P {t.protein_g} g</span>
        <span className="chip">C {t.carbs_g} g</span>
        <span className="chip">F {t.fat_g} g</span>
      </div>
      {t.adjusted && (
        <p className="notice">
          Your goal was adjusted to about {t.effective_kg_per_week} kg per week so daily calories stay above the safe minimum.
        </p>
      )}
      <p className="small muted">{t.notice}</p>
    </div>
  );
}

export default function Family({ session, onSignOut, onDeleted }) {
  const [members, setMembers] = useState(null);
  const [editing, setEditing] = useState(null); // null | {} (new) | member
  const [error, setError] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [password, setPassword] = useState("");

  const load = () => api.members().then(setMembers).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  async function remove(m) {
    if (!window.confirm(`Remove ${m.name}? Their planned portions are removed too.`)) return;
    await api.deleteMember(m.id).catch((e) => setError(e.message));
    load();
  }

  async function deleteAll(e) {
    e.preventDefault();
    setError("");
    try {
      await api.deleteHousehold(password);
      onDeleted();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="stack">
      <div className="row space">
        <h2>Family</h2>
        {!editing && <button className="primary" onClick={() => setEditing({})}>Add person</button>}
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {editing && (
        <MemberForm initial={editing} onCancel={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />
      )}
      {members === null && <p className="muted">Loading…</p>}
      {members?.length === 0 && !editing && <p className="card muted">Add everyone who eats at your table to get calorie targets and a plan.</p>}
      {members?.map((m) => (
        <section className="card" key={m.id} aria-label={m.name}>
          <div className="row space">
            <h3>{m.name}</h3>
            <span className="row">
              <button className="link" onClick={() => setEditing(m)}>Edit</button>
              <button className="link danger" onClick={() => remove(m)}>Remove</button>
            </span>
          </div>
          <p className="small muted">{m.age} y, {m.weight_kg} kg, {m.height_cm} cm</p>
          <Targets t={m.targets} />
        </section>
      ))}

      <section className="card stack" aria-label="Account">
        <h3>Account</h3>
        <p className="small muted">Signed in as {session.email}</p>
        <div className="row">
          <button onClick={onSignOut}>Log out</button>
          {!confirm && <button className="danger" onClick={() => setConfirm(true)}>Delete household…</button>}
        </div>
        {confirm && (
          <form onSubmit={deleteAll} className="stack">
            <p className="notice">This permanently deletes your household, family members, recipes, plans and shopping ticks.</p>
            <label htmlFor="del-pw">Confirm with your password</label>
            <input id="del-pw" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
            <div className="row">
              <button className="danger" type="submit">Delete everything</button>
              <button type="button" onClick={() => setConfirm(false)}>Cancel</button>
            </div>
          </form>
        )}
      </section>
    </div>
  );
}
