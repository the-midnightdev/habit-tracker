# shadcn Redesign + Live-Template Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the snapshot-on-write day model with a live-template + per-day-overrides model (fixing the "today shows a stale block" bug), and rebuild the web UI with shadcn/ui as a light/emerald Dashboard.

**Architecture:** `core.py` renders each day from the *current* template, applying per-day overrides keyed by block start; storage moves to schema v3 with a v2→v3 migration. `api.py` and `cli.py` are unchanged (they already work through `get_day_blocks`/`set_block_*`). The `web/` SPA is rebuilt on Tailwind + shadcn/ui.

**Tech Stack:** Python 3.13, FastAPI, pytest; React + Vite + Vitest; Tailwind CSS + shadcn/ui (Radix), lucide-react, sonner.

**Spec:** `docs/superpowers/specs/2026-05-24-shadcn-redesign-and-live-template-model-design.md`

**Conventions:**
- Times `"HH:MM"` 24h zero-padded (string compare = chronological). States `"pending"|"done"|"skipped"`. Dates ISO `YYYY-MM-DD`.
- Run Python commands from repo root `D:\habit-tracker`; run web commands from `D:\habit-tracker\web`.
- The day shape returned by the API/core stays `{start, end, label, state}` — only *storage* and *rendering source* change.

---

## Phase A: Backend — live-template model (core.py)

### Task A1: New data types and v3 storage round-trip

**Files:**
- Modify: `core.py`
- Modify: `tests/test_core.py`

- [ ] **Step 1: Replace the day/storage tests**

In `tests/test_core.py`, the round-trip test currently builds `Day(blocks=[DayBlock(...)])`. Replace the existing `test_save_then_load_round_trips` function with:

```python
def test_save_then_load_round_trips(data_dir: Path):
    data = PlannerData(
        template=[TemplateBlock(start="08:00", end="09:00", label="standup")],
        days={
            "2026-05-24": Day(
                overrides={"08:00": Override(state="done", label="fixed bug")}
            )
        },
    )
    DataStore(data_dir).save(data)
    assert DataStore(data_dir).load() == data
```

Update the imports at the top of `tests/test_core.py` to include `Override` (and keep `Day`, `DayBlock`, `TemplateBlock`, `PlannerData`, `DataStore`):

```python
from core import (
    DataStore,
    Day,
    DayBlock,
    Override,
    PlannerData,
    TemplateBlock,
)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_core.py::test_save_then_load_round_trips -v`
Expected: FAIL — `ImportError: cannot import name 'Override'` (or `Day` no longer accepts `overrides`).

- [ ] **Step 3: Update the data types and DataStore in `core.py`**

Replace the `DayBlock`/`Day`/`PlannerData` dataclasses and the `DataStore` `load`/`save` bodies. The new dataclasses:

```python
@dataclass
class TemplateBlock:
    start: str
    end: str
    label: str


@dataclass
class DayBlock:
    """A rendered block for a given day (template fields + resolved state/label)."""
    start: str
    end: str
    label: str
    state: str = "pending"


@dataclass
class Override:
    """A per-day deviation for one block, keyed externally by start time."""
    state: str = "pending"
    label: str | None = None


@dataclass
class Day:
    overrides: dict[str, Override] = field(default_factory=dict)


@dataclass
class PlannerData:
    template: list[TemplateBlock] = field(default_factory=list)
    days: dict[str, Day] = field(default_factory=dict)
```

Set `SCHEMA_VERSION = 3`. Replace `DataStore.load` and `DataStore.save`:

```python
    def load(self, on_corrupt: Callable[[Path], None] | None = None) -> PlannerData:
        if not self.path.exists():
            return PlannerData()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("root is not an object")
            version = raw.get("version")
            template = [TemplateBlock(**b) for b in raw["template"]]
            if version == SCHEMA_VERSION:
                days = {
                    d: Day(overrides={
                        start: Override(**ov) for start, ov in day["overrides"].items()
                    })
                    for d, day in raw["days"].items()
                }
            elif version == 2:
                days = _migrate_v2_days(raw["days"], template)
            else:
                raise ValueError(f"unsupported schema version: {version!r}")
            return PlannerData(template=template, days=days)
        except (json.JSONDecodeError, ValueError, TypeError, KeyError):
            backup = self._backup_corrupt()
            if on_corrupt is not None:
                on_corrupt(backup)
            return PlannerData()

    def save(self, data: PlannerData) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        days_payload = {}
        for d, day in data.days.items():
            overrides = {}
            for start, ov in day.overrides.items():
                entry = {"state": ov.state}
                if ov.label is not None:
                    entry["label"] = ov.label
                overrides[start] = entry
            days_payload[d] = {"overrides": overrides}
        payload = {
            "version": SCHEMA_VERSION,
            "template": [asdict(b) for b in data.template],
            "days": days_payload,
        }
        self.path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
```

