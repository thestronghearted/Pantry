import { useState } from "react";
import { api } from "../api.js";
import { cap } from "../format.js";
import MacroChips from "../components/MacroChips.jsx";

const UNITS = ["g", "kg", "ml", "l", "tsp", "tbsp", "cup", "piece"];
const MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"];
const blankLine = () => ({ quantity: "", unit: "g", name: "" });

function NutritionPrompt({ names, onDone }) {
  const [values, setValues] = useState(() =>
    Object.fromEntries(names.map((n) => [n, { kcal: "", protein: "", carbs: "", fat: "" }])),
  );
  const [error, setError] = useState("");

  const set = (name, key) => (e) => setValues({ ...values, [name]: { ...values[name], [key]: e.target.value } });

  async function save(e) {
    e.preventDefault();
    setError("");
    try {
      for (const name of names) {
        const v = values[name];
        await api.addIngredient({
          name, kcal: Number(v.kcal), protein: Number(v.protein), carbs: Number(v.carbs), fat: Number(v.fat),
        });
      }
      onDone();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form className="card stack" onSubmit={save} aria-label="Add nutrition">
      <h3>We don't know these ingredients yet</h3>
      <p className="small muted">Enter nutrition per 100 g (check the packet). Until then this recipe is left out of automatic plans.</p>
      {names.map((n) => (
        <fieldset key={n} style={{ border: 0, padding: 0, margin: 0 }}>
          <legend><strong>{n}</strong></legend>
          <div className="grid2">
            {[["kcal", "kcal"], ["protein", "Protein g"], ["carbs", "Carbs g"], ["fat", "Fat g"]].map(([k, label]) => (
              <div key={k}>
                <label htmlFor={`${n}-${k}`}>{label} per 100 g</label>
                <input id={`${n}-${k}`} type="number" inputMode="decimal" min="0" step="0.1" required value={values[n][k]} onChange={set(n, k)} />
              </div>
            ))}
          </div>
        </fieldset>
      ))}
      {error && <p className="error" role="alert">{error}</p>}
      <div className="row">
        <button className="primary" type="submit">Save nutrition</button>
        <button type="button" onClick={() => onDone(true)}>Skip for now</button>
      </div>
    </form>
  );
}

export default function RecipeForm({ initial, onSaved, onCancel }) {
  const editing = Boolean(initial.id);
  const [r, setR] = useState({
    title: initial.title ?? "",
    servings: initial.servings ?? 2,
    prep_minutes: initial.prep_minutes ?? 10,
    cook_minutes: initial.cook_minutes ?? 20,
    difficulty: initial.difficulty ?? "easy",
    meal_types: initial.meal_types ?? ["dinner"],
    ingredients: initial.ingredients?.length ? initial.ingredients : [blankLine()],
    steps: (initial.steps ?? []).join("\n"),
  });
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(null); // recipe returned by the server (to show macros / missing data)
  const [suggestions, setSuggestions] = useState([]);

  const setField = (key) => (e) => setR({ ...r, [key]: e.target.value });
  const setLine = (i, key) => (e) => {
    const ingredients = r.ingredients.map((l, n) => (n === i ? { ...l, [key]: e.target.value } : l));
    setR({ ...r, ingredients });
    if (key === "name" && e.target.value.length >= 2) {
      api.searchIngredients(e.target.value).then((list) => setSuggestions(list.map((x) => x.name))).catch(() => {});
    }
  };
  const toggleMeal = (m) =>
    setR({ ...r, meal_types: r.meal_types.includes(m) ? r.meal_types.filter((x) => x !== m) : [...r.meal_types, m] });

  async function submit(e) {
    e.preventDefault();
    setError("");
    const body = {
      title: r.title,
      servings: Number(r.servings),
      prep_minutes: Number(r.prep_minutes),
      cook_minutes: Number(r.cook_minutes),
      difficulty: r.difficulty,
      meal_types: r.meal_types,
      ingredients: r.ingredients
        .filter((l) => l.name.trim())
        .map((l) => ({ name: l.name.trim(), quantity: Number(l.quantity), unit: l.unit })),
      steps: r.steps.split("\n"),
    };
    try {
      const result = editing ? await api.updateRecipe(initial.id, body) : await api.createRecipe(body);
      if (result.complete) onSaved(result);
      else setSaved(result);
    } catch (err) {
      setError(err.message);
    }
  }

  if (saved) {
    return (
      <div className="stack">
        <p className="notice">Saved "{saved.title}", but it has no nutrition data for some ingredients.</p>
        <NutritionPrompt names={saved.missing_nutrition} onDone={(skipped) => (skipped ? onSaved(saved) : api.recipe(saved.id).then(onSaved))} />
      </div>
    );
  }

  return (
    <form className="stack" onSubmit={submit} aria-label={editing ? "Edit recipe" : "New recipe"}>
      <h2>{editing ? "Edit recipe" : "New recipe"}</h2>
      <div className="field">
        <label htmlFor="r-title">Title</label>
        <input id="r-title" required maxLength={120} value={r.title} onChange={setField("title")} />
      </div>
      <div className="grid2">
        <div className="field">
          <label htmlFor="r-serv">Servings</label>
          <input id="r-serv" type="number" inputMode="decimal" min="0.5" step="0.5" required value={r.servings} onChange={setField("servings")} />
        </div>
        <div className="field">
          <label htmlFor="r-diff">Difficulty</label>
          <select id="r-diff" value={r.difficulty} onChange={setField("difficulty")}>
            {["easy", "medium", "hard"].map((d) => <option key={d} value={d}>{cap(d)}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="r-prep">Prep (minutes)</label>
          <input id="r-prep" type="number" inputMode="numeric" min="0" required value={r.prep_minutes} onChange={setField("prep_minutes")} />
        </div>
        <div className="field">
          <label htmlFor="r-cook">Cook (minutes)</label>
          <input id="r-cook" type="number" inputMode="numeric" min="0" required value={r.cook_minutes} onChange={setField("cook_minutes")} />
        </div>
      </div>
      <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
        <legend className="small muted">Good for</legend>
        <div className="row">
          {MEAL_TYPES.map((m) => (
            <label key={m} className="row" style={{ gap: 6 }}>
              <input type="checkbox" checked={r.meal_types.includes(m)} onChange={() => toggleMeal(m)} /> {cap(m)}
            </label>
          ))}
        </div>
      </fieldset>

      <section aria-label="Ingredients">
        <h3>Ingredients</h3>
        <datalist id="ingredient-suggestions">{suggestions.map((s) => <option key={s} value={s} />)}</datalist>
        {r.ingredients.map((l, i) => (
          <div className="ing-row" key={i}>
            <div>
              <label htmlFor={`q${i}`}>Qty</label>
              <input id={`q${i}`} type="number" inputMode="decimal" min="0" step="any" value={l.quantity} onChange={setLine(i, "quantity")} />
            </div>
            <div>
              <label htmlFor={`u${i}`}>Unit</label>
              <select id={`u${i}`} value={l.unit} onChange={setLine(i, "unit")}>{UNITS.map((u) => <option key={u}>{u}</option>)}</select>
            </div>
            <div>
              <label htmlFor={`n${i}`}>Ingredient</label>
              <input id={`n${i}`} list="ingredient-suggestions" value={l.name} onChange={setLine(i, "name")} autoComplete="off" />
            </div>
            <button type="button" aria-label={`Remove ingredient ${i + 1}`} disabled={r.ingredients.length === 1}
              onClick={() => setR({ ...r, ingredients: r.ingredients.filter((_, n) => n !== i) })}>✕</button>
          </div>
        ))}
        <button type="button" style={{ marginTop: 10 }} onClick={() => setR({ ...r, ingredients: [...r.ingredients, blankLine()] })}>
          + Add ingredient
        </button>
      </section>

      <div className="field">
        <label htmlFor="r-steps">Method (one step per line)</label>
        <textarea id="r-steps" value={r.steps} onChange={setField("steps")} />
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="row">
        <button className="primary" type="submit">Save recipe</button>
        <button type="button" onClick={onCancel}>Cancel</button>
      </div>
      {initial.macros_per_serving && (
        <div className="badge-row" aria-label="Current macros per serving"><MacroChips macros={initial.macros_per_serving} /></div>
      )}
    </form>
  );
}
