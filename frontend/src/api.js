// Thin fetch wrapper: JSON in/out, same-origin cookies, readable errors, and the last X-Trace-Id.

let lastTraceId = null;
const listeners = new Set();

export function getTraceId() {
  return lastTraceId;
}

export function onTraceId(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function describe(detail, status) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ");
  }
  return status >= 500 ? "Something went wrong on our side. Please try again." : `Request failed (${status})`;
}

export async function request(method, url, body) {
  let res;
  try {
    res = await fetch(url, {
      method,
      credentials: "same-origin",
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "You appear to be offline.");
  }
  const trace = res.headers.get("X-Trace-Id");
  if (trace) {
    lastTraceId = trace;
    listeners.forEach((fn) => fn(trace));
  }
  if (res.status === 204) return null;
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* empty or non-JSON body */
  }
  if (!res.ok) throw new ApiError(res.status, describe(data?.detail, res.status));
  return data;
}

const qs = (params) => {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && p.set(k, v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const api = {
  me: () => request("GET", "/api/auth/me"),
  signup: (b) => request("POST", "/api/auth/signup", b),
  login: (b) => request("POST", "/api/auth/login", b),
  logout: () => request("POST", "/api/auth/logout"),
  deleteHousehold: (password) => request("DELETE", "/api/auth/household", { password }),

  members: () => request("GET", "/api/members"),
  addMember: (b) => request("POST", "/api/members", b),
  updateMember: (id, b) => request("PUT", `/api/members/${id}`, b),
  deleteMember: (id) => request("DELETE", `/api/members/${id}`),

  recipes: (filters = {}) => request("GET", `/api/recipes${qs(filters)}`),
  recipe: (id) => request("GET", `/api/recipes/${id}`),
  createRecipe: (b) => request("POST", "/api/recipes", b),
  updateRecipe: (id, b) => request("PUT", `/api/recipes/${id}`, b),
  deleteRecipe: (id) => request("DELETE", `/api/recipes/${id}`),
  copyRecipe: (id) => request("POST", `/api/recipes/${id}/copy`),
  searchIngredients: (q) => request("GET", `/api/ingredients${qs({ q })}`),
  addIngredient: (b) => request("POST", "/api/ingredients", b),

  plan: (week) => request("GET", `/api/plan${qs({ week })}`),
  generate: (b) => request("POST", "/api/plan/generate", b),
  swap: (day, meal, recipe_id) => request("PUT", `/api/plan/${day}/${meal}`, { recipe_id }),
  setPortion: (day, meal, b) => request("PUT", `/api/plan/${day}/${meal}/portions`, b),

  shopping: (week) => request("GET", `/api/shopping-list${qs({ week })}`),
  check: (week, key, checked) => request("PUT", "/api/shopping-list/checks", { week, key, checked }),
};