Add the migration helper (place it just above the `DataStore` class or just below it, module level):

```python
def _migrate_v2_days(raw_days: dict, template: list[TemplateBlock]) -> dict[str, Day]:
    """Convert v2 day snapshots to v3 overrides: keep a block only if it has a
    non-pending state or a label that differs from the current template default."""
    template_by_start = {b.start: b for b in template}
    days: dict[str, Day] = {}
    for date_iso, day in raw_days.items():
        overrides: dict[str, Override] = {}
        for blk in day.get("blocks", []):
            start = blk["start"]
            state = blk.get("state", "pending")
            label = blk.get("label")
            tb = template_by_start.get(start)
            keep_label = tb is not None and label is not None and label != tb.label
            if state != "pending" or keep_label:
                overrides[start] = Override(
                    state=state, label=label if keep_label else None
                )
        if overrides:
            days[date_iso] = Day(overrides=overrides)
    return days
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_core.py::test_save_then_load_round_trips tests/test_core.py::test_load_returns_empty_when_file_missing tests/test_core.py::test_save_creates_parent_directory -v`
Expected: PASS (3 tests). Other tests in the file may still fail — they're updated in later tasks.

- [ ] **Step 5: Commit**

```bash
git add core.py tests/test_core.py
git commit -m "feat: v3 storage with per-day overrides and v2 migration"
```

### Task A2: v2→v3 migration and corrupt-recovery tests

**Files:**
- Modify: `tests/test_core.py`

- [ ] **Step 1: Update the v1 test and add migration tests**

The existing `test_v1_schema_is_rejected_as_corrupt` stays valid (v1 still rejected). Append new tests:

```python
def test_v2_file_is_migrated_to_overrides(data_dir: Path):
    # A v2 file with a done block and a stale (no-longer-in-template) pending block.
    (data_dir / "data.json").write_text(json.dumps({
        "version": 2,
        "template": [{"start": "13:00", "end": "14:00", "label": "break"}],
        "days": {
            "2026-05-24": {"blocks": [
                {"start": "13:00", "end": "14:00", "label": "break", "state": "done"},
                {"start": "11:55", "end": "13:00", "label": "work", "state": "pending"},
            ]},
        },
    }), encoding="utf-8")
    data = DataStore(data_dir).load()
    # Done block kept as an override; stale pending block dropped.
    assert data.days["2026-05-24"].overrides == {"13:00": Override(state="done")}


def test_v2_migration_keeps_custom_label_override(data_dir: Path):
    (data_dir / "data.json").write_text(json.dumps({
        "version": 2,
        "template": [{"start": "13:00", "end": "14:00", "label": "break"}],
        "days": {
            "2026-05-24": {"blocks": [
                {"start": "13:00", "end": "14:00", "label": "long lunch", "state": "pending"},
            ]},
        },
    }), encoding="utf-8")
    data = DataStore(data_dir).load()
    assert data.days["2026-05-24"].overrides == {
        "13:00": Override(state="pending", label="long lunch")
    }
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/test_core.py -k "migrat or corrupt or v1" -v`
Expected: PASS. The corrupt and v1 tests still pass (recovery unchanged); both migration tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_core.py
git commit -m "test: cover v2->v3 migration"
```

### Task A3: Render days from the live template + override mutations

**Files:**
- Modify: `core.py`
- Modify: `tests/test_core.py`

- [ ] **Step 1: Replace the day-behavior tests**

In `tests/test_core.py`, **delete** the old snapshot-model test
`test_editing_template_does_not_touch_already_materialized_day` and the old
`test_set_block_state_materializes_day_and_persists_state`. Replace them and the
surrounding day tests with the following set (keep `_template_data` as defined earlier in
the file — it adds 08:00 standup and 09:00 code):

```python
def test_get_day_blocks_renders_untouched_day_from_template_as_pending():
    data = _template_data()
    blocks = get_day_blocks(data, "2026-05-24")
    assert [b.start for b in blocks] == ["08:00", "09:00"]
    assert all(b.state == "pending" for b in blocks)
    assert "2026-05-24" not in data.days  # reading never writes


def test_set_block_state_stores_override_and_renders():
    data = _template_data()
    set_block_state(data, "2026-05-24", "08:00", "done")
    blocks = get_day_blocks(data, "2026-05-24")
    assert blocks[0].state == "done"
    assert blocks[1].state == "pending"


def test_set_block_state_rejects_unknown_state():
    data = _template_data()
    with pytest.raises(ValidationError):
        set_block_state(data, "2026-05-24", "08:00", "maybe")


