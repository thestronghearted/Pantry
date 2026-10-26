// Date and quantity helpers. Weeks run Monday-Sunday and are identified by their Monday (YYYY-MM-DD).

const pad = (n) => String(n).padStart(2, "0");

export function toIso(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function parseIso(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function mondayOf(date = new Date()) {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  return toIso(d);
}

export function addDays(iso, days) {
  const d = parseIso(iso);
  d.setDate(d.getDate() + days);
  return toIso(d);
}

export function dayLabel(iso) {
  return parseIso(iso).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
}

export function weekLabel(iso) {
  const end = parseIso(addDays(iso, 6));
  const start = parseIso(iso);
  const f = (d) => d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
  return `${f(start)} - ${f(end)}`;
}

export function formatMinutes(total) {
  if (total < 60) return `${total} min`;
  const h = Math.floor(total / 60);
  const m = total % 60;
  return m ? `${h} h ${m} min` : `${h} h`;
}

const UNIT_LABEL = { piece: "", g: " g", kg: " kg", ml: " ml", l: " l", tsp: " tsp", tbsp: " tbsp", cup: " cup" };

export function formatQuantity(quantity, unit) {
  const q = Number.isInteger(quantity) ? String(quantity) : String(Math.round(quantity * 100) / 100);
  return `${q}${UNIT_LABEL[unit] ?? ` ${unit}`}`;
}

export const AISLES = [
  ["produce", "Fruit & veg"],
  ["dairy", "Dairy & eggs"],
  ["meat_fish", "Meat & fish"],
  ["pantry", "Cupboard"],
  ["frozen", "Frozen"],
  ["other", "Other"],
];

export const MEALS = ["breakfast", "lunch", "dinner"];
export const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
