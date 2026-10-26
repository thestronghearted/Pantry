# Pantry Plan — Product Specification

## Problem
Families trying to lose weight struggle to turn a calorie goal into a week of meals everyone will actually cook and eat. Plans built for one person ignore the rest of the household, recipes rarely show time or macros, and shopping lists get assembled by hand.

## What the system does
A household signs in and adds its members. For each member the app computes a daily calorie and macro target. It then **generates a week of meals** that respects a maximum difficulty and a maximum cooking time per day, gives each member a **portion sized to their own target**, and produces **one combined shopping list** that works on a phone in the shop.

Calorie and macro figures are estimates, not medical advice. The app shows this notice wherever targets appear.

## Users and context
- A household account (one shared email + password). Members are profiles, not logins.
- Used mostly on a phone: building the plan on the sofa, ticking items in the supermarket, entering recipes in the kitchen.

## Non-goals
Per-member logins, password reset by email, sharing recipes between households, barcode scanning, external nutrition APIs, weigh-in tracking.

## Conventions
- A plan covers one **week, Monday–Sunday**. Weeks are identified by their Monday date (`YYYY-MM-DD`).
- Meal slots: `breakfast`, `lunch`, `dinner` (snack is a recipe tag only).
- Difficulty: `easy < medium < hard`.
- Units: `g, kg, ml, l, tsp, tbsp, cup, piece`.

---

## F1 Household and login
- **F1.1** Sign up with household name, email, password (min 10 chars). Duplicate email → 409.
- **F1.2** Log in / log out. Session is a signed, httpOnly, `SameSite=Lax` cookie (`Secure` in production). Wrong credentials → 401 with no hint which field was wrong.
- **F1.3** Passwords are stored only as argon2 hashes.
- **F1.4** Every data endpoint requires a session (401 otherwise) and only ever touches the caller's household. A second household can never read, change or delete the first's data (404, not 403).
- **F1.5** More than 10 login/signup attempts per minute from one IP → 429.
- **F1.6** "Delete household" removes the household, members, plans, custom recipes, ticks and the user, after password confirmation.

## F2 Members and targets
- **F2.1** A household has 1–8 members: name, sex (`female|male`), age (years), height (cm), weight (kg), activity (`sedentary|light|moderate|active|very_active`), goal.
- **F2.2** Goal is `lose` (0.1–1.0 kg/week), `maintain`, or `custom` (explicit daily kcal).
- **F2.3** Members under 18 must use `custom`; the adult formula is refused with a clear message.
- **F2.4** Daily kcal for `lose`/`maintain` = Mifflin–St Jeor BMR × activity factor (1.2, 1.375, 1.55, 1.725, 1.9) − (kg/week × 7700 ÷ 7).
- **F2.5** Safety floor: never below 1500 kcal (male) / 1200 kcal (female). When the floor changes the result, the response says so and reports the effective kg/week.
- **F2.6** Macros: protein = min(1.8 g × weight, 35% of kcal ÷ 4); fat = 25% of kcal ÷ 9; carbs = the remaining kcal ÷ 4, never negative.
- **F2.7** Targets are returned with the "estimate, not medical advice" notice.

## F3 Recipes
- **F3.1** A recipe has title, servings, prep minutes, cook minutes, difficulty, meal types, ingredients (quantity, unit, name) and steps. Total time = prep + cook.
- **F3.2** Macros per serving are **computed** from ingredients using the nutrition table (per 100 g, from USDA FoodData Central, public domain). Volume units convert via per-ingredient density; `piece` via per-ingredient grams.
- **F3.3** The ingredient field autocompletes from the table (`GET /api/ingredients?q=`).
- **F3.4** An ingredient not in the table must be given kcal/protein/carbs/fat per 100 g; it is saved as a household custom ingredient. Alternatively the recipe carries a manual per-serving macro override.
- **F3.5** A recipe whose macros cannot be computed is marked `incomplete` and is **never auto-planned**.
- **F3.6** Global seed recipes (≥30, ≥6 easy per meal type) are read-only; "copy to my recipes" creates an editable household copy.
- **F3.7** A recipe used in any plan cannot be hard-deleted; it is archived (hidden from pickers, still shown in existing plans).
- **F3.8** Recipe list filters: difficulty, max total minutes, meal type, text.

## F4 Plan generator
- **F4.1** Inputs: week, meals per day (subset of breakfast/lunch/dinner), max difficulty, max cooking minutes per day, no-repeat window (days), and which members eat which meals.
- **F4.2** One recipe per slot, shared by the family. Only complete, non-archived recipes matching the meal type and difficulty are candidates; the day's total cooking time must not exceed the limit.
- **F4.3** Each member's daily target is split across the meals they eat (breakfast 25%, lunch 35%, dinner 40%, renormalised when a meal is skipped).
- **F4.4** A member's portion is a multiple of 0.25 servings, **between 0.5 and 2.0**, chosen to land closest to their meal target.
- **F4.5** Each member's day should land within ±10% of their daily target. A day that cannot is flagged `off_target`, keeps the closest option, and increments `plan_days_off_target_total`.
- **F4.6** Generation is deterministic for the same inputs and `seed`.
- **F4.7** The plan view shows per-member kcal/protein/carbs/fat per day against target, and total cooking minutes per day and per week.
- **F4.8** A member can be marked as skipping a meal; their portion becomes zero and the shopping list shrinks accordingly.
- **F4.9** Any slot can be swapped for another eligible recipe, and any portion edited by hand.

## F5 Shopping list (key user journey)
- **F5.1** `GET /api/shopping-list?week=` sums every ingredient across every planned meal × every member's portion ÷ recipe servings.
- **F5.2** Names are normalised (case, plural, aliases). Weights/volumes with a known density are merged in grams or millilitres; otherwise they stay as separate lines.
- **F5.3** Countable items (`piece`) are rounded **up** to whole units.
- **F5.4** Items are grouped by aisle (produce, dairy, meat & fish, pantry, frozen, other) and sorted by name.
- **F5.5** Ticking an item is stored per (household, week, item key) and survives reload and device change.
- **F5.6** A weekly list with no plan returns an empty list, not an error.

## F6 Mobile-first interface
- **F6.1** Works at 375 px width with no horizontal scroll; tap targets ≥ 44 px.
- **F6.2** Bottom tab bar: Plan, Recipes, Shopping, Family.
- **F6.3** Recipe entry is a single-column form with ingredient rows that add quickly.
- **F6.4** Each meal card shows time, difficulty, per-member portion chips and macros.
- **F6.5** The footer shows the trace id of the last journey request (`X-Trace-Id`), for support.

## F7 Operability requirements
- **F7.1** The key journey (**shopping list**) emits metrics, a trace and structured logs sharing one trace id; no emails, passwords, cookies, weights or ages appear in telemetry.
- **F7.2** An alert fires on real-user 5xx rate for the shopping list; synthetic probe traffic is excluded.
- **F7.3** The on-call Responder agent wakes on that alert, mitigates a known cause, verifies with a probe, and writes an incident report — or escalates.
- **F7.4** The whole system, including the database, starts with one command. CI runs tests on every PR; merges deploy to dev automatically and to prod after manual approval; rollback is one workflow.

## Success measures
- ≥ 95% of generated weeks have every member within ±10% on every day, with default seed recipes and default limits.
- Shopping-list requests succeed ≥ 99.5% (the SLO behind the alert).
- Shopping-list p95 latency < 1 s.