def test_set_block_state_rejects_block_not_in_template():
    data = _template_data()
    with pytest.raises(ValidationError):
        set_block_state(data, "2026-05-24", "11:00", "done")


def test_set_block_label_overrides_for_that_day_only():
    data = _template_data()
    set_block_label(data, "2026-05-24", "08:00", "fixed login bug")
    assert get_day_blocks(data, "2026-05-24")[0].label == "fixed login bug"
    assert get_day_blocks(data, "2026-05-25")[0].label == "standup"


def test_set_block_label_rejects_block_not_in_template():
    data = _template_data()
    with pytest.raises(ValidationError):
        set_block_label(data, "2026-05-24", "11:00", "nope")


def test_adding_template_block_appears_on_a_day_with_existing_marks():
    # THE BUG FIX: a day with overrides still reflects later template additions.
    data = _template_data()
    set_block_state(data, "2026-05-24", "08:00", "done")  # day now has an override
    add_template_block(data, "10:00", "11:00", "review")
    blocks = get_day_blocks(data, "2026-05-24")
    assert [b.start for b in blocks] == ["08:00", "09:00", "10:00"]
    assert blocks[0].state == "done"      # existing mark preserved
    assert blocks[2].state == "pending"   # new block shows up, pending


def test_removing_template_block_makes_its_override_inert():
    data = _template_data()
    set_block_state(data, "2026-05-24", "09:00", "skipped")
    remove_template_block(data, "09:00")
    blocks = get_day_blocks(data, "2026-05-24")
    assert [b.start for b in blocks] == ["08:00"]  # 09:00 gone everywhere


def test_setting_state_back_to_pending_clears_override():
    data = _template_data()
    set_block_state(data, "2026-05-24", "08:00", "done")
    set_block_state(data, "2026-05-24", "08:00", "pending")
    assert "2026-05-24" not in data.days  # tidy: empty day removed


def test_history_dates_sorted():
    data = _template_data()
    set_block_state(data, "2026-05-25", "08:00", "done")
    set_block_state(data, "2026-05-24", "08:00", "done")
    assert history_dates(data) == ["2026-05-24", "2026-05-25"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_core.py::test_adding_template_block_appears_on_a_day_with_existing_marks -v`
Expected: FAIL — current `get_day_blocks`/mutations use the old snapshot model.

- [ ] **Step 3: Replace the day functions in `core.py`**

Remove the old `_blocks_from_template`, `_materialize`, `_find_day_block`,
`get_day_blocks`, `set_block_state`, `set_block_label`, `history_dates` and replace with:

```python
def get_day_blocks(data: PlannerData, date_iso: str) -> list[DayBlock]:
    """Render a day from the CURRENT template, applying that day's overrides.

    Overrides whose start is no longer in the template are inert (ignored).
    Reading never mutates `data`.
    """
    overrides = data.days[date_iso].overrides if date_iso in data.days else {}
    blocks = []
    for tb in data.template:
        ov = overrides.get(tb.start)
        state = ov.state if ov is not None else "pending"
        label = ov.label if (ov is not None and ov.label is not None) else tb.label
        blocks.append(DayBlock(start=tb.start, end=tb.end, label=label, state=state))
    return blocks


def _require_template_start(data: PlannerData, start: str) -> None:
    if find_template_block(data, start) is None:
        raise ValidationError(f"no template block starts at {start!r}")


def _override(data: PlannerData, date_iso: str, start: str) -> Override:
    day = data.days.setdefault(date_iso, Day())
    return day.overrides.setdefault(start, Override())


def _prune(data: PlannerData, date_iso: str, start: str) -> None:
    day = data.days.get(date_iso)
    if day is None:
        return
    ov = day.overrides.get(start)
    if ov is not None and ov.state == "pending" and ov.label is None:
        del day.overrides[start]
    if not day.overrides:
        data.days.pop(date_iso, None)


def set_block_state(data: PlannerData, date_iso: str, start: str, state: str) -> None:
    if state not in STATES:
        raise ValidationError(f"unknown state {state!r}; expected one of {STATES}")
    _require_template_start(data, start)
    _override(data, date_iso, start).state = state
    _prune(data, date_iso, start)


def set_block_label(data: PlannerData, date_iso: str, start: str, label: str) -> None:
    _require_template_start(data, start)
    _override(data, date_iso, start).label = label


def history_dates(data: PlannerData) -> list[str]:
    return sorted(d for d, day in data.days.items() if day.overrides)
```

- [ ] **Step 4: Run the full core suite**

Run: `python -m pytest tests/test_core.py -v`
Expected: PASS (all core tests, including the resolver and template tests untouched by this change).

- [ ] **Step 5: Commit**

```bash
git add core.py tests/test_core.py
git commit -m "feat: render days from live template with per-day overrides"
```

### Task A4: Confirm API and CLI still pass under the new model

**Files:**
- Modify: `tests/test_api.py` (add one regression test)

- [ ] **Step 1: Add an API regression test for the bug fix**

Append to `tests/test_api.py`:

```python
def test_added_template_block_shows_on_a_day_with_existing_marks(client):
    client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "standup"})
    client.post("/api/days/2026-05-24/blocks/08:00", json={"state": "done"})
    client.post("/api/template", json={"start": "10:00", "end": "11:00", "label": "review"})
    blocks = client.get("/api/days/2026-05-24").json()["blocks"]
    assert [b["start"] for b in blocks] == ["08:00", "10:00"]
    assert blocks[0]["state"] == "done"
    assert blocks[1]["state"] == "pending"
