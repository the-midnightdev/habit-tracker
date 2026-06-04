# Outcomes — design

## Summary

An "Outcomes" feature that reframes the planner from block-adherence to
outcome-progress. The user names an outcome they care about (e.g. "Sleep
better", "More energy"), links the recurring **block templates** that serve it,
rates each active outcome once a day with a single tap, and — once enough data
exists — sees cautious, timing-aware "signals" relating block adherence to those
ratings, each with a one-tap keep / tweak / drop suggestion.

The feature is **purely additive**. Existing template, day, check-in, reminder,
and push flows are untouched; Outcomes reuse the same JSON store, the same
load → mutate → save API shape, and the same React/shadcn UI patterns.

## Context: the model this adapts to

This app is a **time-blocking planner**, not a classic habit tracker. There is
no `Habit` entity. The relevant facts (`core.py`):

- One global recurring `template: list[TemplateBlock]`. Every date renders from
  it via `get_day_blocks` (`core.py:254`); there are no per-weekday schedules.
  **The template is the recurrence abstraction** — a template block recurs
  daily.
- Per-day deviations live in `Day.overrides: dict[start, Override]`, where
  `Override.state ∈ {pending, done, skipped}`. Marking a block `done` already
  records adherence; `skipped` records non-adherence.
- Template blocks are currently addressed by `start` time everywhere (override
  keys, `find_template_block`, routes `/api/template/{start}`). They have **no
  stable id**, so a link keyed by `start` would break when a block is edited.

Mapping decision (approved): **Outcomes link to block templates** (the recurring
unit); **scheduled instances supply adherence**, reusing the existing
`done`/`skipped` state.

### Adherence capture (approved)

Adherence is read from the data that already exists. For each linked block on a
given date: `done` → honored (1); `skipped` or unconfirmed `pending` → not
honored (0). This works retroactively over all history with **no new write
path** — correlation just reads `Override.state`.

The only quality gap is the ambiguous `pending` (untouched blocks are pruned and
read back as `pending` — done-but-not-tapped is indistinguishable from missed).
To improve confirmation quality, an **opt-in end-of-day review** lists today's
still-`pending` blocks for one-tap done/skip, reusing the existing
`CheckInModal` + push machinery (`DayView.jsx:108`) and the existing
`markBlock` endpoint. Until a block is confirmed it counts as **not honored**;
auto-confirming pending-as-done was rejected because it would inflate adherence
and bias the very correlations this feature surfaces.

## 1. Data model & migration (schema v4 → v5)

### Changes to existing types

```
TemplateBlock  +  id: str        # uuid hex, generated once. Stable link target.
                                 # `start` REMAINS the API/override addressing key — unchanged.

Day            +  outcome_checkins: dict[outcome_id, OutcomeCheckin]
                                 # one rating per outcome per day, enforced by the dict key
                                 # (mirrors how `overrides` is keyed by block start).
```

### New types

```
@dataclass
class Outcome:
    id: str                      # uuid hex
    name: str
    description: str
    direction: str               # "increase" | "decrease"  (intent/phrasing only)
    created: str                 # ISO date
    status: str                  # "active" | "archived"
    block_ids: list[str]         # M:N link -> TemplateBlock.id

@dataclass
class OutcomeCheckin:
    rating: int                  # 1..5, higher = better state of the outcome
    at: str                      # ISO-8601 timestamp
```

`PlannerData` gains `outcomes: list[Outcome]` alongside `template` and `days`.

### Linking semantics

- **M:N stored on the Outcome side** as `block_ids`. A block serves multiple
  outcomes simply by appearing in several outcomes' lists; storing one side
  avoids two-way sync bugs.
- **Orphan tolerance**: a `block_id` whose block was deleted is **inert and
  filtered at read**, exactly like an override whose `start` left the template
  (`core.py:256`). Deleting a template block does not cascade; it just drops out
  of insight computation.

### Migration

Bump `SCHEMA_VERSION` 4 → 5 (`core.py:13`). On loading a v4 file:

1. Assign a fresh `id` to every existing `TemplateBlock`.
2. Initialise `outcomes: []`.
3. Leave every existing `Day` untouched; `outcome_checkins` defaults to `{}`.

Migration is additive and lossless. v4 is still accepted on read (and upgraded
on next save), consistent with the existing v2/v3/v4 handling. The corrupt-file
backup path (`core.py:187`) is unchanged. Persistence keeps the existing
"don't write empty structures" discipline: outcomes with no check-ins add
nothing to a day; days with only an empty `outcome_checkins` are still pruned.

### Validation

- `direction ∈ {increase, decrease}`; `status ∈ {active, archived}` — raise the
  existing `ValidationError` otherwise.
- `rating` must be an integer 1–5.
- `name` non-empty after strip.

## 2. API (FastAPI, same load → mutate → save → payload shape)

```
GET    /api/outcomes                      -> [outcome + {checkedToday, todayRating}]
POST   /api/outcomes                      -> create (name, description, direction, block_ids)
PUT    /api/outcomes/{id}                 -> edit name/description/direction/status/block_ids
DELETE /api/outcomes/{id}                 -> remove
POST   /api/days/{date}/outcomes/{id}     -> upsert today's rating {rating}
GET    /api/outcomes/{id}/insights        -> confidence meter OR insight cards (computed on demand)
```

Mutations mirror existing endpoints: load the store, call a pure `core` helper,
catch `ValidationError` → HTTP 400, `save`, return the relevant payload. Unknown
ids → 404. The curated outcome list is a **frontend constant** — no endpoint.

## 3. Onboarding / UX flow

Navigation: add a third tab to `App.jsx`'s `Tabs` — **Day / Template /
Outcomes**. State stays plain local `useState`/`useEffect` over `api.js`
wrappers; no new state library.

### Create wizard (`OutcomeWizard.jsx`, Radix dialog like `BlockDialog`)

1. **Name it.** Curated chips (*Sleep better, Less anxious, More energy, More
   focus, Move more, Eat better*) each carrying a default `direction` and a
   check-in question, plus a **custom** option (free name + direction picker).
2. **Link blocks.** Multi-select over existing template blocks ("Which parts of
   your day serve this?"), plus **"Add an experiment"** which opens the existing
   `BlockDialog` to create a new template block framed as an experiment. Either
   path appends a `TemplateBlock.id` to `block_ids`.

### Daily check-in surface (`OutcomeCheckinCard.jsx`, in Day view, today only)

One compact row per **active** outcome: the question + a 1–5 tap scale (higher =
better). A tap writes immediately (`POST /api/days/{date}/outcomes/{id}`) and the
row collapses to its rating, re-tappable to change. No modal, no submit — the
<5-second requirement. One rating per outcome per day (dict-key enforced). Shown
only when viewing today and at least one active outcome exists.

`direction` never flips the scale; curated questions are phrased so 5 is always
the good end (e.g. "Less anxious" → "How calm did you feel today?").

## 4. Insights engine (`outcomes.py`, pure, on demand)

A new IO-free module mirroring `core.py`'s style, called by
`GET /api/outcomes/{id}/insights`. **Computed on demand** — single-user, ≤6
weeks of data is tiny, so no scheduled job (a cache can be added later if ever
needed; YAGNI now).

### Feature extraction

Trailing **6 weeks** (42 days) ending today. For each active outcome, build a
per-day series: `{ date, rating }` for days with a check-in, joined to features
derived from that day's linked-block adherence and each block's template
`start`/`end`:

- **adherence** per linked block (done = 1; skipped or unconfirmed-`pending` =
  0), evaluated at **lag 0, 1, 2 days** against the rating;
- **time-of-day bucket** (morning / afternoon / evening from `start`);
- **duration** (`end − start`);
- **day-of-week**;
- **latest honored end-time** per day (enables "blocks ending after 9pm"
  shapes).

### Statistic

Rank candidate signals by correlation strength over the series, then **express
the winner as a group mean-delta** so the surfaced sentence is concrete and
honest:

- *"Energy averaged +1.2 on weeks with 3+ morning deep-work blocks."*
- *"Sleep ratings ran lower on days with blocks ending after 9pm — a signal
  worth watching."*

Correlation is used only to *select* the strongest candidate; the *displayed*
number is always the plain mean-delta between the high and low groups.

### Guardrails

- **Threshold gate:** fewer than **14 days of check-ins** OR fewer than **10
  linked completions** → return a confidence meter
  `{ daysChecked, completions, ready: false }`, never an insight.
- **Cautious, non-causal language:** phrasing templates use "pattern" /
  "signal" / "averaged"; never "causes", "improves", "because". Lag > 0 surfaces
  as "the day after".
- **Null result:** sufficient data but no signal clears the strength bar →
  an empathetic alternative-experiment message, not a negative verdict
  ("No clear pattern yet — want to try moving this block earlier and watch for
  two weeks?").
- Each insight ends with a **keep / tweak / drop** suggestion and a one-tap
  action (`InsightCard.jsx`): *keep* = no-op acknowledgement; *tweak* = open the
  block in `BlockDialog`; *drop* = unlink the block from the outcome.

### Module shape (testable seams)

```
trailing_window(today, weeks=6) -> (start_date, end_date)
build_series(data, outcome, today) -> list[DayPoint]      # rating + features, lag-aware
candidate_signals(series) -> list[Signal]                 # feature, strength, n, mean_delta, lag
select_signal(signals, min_strength) -> Signal | None
confidence(series) -> {daysChecked, completions, ready}
phrase(signal | None, outcome) -> InsightCard             # cautious copy + suggestion
```

## 5. Frontend components

- `OutcomesView.jsx` — tab body: list of outcome cards, create button, per-card
  insight area; empty state launches the wizard.
- `OutcomeWizard.jsx` — the two-step create flow above.
- `OutcomeCheckinCard.jsx` — the <5s daily rating surface in Day view.
- `InsightCard.jsx` — renders either the confidence meter or an insight +
  keep/tweak/drop action.
- `EndOfDayReview.jsx` — opt-in surface (reusing `CheckInModal`) that lists
  today's still-`pending` blocks for one-tap done/skip, improving adherence
  confirmation quality. Writes through the existing `markBlock` endpoint; adds
  no new write path.
- `web/src/api.js` — add `getOutcomes`, `createOutcome`, `updateOutcome`,
  `deleteOutcome`, `rateOutcome`, `getInsights`.
- Curated-outcome constants live in a small frontend module (e.g.
  `web/src/lib/outcomes.js`).

## 6. Privacy considerations (flagged)

- Outcome ratings are **mood-like data stored in plaintext** in
  `~/.plan/data.json`, the same local, single-user, unencrypted threat model as
  existing planner data. No new network egress: insights are computed
  server-side **locally**.
- **Hard rule the design enforces:** push payloads must **never** include
  outcome ratings or insight text. The existing push path
  (`push_active_block`) stays block-only; the Outcomes feature adds nothing to
  it.
- No third-party analytics, no remote sync. If remote sync is ever added, mood
  ratings should be treated as sensitive and encrypted at rest — out of scope
  here, noted for the future.

## 7. Testing (TDD)

### Backend — `tests/test_outcomes.py` (correlation logic, the priority)

Edge cases required by the constraints:

- **Below threshold / sparse data** → `ready: false`, no insight emitted.
- **All-same ratings** (zero variance) → no signal, no division-by-zero.
- **All-same adherence** (block always done / never done) → that feature is
  skipped, no false signal.
- **Single linked block** → still produces a valid (or null) result.
- **Empty 6-week window** / no check-ins → confidence meter, not a crash.
- **Lag windows running off the start of history** → ignored cleanly.
- **Happy path** → known fixture yields the expected mean-delta sentence and
  the expected keep/tweak/drop suggestion.
- **Null result with sufficient data** → empathetic alternative message, no
  causal/negative wording.

### Backend — `tests/test_core.py` additions

- v4 → v5 migration assigns block ids, initialises `outcomes`, preserves days.
- Outcome create/edit/archive/delete; `block_ids` validation and orphan
  filtering when a linked block is removed.
- One-per-day rating upsert; rating validation (1–5).

### Backend — `tests/test_api.py` additions

- Each new endpoint: success, 400 on bad input, 404 on unknown id.

### Frontend — Vitest

- `OutcomeCheckinCard.test.jsx` — one tap rates and collapses; re-tap changes.
- `OutcomeWizard.test.jsx` — curated vs custom; linking existing blocks vs
  creating an experiment block.
- `InsightCard.test.jsx` — renders confidence meter below threshold; renders
  insight + keep/tweak/drop above it; copy contains no causal verbs.
- `EndOfDayReview.test.jsx` — lists only today's still-`pending` blocks; a tap
  marks done/skip via `markBlock`; nothing pending → renders nothing.
- `api.test.js` — new client wrappers hit the right URLs/methods.

## 8. Out of scope (YAGNI)

- Scheduled/cron insight precomputation (compute on demand; cache later if
  needed).
- Per-weekday templates or block recurrence rules (the model has none today).
- AI-generated insight copy (phrasing is templated; a seam can be added like the
  existing check-in `composeCheckIn` AI seam).
- Remote sync / multi-user / encryption at rest.
- Retroactively backfilling adherence for *historical* `pending` days (only
  today's pending blocks are surfaced by the end-of-day review; past unconfirmed
  blocks stay not-honored).
