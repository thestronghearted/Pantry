import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import { cap, formatMinutes, formatQuantity } from "../format.js";
import MacroChips from "../components/MacroChips.jsx";
import RecipeForm from "./RecipeForm.jsx";

function RecipeDetail({ recipe, onClose, onChanged, onEdit }) {
  const [error, setError] = useState("");

  async function copy() {
    try {
      await api.copyRecipe(recipe.id);
      onChanged();
      onClose();
    } catch (e) {
      setError(e.message);
    }
  }
  async function remove() {
    if (!window.confirm(`Delete "${recipe.title}"?`)) return;
    try {
      await api.deleteRecipe(recipe.id);
      onChanged();
      onClose();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="sheet" role="dialog" aria-modal="true" aria-label={recipe.title}>
      <div className="stack">
        <div className="row space">
          <h2>{recipe.title}</h2>
          <button onClick={onClose} aria-label="Close">✕</button>
        </div>
        <div className="badge-row">
          <span className={`chip ${recipe.difficulty}`}>{cap(recipe.difficulty)}</span>
          <span className="chip">⏱ {formatMinutes(recipe.total_minutes)} (prep {recipe.prep_minutes}, cook {recipe.cook_minutes})</span>
          <span className="chip">{recipe.servings} servings</span>
        </div>
        <div className="badge-row" aria-label="Per serving"><MacroChips macros={recipe.macros_per_serving} /></div>
        {!recipe.complete && (
          <p className="notice">Missing nutrition for: {recipe.missing_nutrition.join(", ")}. This recipe is left out of automatic plans.</p>
        )}
        <h3>Ingredients</h3>
        <ul>
          {recipe.ingredients.map((i, n) => <li key={n}>{formatQuantity(i.quantity, i.unit)} {i.name}</li>)}
        </ul>
        {recipe.steps.length > 0 && (
          <>
            <h3>Method</h3>
            <ol>{recipe.steps.map((s, n) => <li key={n}>{s}</li>)}</ol>
          </>
        )}
        {error && <p className="error" role="alert">{error}</p>}
        <div className="row">
          {recipe.is_global ? (
            <button className="primary" onClick={copy}>Copy to my recipes</button>
          ) : (
            <>
              <button onClick={() => onEdit(recipe)}>Edit</button>
              <button className="danger" onClick={remove}>Delete</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Recipes() {
  const [recipes, setRecipes] = useState(null);
  const [filters, setFilters] = useState({ q: "", difficulty: "", max_minutes: "", meal_type: "" });
  const [open, setOpen] = useState(null);
  const [editing, setEditing] = useState(null); // null | {} | recipe
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api.recipes(filters).then(setRecipes).catch((e) => setError(e.message));
  }, [filters]);
  useEffect(() => { load(); }, [load]);

  const set = (key) => (e) => setFilters({ ...filters, [key]: e.target.value });

  if (editing) {
    return <RecipeForm initial={editing} onCancel={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />;
  }

  return (
    <div className="stack">
      <div className="row space">
        <h2>Recipes</h2>
        <button className="primary" onClick={() => setEditing({})}>New recipe</button>
      </div>
      <div className="card">
        <label htmlFor="rq">Search</label>
        <input id="rq" type="search" value={filters.q} onChange={set("q")} placeholder="e.g. chicken" />
        <div className="grid2">
          <div className="field">
            <label htmlFor="rd">Difficulty up to</label>
            <select id="rd" value={filters.difficulty} onChange={set("difficulty")}>
              <option value="">Any</option><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="rt">Time up to</label>
            <select id="rt" value={filters.max_minutes} onChange={set("max_minutes")}>
              <option value="">Any</option><option value="15">15 min</option><option value="30">30 min</option><option value="45">45 min</option><option value="60">1 hour</option>
            </select>
          </div>
        </div>
        <div className="field">
          <label htmlFor="rm">Meal</label>
          <select id="rm" value={filters.meal_type} onChange={set("meal_type")}>
            <option value="">Any</option><option value="breakfast">Breakfast</option><option value="lunch">Lunch</option><option value="dinner">Dinner</option><option value="snack">Snack</option>
          </select>
        </div>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {recipes === null && <p className="muted">Loading…</p>}
      {recipes?.length === 0 && <p className="card muted">No recipes match those filters.</p>}
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {recipes?.map((r) => (
          <li key={r.id} className="card">
            <button className="link" style={{ textAlign: "left", padding: 0, fontWeight: 600, fontSize: "1.05rem" }} onClick={() => setOpen(r)}>
              {r.title}
            </button>
            <div className="badge-row">
              <span className={`chip ${r.difficulty}`}>{cap(r.difficulty)}</span>
              <span className="chip">⏱ {formatMinutes(r.total_minutes)}</span>
              {!r.is_global && <span className="chip">Mine</span>}
              <MacroChips macros={r.macros_per_serving} />
            </div>
          </li>
        ))}
      </ul>
      {open && (
        <RecipeDetail
          recipe={open}
          onClose={() => setOpen(null)}
          onChanged={load}
          onEdit={(r) => { setOpen(null); setEditing(r); }}
        />
      )}
    </div>
  );
}