```

- [ ] **Step 2: Run the whole Python suite**

Run: `python -m pytest -q`
Expected: PASS — `test_core.py`, `test_cli.py`, `test_api.py` all green. `api.py` and `cli.py` need no changes (they operate through `get_day_blocks`/`set_block_*`). If any CLI/API test fails, fix the test only if it encoded the old snapshot semantics; do not reintroduce snapshots.

- [ ] **Step 3: Commit**

```bash
git add tests/test_api.py
git commit -m "test: API regression for live-template day rendering"
```

---

## Phase B: Frontend tooling — Tailwind + shadcn/ui

### Task B1: Install and configure Tailwind + path alias

**Files:**
- Modify: `web/package.json` (via npm install)
- Create: `web/tailwind.config.js`, `web/postcss.config.js`, `web/src/index.css`, `web/jsconfig.json`, `web/src/lib/utils.js`
- Modify: `web/vite.config.js`, `web/src/main.jsx`
- Delete: `web/src/styles.css`

- [ ] **Step 1: Install dependencies**

Run (from `web/`):
```bash
npm install -D tailwindcss@^3.4 postcss autoprefixer
npm install class-variance-authority clsx tailwind-merge tailwindcss-animate lucide-react
```
Expected: installs without ERR.

- [ ] **Step 2: Create `web/tailwind.config.js`**

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: { DEFAULT: "hsl(var(--primary))", foreground: "hsl(var(--primary-foreground))" },
        secondary: { DEFAULT: "hsl(var(--secondary))", foreground: "hsl(var(--secondary-foreground))" },
        destructive: { DEFAULT: "hsl(var(--destructive))", foreground: "hsl(var(--destructive-foreground))" },
        muted: { DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" },
        accent: { DEFAULT: "hsl(var(--accent))", foreground: "hsl(var(--accent-foreground))" },
        popover: { DEFAULT: "hsl(var(--popover))", foreground: "hsl(var(--popover-foreground))" },
        card: { DEFAULT: "hsl(var(--card))", foreground: "hsl(var(--card-foreground))" },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
```

- [ ] **Step 3: Create `web/postcss.config.js`**

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 4: Create `web/src/index.css` (light + emerald theme tokens)**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222 47% 11%;
    --card: 0 0% 100%;
    --card-foreground: 222 47% 11%;
    --popover: 0 0% 100%;
    --popover-foreground: 222 47% 11%;
    --primary: 160 84% 39%;            /* emerald */
    --primary-foreground: 0 0% 100%;
    --secondary: 210 40% 96%;
    --secondary-foreground: 222 47% 11%;
    --muted: 210 40% 96%;
    --muted-foreground: 215 16% 47%;
    --accent: 152 76% 95%;
    --accent-foreground: 160 84% 25%;
    --destructive: 0 72% 51%;
    --destructive-foreground: 0 0% 100%;
    --border: 214 32% 91%;
    --input: 214 32% 91%;
    --ring: 160 84% 39%;
    --radius: 0.6rem;
  }
}

@layer base {
  * { @apply border-border; }
  body { @apply bg-background text-foreground; }
}
```

- [ ] **Step 5: Create `web/jsconfig.json` (path alias for `@/`)**

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  }
}
```

- [ ] **Step 6: Create `web/src/lib/utils.js`**

```javascript
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 7: Add the `@/` alias to `web/vite.config.js`**

Replace the file with:

```javascript
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test-setup.js",
  },
});
```

- [ ] **Step 8: Point `main.jsx` at the new stylesheet and remove the old one**

In `web/src/main.jsx`, change `import "./styles.css";` to `import "./index.css";`. Then delete the old stylesheet:
```bash
git rm web/src/styles.css
```

- [ ] **Step 9: Verify the toolchain builds**

Run (from `web/`): `npm run build`
Expected: Vite build completes with no errors (Tailwind processes `index.css`). Components still reference the old `styles.css` classes via className strings — that's fine, they're rebuilt in Phase C; the build only needs to compile.

- [ ] **Step 10: Commit**

```bash
git add web/package.json web/package-lock.json web/tailwind.config.js web/postcss.config.js web/src/index.css web/jsconfig.json web/src/lib/utils.js web/vite.config.js web/src/main.jsx
git commit -m "chore(web): add Tailwind + theme tokens + @ alias"
```

### Task B2: Generate shadcn/ui components

**Files:**
- Create: `web/components.json`, `web/src/components/ui/*`

- [ ] **Step 1: Create `web/components.json`** (so the shadcn CLI knows the project config)

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": false,
  "tsx": false,
  "tailwind": {
    "config": "tailwind.config.js",
    "css": "src/index.css",
    "baseColor": "slate",
    "cssVariables": true
  },
  "aliases": { "components": "@/components", "utils": "@/lib/utils", "ui": "@/components/ui" }
}
```

- [ ] **Step 2: Add components via the shadcn CLI (non-interactive)**

Run (from `web/`):
```bash
npx --yes shadcn@latest add -y button card badge progress tabs dialog input label sonner
```
Expected: creates `web/src/components/ui/{button,card,badge,progress,tabs,dialog,input,label,sonner}.jsx` and installs the Radix/sonner deps. (If the CLI prompts despite `-y`, or has no network, report BLOCKED — the controller will supply the component sources manually.)

- [ ] **Step 3: Verify the components exist and the app builds**

Run (from `web/`):
```bash
ls src/components/ui
npm run build
```
Expected: the listed `.jsx` files are present; build still succeeds.

- [ ] **Step 4: Commit**

```bash
git add web/components.json web/src/components/ui web/package.json web/package-lock.json
git commit -m "chore(web): add shadcn/ui components"
```

---

## Phase C: Frontend rebuild

Note: these components import shadcn primitives from `@/components/ui/...`. The API client (`web/src/api.js`) is unchanged.

### Task C1: App shell with Tabs + Toaster

**Files:**
- Modify: `web/src/App.jsx`
- Modify: `web/src/App.test.jsx`

- [ ] **Step 1: Update the test**

Replace `web/src/App.test.jsx` with:

```jsx
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import App from "./App.jsx";
import * as api from "./api.js";

afterEach(() => vi.restoreAllMocks());

test("shows the day view by default and switches to template", async () => {
  vi.spyOn(api, "getDay").mockResolvedValue({ date: "2026-05-24", blocks: [] });
  vi.spyOn(api, "getTemplate").mockResolvedValue([]);
  render(<App />);
  expect(screen.getByRole("tab", { name: /day/i })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: /template/i }));
  // Assert on the always-present "Add block" button rather than a heading —
  // shadcn's CardTitle may render a <div>, so role="heading" is unreliable.
  expect(await screen.findByRole("button", { name: /add block/i })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `web/`): `npm test -- App`
Expected: FAIL — App still renders plain buttons (`role="button"`, not `role="tab"`), or imports break.

- [ ] **Step 3: Rewrite `web/src/App.jsx`**

```jsx
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Toaster } from "@/components/ui/sonner";
import DayView from "./DayView.jsx";
import TemplateEditor from "./TemplateEditor.jsx";

export default function App() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">Time-Blocking Planner</h1>
      <Tabs defaultValue="day">
        <TabsList className="mb-4">
          <TabsTrigger value="day">Day</TabsTrigger>
          <TabsTrigger value="template">Template</TabsTrigger>
        </TabsList>
        <TabsContent value="day">
          <DayView />
        </TabsContent>
        <TabsContent value="template">
          <TemplateEditor />
        </TabsContent>
      </Tabs>
      <Toaster richColors position="top-center" />
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `web/`): `npm test -- App`
Expected: PASS. (DayView/TemplateEditor are rebuilt in later tasks; their current versions still render, so the shell test passes.)

- [ ] **Step 5: Commit**

```bash
git add web/src/App.jsx web/src/App.test.jsx
git commit -m "feat(web): shadcn Tabs shell with Toaster"
```

### Task C2: BlockRow with shadcn Done/Skip + inline label edit

**Files:**
- Modify: `web/src/BlockRow.jsx`
- Modify: `web/src/BlockRow.test.jsx`

- [ ] **Step 1: Replace the test**

Replace `web/src/BlockRow.test.jsx` with:

```jsx
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import BlockRow from "./BlockRow.jsx";

afterEach(() => vi.restoreAllMocks());

const block = { start: "08:00", end: "09:00", label: "standup", state: "pending" };

test("renders time range and label", () => {
  render(<BlockRow block={block} onMark={() => {}} />);
  expect(screen.getByText("08:00–09:00")).toBeInTheDocument();
  expect(screen.getByText("standup")).toBeInTheDocument();
});

test("Done calls onMark with done", () => {
  const onMark = vi.fn();
  render(<BlockRow block={block} onMark={onMark} />);
  fireEvent.click(screen.getByRole("button", { name: /done/i }));
  expect(onMark).toHaveBeenCalledWith("08:00", { state: "done" });
});

test("clicking Done on a done block resets to pending", () => {
  const onMark = vi.fn();
  render(<BlockRow block={{ ...block, state: "done" }} onMark={onMark} />);
  fireEvent.click(screen.getByRole("button", { name: /done/i }));
  expect(onMark).toHaveBeenCalledWith("08:00", { state: "pending" });
});

test("Skip calls onMark with skipped", () => {
  const onMark = vi.fn();
  render(<BlockRow block={block} onMark={onMark} />);
  fireEvent.click(screen.getByRole("button", { name: /skip/i }));
  expect(onMark).toHaveBeenCalledWith("08:00", { state: "skipped" });
});

test("editing the label submits once on blur", () => {
  const onMark = vi.fn();
  render(<BlockRow block={block} onMark={onMark} />);
  fireEvent.click(screen.getByText("standup"));
  const input = screen.getByDisplayValue("standup");
  fireEvent.change(input, { target: { value: "fixed bug" } });
  fireEvent.blur(input);
  expect(onMark).toHaveBeenCalledTimes(1);
  expect(onMark).toHaveBeenCalledWith("08:00", { label: "fixed bug" });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `web/`): `npm test -- BlockRow`
Expected: FAIL — current BlockRow uses old markup/classes; imports of shadcn Button not present yet.

- [ ] **Step 3: Rewrite `web/src/BlockRow.jsx`**

```jsx
import { useEffect, useState } from "react";
import { Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

const STATE_RING = {
  done: "border-l-primary",
  skipped: "border-l-destructive",
  pending: "border-l-border",
};

export default function BlockRow({ block, onMark }) {
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(block.label);

  useEffect(() => {
    setLabel(block.label);
  }, [block.label]);

  const toggle = (target) =>
    onMark(block.start, { state: block.state === target ? "pending" : target });

  const submitLabel = () => {
    setEditing(false);
    if (label !== block.label) onMark(block.start, { label });
  };

  return (
    <div
      className={cn(
        "flex items-center gap-3 border-l-4 rounded-md bg-card px-3 py-2",
        STATE_RING[block.state]
      )}
    >
      <span className="w-[104px] shrink-0 tabular-nums text-sm text-muted-foreground">
        {block.start}–{block.end}
      </span>
      {editing ? (
        <Input
          className="h-8 flex-1"
          value={label}
          autoFocus
          onChange={(e) => setLabel(e.target.value)}
          onBlur={submitLabel}
          onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
        />
      ) : (
        <span
          className="flex-1 cursor-text text-sm"
          onClick={() => setEditing(true)}
        >
          {block.label}
        </span>
      )}
      <Button
        size="sm"
        variant={block.state === "done" ? "default" : "outline"}
        aria-pressed={block.state === "done"}
        onClick={() => toggle("done")}
      >
        <Check className="mr-1 h-4 w-4" /> Done
      </Button>
      <Button
        size="sm"
        variant={block.state === "skipped" ? "destructive" : "outline"}
        aria-pressed={block.state === "skipped"}
        onClick={() => toggle("skipped")}
      >
        <X className="mr-1 h-4 w-4" /> Skip
      </Button>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `web/`): `npm test -- BlockRow`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add web/src/BlockRow.jsx web/src/BlockRow.test.jsx
git commit -m "feat(web): shadcn BlockRow with Done/Skip and inline label"
```

### Task C3: DayView dashboard (header, progress, date nav)

**Files:**
- Modify: `web/src/DayView.jsx`
- Create: `web/src/DayView.test.jsx`

- [ ] **Step 1: Write the test**

Create `web/src/DayView.test.jsx`:

```jsx
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import DayView from "./DayView.jsx";
import * as api from "./api.js";

afterEach(() => vi.restoreAllMocks());

test("renders blocks and a done-count summary", async () => {
  vi.spyOn(api, "getDay").mockResolvedValue({
    date: "2026-05-24",
    blocks: [
      { start: "08:00", end: "09:00", label: "standup", state: "done" },
      { start: "09:00", end: "10:00", label: "code", state: "pending" },
    ],
  });
  render(<DayView />);
  await waitFor(() => expect(screen.getByText("standup")).toBeInTheDocument());
  expect(screen.getByText("1 / 2 done")).toBeInTheDocument(); // exact: only the count span
});

test("shows an empty state when there are no blocks", async () => {
  vi.spyOn(api, "getDay").mockResolvedValue({ date: "2026-05-24", blocks: [] });
  render(<DayView />);
  await waitFor(() =>
    expect(screen.getByText(/no blocks/i)).toBeInTheDocument()
  );
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `web/`): `npm test -- DayView`
Expected: FAIL — current DayView has no done-count summary.

- [ ] **Step 3: Rewrite `web/src/DayView.jsx`**

```jsx
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import { getDay, markBlock } from "./api.js";
import BlockRow from "./BlockRow.jsx";

function toLocalISODate(d) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function shiftDate(iso, days) {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + days);
  return toLocalISODate(d);
}

function prettyDate(iso) {
  return new Date(iso + "T00:00:00").toLocaleDateString(undefined, {
    weekday: "short", month: "short", day: "numeric",
  });
}

export default function DayView() {
  const [date, setDate] = useState(() => toLocalISODate(new Date()));
  const [blocks, setBlocks] = useState([]);

  useEffect(() => {
    getDay(date)
      .then((day) => setBlocks(day.blocks))
      .catch((e) => toast.error(e.message));
  }, [date]);

  const onMark = (start, mark) =>
    markBlock(date, start, mark)
      .then((day) => setBlocks(day.blocks))
      .catch((e) => toast.error(e.message));

  const done = blocks.filter((b) => b.state === "done").length;
  const pct = blocks.length ? (done / blocks.length) * 100 : 0;

  return (
    <Card>
      <CardHeader className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1">
            <Button variant="outline" size="icon" aria-label="previous day"
              onClick={() => setDate(shiftDate(date, -1))}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="icon" aria-label="next day"
              onClick={() => setDate(shiftDate(date, 1))}>
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="sm"
              onClick={() => setDate(toLocalISODate(new Date()))}>
              Today
            </Button>
          </div>
          <Input type="date" className="h-9 w-auto" value={date}
            onChange={(e) => e.target.value && setDate(e.target.value)} />
        </div>
        <div className="flex items-center gap-3">
          <span className="text-lg font-medium">{prettyDate(date)}</span>
          <span className="ml-auto text-sm text-muted-foreground">
            {done} / {blocks.length} done
          </span>
        </div>
        <Progress value={pct} />
      </CardHeader>
      <CardContent className="space-y-2">
        {blocks.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No blocks. Add some in the Template tab.
          </p>
        ) : (
          blocks.map((b) => <BlockRow key={b.start} block={b} onMark={onMark} />)
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `web/`): `npm test -- DayView`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add web/src/DayView.jsx web/src/DayView.test.jsx
git commit -m "feat(web): dashboard DayView with progress and date nav"
```

### Task C4: TemplateEditor with shadcn Dialog (add/edit/remove)

**Files:**
- Modify: `web/src/TemplateEditor.jsx`
- Modify: `web/src/TemplateEditor.test.jsx`

- [ ] **Step 1: Replace the test**

Replace `web/src/TemplateEditor.test.jsx` with:

```jsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import TemplateEditor from "./TemplateEditor.jsx";
import * as api from "./api.js";

afterEach(() => vi.restoreAllMocks());

test("lists existing template blocks", async () => {
  vi.spyOn(api, "getTemplate").mockResolvedValue([
    { start: "08:00", end: "09:00", label: "standup" },
  ]);
  render(<TemplateEditor />);
  expect(await screen.findByText(/standup/)).toBeInTheDocument();
  expect(screen.getByText(/08:00/)).toBeInTheDocument();
});

test("editing a block calls editTemplateBlock with new values", async () => {
  vi.spyOn(api, "getTemplate").mockResolvedValue([
    { start: "08:00", end: "09:00", label: "standup" },
  ]);
  const edit = vi.spyOn(api, "editTemplateBlock").mockResolvedValue({});
  render(<TemplateEditor />);

  fireEvent.click(await screen.findByRole("button", { name: /edit/i }));
  fireEvent.change(screen.getByLabelText("label"), { target: { value: "sync" } });
  fireEvent.click(screen.getByRole("button", { name: /save/i }));

  await waitFor(() =>
    expect(edit).toHaveBeenCalledWith("08:00", {
      new_start: "08:00", new_end: "09:00", label: "sync",
    })
  );
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `web/`): `npm test -- TemplateEditor`
Expected: FAIL — current TemplateEditor has no Dialog/edit affordance with these labels.

- [ ] **Step 3: Rewrite `web/src/TemplateEditor.jsx`**

```jsx
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  addTemplateBlock, deleteTemplateBlock, editTemplateBlock, getTemplate,
} from "./api.js";

const EMPTY = { start: "", end: "", label: "" };

function BlockDialog({ trigger, title, initial, onSubmit }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(initial);

  useEffect(() => {
    if (open) setForm(initial);
  }, [open, initial]);

  const submit = (e) => {
    e.preventDefault();
    onSubmit(form)
      .then(() => setOpen(false))
      .catch((err) => toast.error(err.message));
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>{title}</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="flex gap-3">
            <div className="flex-1">
              <Label htmlFor="start">Start</Label>
              <Input id="start" type="time" aria-label="start" required
                value={form.start}
                onChange={(e) => setForm({ ...form, start: e.target.value })} />
            </div>
            <div className="flex-1">
              <Label htmlFor="end">End</Label>
              <Input id="end" type="time" aria-label="end" required
                value={form.end}
                onChange={(e) => setForm({ ...form, end: e.target.value })} />
            </div>
          </div>
          <div>
            <Label htmlFor="label">Label</Label>
            <Input id="label" aria-label="label" required value={form.label}
              onChange={(e) => setForm({ ...form, label: e.target.value })} />
          </div>
          <DialogFooter>
            <Button type="submit">Save</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function TemplateEditor() {
  const [blocks, setBlocks] = useState([]);

  const refresh = () =>
    getTemplate().then(setBlocks).catch((e) => toast.error(e.message));

  useEffect(() => { refresh(); }, []);

  const add = (form) => addTemplateBlock(form).then(refresh);
  const edit = (start) => (form) =>
    editTemplateBlock(start, {
      new_start: form.start, new_end: form.end, label: form.label,
    }).then(refresh);
  const remove = (start) =>
    deleteTemplateBlock(start).then(refresh).catch((e) => toast.error(e.message));

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Template</CardTitle>
        <BlockDialog
          title="Add block"
          initial={EMPTY}
          onSubmit={add}
          trigger={<Button size="sm">Add block</Button>}
        />
      </CardHeader>
      <CardContent className="space-y-2">
        {blocks.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No template blocks yet.
          </p>
        ) : (
          blocks.map((b) => (
            <div key={b.start}
              className="flex items-center gap-3 rounded-md border px-3 py-2 text-sm">
              <span className="tabular-nums text-muted-foreground">
                {b.start}–{b.end}
              </span>
              <span className="flex-1">{b.label}</span>
              <BlockDialog
                title="Edit block"
                initial={{ start: b.start, end: b.end, label: b.label }}
                onSubmit={edit(b.start)}
                trigger={<Button size="sm" variant="outline">Edit</Button>}
              />
              <Button size="sm" variant="ghost" onClick={() => remove(b.start)}>
                Remove
              </Button>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `web/`): `npm test -- TemplateEditor`
Expected: PASS (2 tests). Note: the edit test opens the dialog (the "Edit" button is the `DialogTrigger`), edits the label, and submits.

- [ ] **Step 5: Commit**

```bash
git add web/src/TemplateEditor.jsx web/src/TemplateEditor.test.jsx
git commit -m "feat(web): shadcn TemplateEditor with add/edit/remove dialog"
```

---

## Phase D: Verification

### Task D1: Full suites, build, and live smoke test

**Files:** none (verification only)

- [ ] **Step 1: Full Python suite**

Run: `python -m pytest -q`
Expected: PASS (core + cli + api).

- [ ] **Step 2: Full web suite + build**

Run (from `web/`): `npm test` then `npm run build`
Expected: all Vitest files pass; Vite build emits `dist/` with no errors.

- [ ] **Step 3: Live smoke test (shared data dir)**

In one terminal: `PLAN_DATA_DIR=/tmp/plan-smoke2 python -m uvicorn api:app --port 8000` (PowerShell: `$env:PLAN_DATA_DIR="$env:TEMP\plan-smoke2"; python -m uvicorn api:app --port 8000`).
In another: `cd web && npm run dev`, open http://localhost:5173.

Verify by hand:
1. Template tab → add `08:00–09:00 "standup"`; it appears.
2. Day tab → the block shows pending; click **Done** → emerald, progress shows `1 / 1 done`; click **Done** again → pending.
3. Template tab → add `10:00–11:00 "review"`. Day tab (same day) → the `10:00` block now appears even though you already marked `08:00` (the bug fix).
4. Edit `08:00`'s label via the block row; navigate a day forward and back — the override persists; other days show the template default.
5. `PLAN_DATA_DIR=/tmp/plan-smoke2 python cli.py today` reflects the same data.

- [ ] **Step 4: Clean up the stale real data file (optional)**

The existing `~/.plan/data.json` is v2 and will auto-migrate on first load; its stale
`11:55 work` entry becomes inert and won't render. No action required, but you may delete
`~/.plan/data.json` to start clean if desired.

- [ ] **Step 5: Final commit (if any verification tweaks were needed)**

```bash
git add -A
git commit -m "chore: verify shadcn redesign + live-template model end-to-end"
```
