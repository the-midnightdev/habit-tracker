# Timeline Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the planner to the reference "Timeline" design (warm Geist/cream/orange theme) and rebuild the Day view as a vertical hour-axis timeline with a live NOW line, active-block highlight, countdown, and progress sidebar — adding an optional block `tag`.

**Architecture:** Small backend addition (optional `tag` on blocks, schema v3 additive). Frontend re-themes the shadcn tokens to the reference palette, ports the palette to `web/src/lib/palette.js`, isolates clock math in pure `web/src/lib/schedule.js` helpers (unit-tested), shares one `BlockDialog` between the Day "+ Block" button and the Template editor, and renders the timeline via `TimelineBlock` + a `DaySidebar`.

**Tech Stack:** Python 3.13/FastAPI/pytest; React+Vite+Vitest; Tailwind + shadcn/ui; lucide-react; Geist fonts.

**Spec:** `docs/superpowers/specs/2026-05-24-timeline-redesign-design.md`
**Visual reference:** `docs/design-reference/planner.jsx` (`VariantTimeline`).

**Conventions:** times `"HH:MM"` 24h; states `pending|done|skipped`; `tag ∈ {Deep work, Break, Shallow}|null`. Python from repo root (`python -m pytest`); web from `web/` (`npm test`, `npm run build`). The rendered day-block shape is `{start,end,label,state,tag}`.

---

## Phase A: Backend — block `tag`

### Task A1: `tag` on the core model

**Files:** Modify `core.py`, Modify `tests/test_core.py`.

- [ ] **Step 1: Write failing tests** — append to `tests/test_core.py`:

```python
from core import TAGS


def test_add_template_block_with_tag_round_trips(data_dir: Path):
    data = PlannerData()
    add_template_block(data, "08:00", "09:00", "standup", tag="Deep work")
    DataStore(data_dir).save(data)
    loaded = DataStore(data_dir).load()
    assert loaded.template[0].tag == "Deep work"


def test_template_block_defaults_to_no_tag():
    data = PlannerData()
    add_template_block(data, "08:00", "09:00", "standup")
    assert data.template[0].tag is None


def test_v3_file_without_tag_loads_as_none(data_dir: Path):
    (data_dir / "data.json").write_text(json.dumps({
        "version": 3,
        "template": [{"start": "08:00", "end": "09:00", "label": "standup"}],
        "days": {},
    }), encoding="utf-8")
    loaded = DataStore(data_dir).load()
    assert loaded.template[0].tag is None


def test_add_template_block_rejects_unknown_tag():
    data = PlannerData()
    with pytest.raises(ValidationError):
        add_template_block(data, "08:00", "09:00", "standup", tag="Nonsense")


def test_edit_template_block_sets_tag():
    data = PlannerData()
    add_template_block(data, "08:00", "09:00", "standup")
    edit_template_block(data, "08:00", new_start="08:00", new_end="09:00",
                        label="standup", tag="Break")
    assert data.template[0].tag == "Break"


def test_get_day_blocks_includes_tag():
    data = PlannerData()
    add_template_block(data, "08:00", "09:00", "standup", tag="Shallow")
    assert get_day_blocks(data, "2026-05-24")[0].tag == "Shallow"


def test_known_tags():
    assert TAGS == ("Deep work", "Break", "Shallow")
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_core.py::test_known_tags -v`
Expected: FAIL — `ImportError: cannot import name 'TAGS'`.

- [ ] **Step 3: Implement in `core.py`**

Add the tags constant and validator near the top (after `STATES`):

```python
TAGS = ("Deep work", "Break", "Shallow")


def validate_tag(tag: str | None) -> None:
    if tag is not None and tag not in TAGS:
        raise ValidationError(f"unknown tag {tag!r}; expected one of {TAGS} or null")
```

Add `tag` to the dataclasses (keep all other fields):

```python
@dataclass
class TemplateBlock:
    start: str
    end: str
    label: str
    tag: str | None = None


@dataclass
class DayBlock:
    """A rendered block for a given day (template fields + resolved state/label)."""
    start: str
    end: str
    label: str
    state: str = "pending"
    tag: str | None = None
```

Update `add_template_block` and `edit_template_block` to accept/validate/store `tag`:

```python
def add_template_block(
    data: PlannerData, start: str, end: str, label: str, tag: str | None = None
) -> TemplateBlock:
    _check_template_slot(data, start, end)
    validate_tag(tag)
    block = TemplateBlock(start=start, end=end, label=label, tag=tag)
    data.template.append(block)
    data.template.sort(key=lambda b: b.start)
    return block


def edit_template_block(
    data: PlannerData, start: str, *, new_start: str, new_end: str,
    label: str, tag: str | None = None
) -> TemplateBlock:
    block = find_template_block(data, start)
    if block is None:
        raise ValidationError(f"no template block starts at {start!r}")
    _check_template_slot(data, new_start, new_end, ignore_start=start)
    validate_tag(tag)
    block.start, block.end, block.label, block.tag = new_start, new_end, label, tag
    data.template.sort(key=lambda b: b.start)
    return block
```

In `get_day_blocks`, carry `tag` from the template block onto the rendered `DayBlock` (the loop body becomes):

```python
        blocks.append(DayBlock(start=tb.start, end=tb.end, label=label,
                               state=state, tag=tb.tag))
```

(`tag` is a block-type property, never a per-day override.)

- [ ] **Step 4: Run the full core suite**

Run: `python -m pytest tests/test_core.py -v`
Expected: PASS (existing tests + the 7 new ones). `asdict`-based save now writes `tag` (possibly null); older v3 files without it load as `None` via the dataclass default.

- [ ] **Step 5: Commit**

```bash
git add core.py tests/test_core.py
git commit -m "feat: optional block tag in core model"
```

### Task A2: `tag` through the API

**Files:** Modify `api.py`, Modify `tests/test_api.py`.

- [ ] **Step 1: Write failing tests** — append to `tests/test_api.py`:

```python
def test_create_block_with_tag(client):
    resp = client.post("/api/template",
                       json={"start": "08:00", "end": "09:00", "label": "x", "tag": "Deep work"})
    assert resp.status_code == 201
    assert resp.json()["tag"] == "Deep work"
    assert client.get("/api/template").json()[0]["tag"] == "Deep work"


def test_create_block_with_bad_tag_returns_400(client):
    resp = client.post("/api/template",
                       json={"start": "08:00", "end": "09:00", "label": "x", "tag": "Bogus"})
    assert resp.status_code == 400


def test_day_blocks_include_tag(client):
    client.post("/api/template",
                json={"start": "08:00", "end": "09:00", "label": "x", "tag": "Break"})
    assert client.get("/api/days/2026-05-24").json()["blocks"][0]["tag"] == "Break"


def test_edit_block_sets_tag(client):
    client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "x"})
    resp = client.put("/api/template/08:00",
                      json={"new_start": "08:00", "new_end": "09:00", "label": "x", "tag": "Shallow"})
    assert resp.status_code == 200
    assert resp.json()["tag"] == "Shallow"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_api.py::test_create_block_with_tag -v`
Expected: FAIL — `tag` is dropped (not on `BlockIn`), so the created block's `tag` is `None`.

- [ ] **Step 3: Implement in `api.py`**

Add `tag` to the request models:

```python
class BlockIn(BaseModel):
    start: str
    end: str
    label: str
    tag: str | None = None


class BlockEdit(BaseModel):
    new_start: str
    new_end: str
    label: str
    tag: str | None = None
```

Pass `tag` through in the handlers:

```python
        created = add_template_block(data, block.start, block.end, block.label, tag=block.tag)
```

```python
        updated = edit_template_block(
            data, start, new_start=edit.new_start, new_end=edit.new_end,
            label=edit.label, tag=edit.tag,
        )
```

(`GET /api/days` already returns `asdict(b)` for each `DayBlock`, which now includes `tag` — no change needed there.)

- [ ] **Step 4: Run the full Python suite**

Run: `python -m pytest -q`
Expected: PASS (core + cli + api, including the 4 new API tests).

- [ ] **Step 5: Commit**

```bash
git add api.py tests/test_api.py
git commit -m "feat: accept block tag in the API"
```

---

## Phase B: Theme

### Task B1: Warm palette, Geist fonts, shared `palette.js`

**Files:** Modify `web/index.html`, Modify `web/src/index.css`, Modify `web/tailwind.config.js`, Create `web/src/lib/palette.js`.

- [ ] **Step 1: Add Geist fonts in `web/index.html`**

In `<head>` (before the existing `<title>` or right after the charset/viewport metas), add:

```html
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
```

- [ ] **Step 2: Rewrite the token values in `web/src/index.css`**

Replace the `:root { ... }` block with RGB-triplet tokens (the warm palette). Keep the `@tailwind` directives and the `@layer base { * { @apply border-border } ... }` block:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 250 248 244;
    --foreground: 27 26 23;
    --card: 255 255 255;
    --card-foreground: 27 26 23;
    --popover: 255 255 255;
    --popover-foreground: 27 26 23;
    --primary: 224 122 59;
    --primary-foreground: 255 255 255;
    --secondary: 242 238 229;
    --secondary-foreground: 58 54 49;
    --muted: 242 238 229;
    --muted-foreground: 107 101 91;
    --accent: 251 233 215;
    --accent-foreground: 182 92 36;
    --destructive: 179 64 46;
    --destructive-foreground: 255 255 255;
    --border: 236 231 220;
    --input: 236 231 220;
    --ring: 224 122 59;
    --radius: 0.6rem;
  }
}

@layer base {
  * { @apply border-border; }
  body { @apply bg-background text-foreground; }
}
```

- [ ] **Step 3: Switch Tailwind colors to the RGB-channel form and add fonts in `web/tailwind.config.js`**

Replace the file with:

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Geist', '-apple-system', 'system-ui', 'sans-serif'],
        mono: ['"Geist Mono"', 'ui-monospace', 'monospace'],
      },
      colors: {
        border: "rgb(var(--border) / <alpha-value>)",
        input: "rgb(var(--input) / <alpha-value>)",
        ring: "rgb(var(--ring) / <alpha-value>)",
        background: "rgb(var(--background) / <alpha-value>)",
        foreground: "rgb(var(--foreground) / <alpha-value>)",
        primary: { DEFAULT: "rgb(var(--primary) / <alpha-value>)", foreground: "rgb(var(--primary-foreground) / <alpha-value>)" },
        secondary: { DEFAULT: "rgb(var(--secondary) / <alpha-value>)", foreground: "rgb(var(--secondary-foreground) / <alpha-value>)" },
        destructive: { DEFAULT: "rgb(var(--destructive) / <alpha-value>)", foreground: "rgb(var(--destructive-foreground) / <alpha-value>)" },
        muted: { DEFAULT: "rgb(var(--muted) / <alpha-value>)", foreground: "rgb(var(--muted-foreground) / <alpha-value>)" },
        accent: { DEFAULT: "rgb(var(--accent) / <alpha-value>)", foreground: "rgb(var(--accent-foreground) / <alpha-value>)" },
        popover: { DEFAULT: "rgb(var(--popover) / <alpha-value>)", foreground: "rgb(var(--popover-foreground) / <alpha-value>)" },
        card: { DEFAULT: "rgb(var(--card) / <alpha-value>)", foreground: "rgb(var(--card-foreground) / <alpha-value>)" },
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

- [ ] **Step 4: Create `web/src/lib/palette.js`** (ported from the reference `PAL`, for the bespoke timeline inline styles)

```javascript
export const PAL = {
  bg: "#FAF8F4",
  surface: "#FFFFFF",
  ink: "#1B1A17",
  ink2: "#3A3631",
  muted: "#6B655B",
  hairline: "#ECE7DC",
  hairline2: "#E2DBCC",
  accent: "#E07A3B",
  accentSoft: "#FBE9D7",
  accentDeep: "#B65C24",
  done: "#4C8A6E",
  doneSoft: "#DDEBE2",
  skip: "#B0A89C",
  skipSoft: "#EFEBE3",
};
```

- [ ] **Step 5: Verify the build**

Run (from `web/`): `npm run build`
Expected: build succeeds. The whole app now renders cream/orange with Geist (existing shadcn components pick up the new tokens automatically).

- [ ] **Step 6: Commit**

```bash
git add web/index.html web/src/index.css web/tailwind.config.js web/src/lib/palette.js
git commit -m "feat(web): warm Geist/cream/orange theme + palette module"
```

---

## Phase C: Clock math

### Task C1: Pure schedule helpers

**Files:** Create `web/src/lib/schedule.js`, Create `web/src/lib/schedule.test.js`.

- [ ] **Step 1: Write the failing tests** — create `web/src/lib/schedule.test.js`:

```javascript
import { expect, test } from "vitest";
import {
  minOf, durMin, axisRange, activeStart, focusedMinutes, remainingMinutes, countdown,
} from "./schedule.js";

const blocks = [
  { start: "13:00", end: "14:00", state: "done" },
  { start: "14:00", end: "15:00", state: "pending" },
  { start: "15:00", end: "16:30", state: "pending" },
];

test("minOf parses HH:MM", () => {
  expect(minOf("14:30")).toBe(870);
});

test("durMin is end minus start", () => {
  expect(durMin({ start: "15:00", end: "16:30" })).toBe(90);
});

test("axisRange floors earliest hour and ceils latest", () => {
  expect(axisRange(blocks)).toEqual({ startHour: 13, endHour: 17 });
  expect(axisRange([])).toBeNull();
});

test("activeStart finds the non-done block containing now", () => {
  expect(activeStart(blocks, minOf("14:23"))).toBe("14:00");
});

test("activeStart ignores done blocks and returns null when nothing matches", () => {
  expect(activeStart(blocks, minOf("13:30"))).toBeNull(); // 13:00 block is done
  expect(activeStart(blocks, minOf("20:00"))).toBeNull();
});

test("focusedMinutes sums done durations", () => {
  expect(focusedMinutes(blocks)).toBe(60);
});

test("remainingMinutes sums not-done blocks ending after now", () => {
  expect(remainingMinutes(blocks, minOf("14:23"))).toBe(60 + 90); // 14:00 and 15:00 blocks
  expect(remainingMinutes(blocks, minOf("15:30"))).toBe(90);       // only the 15:00 block
});

test("countdown renders mm:ss and clamps at zero", () => {
  expect(countdown(minOf("15:00"), minOf("14:23"))).toBe("37:00");
  expect(countdown(minOf("15:00"), 14 * 60 + 23.5)).toBe("36:30");
  expect(countdown(minOf("14:00"), minOf("15:00"))).toBe("0:00");
});
```

- [ ] **Step 2: Run to verify failure**

Run (from `web/`): `npm test -- schedule`
Expected: FAIL — cannot resolve `./schedule.js`.

- [ ] **Step 3: Implement `web/src/lib/schedule.js`**

```javascript
export function minOf(hm) {
  const [h, m] = hm.split(":").map(Number);
  return h * 60 + m;
}

export function durMin(b) {
  return minOf(b.end) - minOf(b.start);
}

export function axisRange(blocks) {
  if (!blocks.length) return null;
  const starts = blocks.map((b) => minOf(b.start));
  const ends = blocks.map((b) => minOf(b.end));
  return {
    startHour: Math.floor(Math.min(...starts) / 60),
    endHour: Math.ceil(Math.max(...ends) / 60),
  };
}

export function activeStart(blocks, nowMin) {
  for (const b of blocks) {
    if (b.state !== "done" && minOf(b.start) <= nowMin && nowMin < minOf(b.end)) {
      return b.start;
    }
  }
  return null;
}

export function focusedMinutes(blocks) {
  return blocks
    .filter((b) => b.state === "done")
    .reduce((sum, b) => sum + durMin(b), 0);
}

export function remainingMinutes(blocks, nowMin) {
  return blocks
    .filter((b) => b.state !== "done" && minOf(b.end) > nowMin)
    .reduce((sum, b) => sum + durMin(b), 0);
}

export function countdown(endMin, nowMin) {
  const totalSec = Math.max(0, Math.round((endMin - nowMin) * 60));
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}
```

- [ ] **Step 4: Run to verify pass**

Run (from `web/`): `npm test -- schedule`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/schedule.js web/src/lib/schedule.test.js
git commit -m "feat(web): pure schedule/clock helpers with tests"
```

---

## Phase D: Shared block dialog with tag

### Task D1: Extract `BlockDialog` (with Tag select) and use it in TemplateEditor

**Files:** Create `web/src/BlockDialog.jsx`, Create `web/src/lib/tags.js`, Modify `web/src/TemplateEditor.jsx`, Modify `web/src/TemplateEditor.test.jsx`.

- [ ] **Step 1: Update the TemplateEditor test** — replace `web/src/TemplateEditor.test.jsx` with:

```jsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import TemplateEditor from "./TemplateEditor.jsx";
import * as api from "./api.js";

afterEach(() => vi.restoreAllMocks());

test("lists existing template blocks with their tag", async () => {
  vi.spyOn(api, "getTemplate").mockResolvedValue([
    { start: "08:00", end: "09:00", label: "standup", tag: "Deep work" },
  ]);
  render(<TemplateEditor />);
  expect(await screen.findByText(/standup/)).toBeInTheDocument();
  expect(screen.getByText(/Deep work/)).toBeInTheDocument();
});

test("editing a block sends the chosen tag", async () => {
  vi.spyOn(api, "getTemplate").mockResolvedValue([
    { start: "08:00", end: "09:00", label: "standup", tag: null },
  ]);
  const edit = vi.spyOn(api, "editTemplateBlock").mockResolvedValue({});
  render(<TemplateEditor />);

  fireEvent.click(await screen.findByRole("button", { name: /edit/i }));
  fireEvent.change(screen.getByLabelText("tag"), { target: { value: "Break" } });
  fireEvent.click(screen.getByRole("button", { name: /save/i }));

  await waitFor(() =>
    expect(edit).toHaveBeenCalledWith("08:00", {
      new_start: "08:00", new_end: "09:00", label: "standup", tag: "Break",
    })
  );
});
```

- [ ] **Step 2: Run to verify failure**

Run (from `web/`): `npm test -- TemplateEditor`
Expected: FAIL — there's no tag `<select>` (label "tag") in the current dialog.

- [ ] **Step 3: Create `web/src/BlockDialog.jsx`** (shared add/edit dialog; native `<select>` for tag to keep it test-friendly)

```jsx
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";

const TAGS = ["Deep work", "Break", "Shallow"];

// initial: { start, end, label, tag } where tag may be null/"".
export default function BlockDialog({ trigger, title, initial, onSubmit }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(initial);

  // Seed only on open; `initial` is a one-time seed, not a live sync target.
  useEffect(() => {
    if (open) setForm({ ...initial, tag: initial.tag ?? "" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const submit = (e) => {
    e.preventDefault();
    onSubmit({ ...form, tag: form.tag || null })
      .then(() => setOpen(false))
      .catch((err) => toast.error(err.message));
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription className="sr-only">
            Set the block's start time, end time, label, and type.
          </DialogDescription>
        </DialogHeader>
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
          <div>
            <Label htmlFor="tag">Type</Label>
            <select id="tag" aria-label="tag" value={form.tag ?? ""}
              onChange={(e) => setForm({ ...form, tag: e.target.value })}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm">
              <option value="">No type</option>
              {TAGS.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <DialogFooter>
            <Button type="submit">Save</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 4: Create `web/src/lib/tags.js`** (tag→icon map, shared by the template list and the timeline)

```javascript
import { Brain, Coffee, List } from "lucide-react";

export function tagIcon(tag) {
  if (tag === "Deep work") return Brain;
  if (tag === "Break") return Coffee;
  return List;
}
```

- [ ] **Step 5: Rewrite `web/src/TemplateEditor.jsx`** to use the shared dialog and show the tag

```jsx
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import BlockDialog from "./BlockDialog.jsx";
import { tagIcon } from "./lib/tags.js";
import {
  addTemplateBlock, deleteTemplateBlock, editTemplateBlock, getTemplate,
} from "./api.js";

const EMPTY = { start: "", end: "", label: "", tag: "" };

export default function TemplateEditor() {
  const [blocks, setBlocks] = useState([]);

  const refresh = () =>
    getTemplate().then(setBlocks).catch((e) => toast.error(e.message));

  useEffect(() => { refresh(); }, []);

  const add = (form) =>
    addTemplateBlock({ start: form.start, end: form.end, label: form.label, tag: form.tag })
      .then(refresh);
  const edit = (start) => (form) =>
    editTemplateBlock(start, {
      new_start: form.start, new_end: form.end, label: form.label, tag: form.tag,
    }).then(refresh);
  const remove = (start) =>
    deleteTemplateBlock(start).then(refresh).catch((e) => toast.error(e.message));

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Template</CardTitle>
        <BlockDialog title="Add block" initial={EMPTY} onSubmit={add}
          trigger={<Button size="sm">Add block</Button>} />
      </CardHeader>
      <CardContent className="space-y-2">
        {blocks.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">No template blocks yet.</p>
        ) : (
          blocks.map((b) => {
            const TagIcon = tagIcon(b.tag);
            return (
              <div key={b.start}
                className="flex items-center gap-3 rounded-md border px-3 py-2 text-sm">
                <span className="font-mono text-muted-foreground">{b.start}–{b.end}</span>
                <span className="flex-1">{b.label}</span>
                {b.tag && (
                  <span className="flex items-center gap-1 text-muted-foreground">
                    <TagIcon className="h-3.5 w-3.5" /> {b.tag}
                  </span>
                )}
                <BlockDialog title="Edit block"
                  initial={{ start: b.start, end: b.end, label: b.label, tag: b.tag }}
                  onSubmit={edit(b.start)}
                  trigger={<Button size="sm" variant="outline">Edit</Button>} />
                <Button size="sm" variant="ghost" onClick={() => remove(b.start)}>Remove</Button>
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 6: Run to verify pass**

Run (from `web/`): `npm test -- TemplateEditor`
Expected: PASS (2 tests). The edit test changes the `tag` select to "Break" and asserts the call includes `tag: "Break"`.

- [ ] **Step 7: Commit**

```bash
git add web/src/BlockDialog.jsx web/src/lib/tags.js web/src/TemplateEditor.jsx web/src/TemplateEditor.test.jsx
git commit -m "feat(web): shared BlockDialog with Type select; tags in template list"
```

---

## Phase E: Timeline Day view

### Task E1: `TimelineBlock`, `DaySidebar`, and the Timeline `DayView`

**Files:** Create `web/src/TimelineBlock.jsx`, Create `web/src/DaySidebar.jsx`, Modify `web/src/DayView.jsx`, Modify `web/src/DayView.test.jsx`, Delete `web/src/BlockRow.jsx` + `web/src/BlockRow.test.jsx` (replaced by `TimelineBlock`).

- [ ] **Step 1: Replace the DayView test** — `web/src/DayView.test.jsx`:

```jsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import DayView from "./DayView.jsx";
import * as api from "./api.js";

afterEach(() => vi.restoreAllMocks());

const FIXED_NOW = new Date("2026-05-24T14:23:00");

function mockDay(blocks) {
  vi.spyOn(api, "getDay").mockResolvedValue({ date: "2026-05-24", blocks });
}

test("renders blocks, progress count, and the active countdown", async () => {
  mockDay([
    { start: "13:00", end: "14:00", label: "Lunch", state: "done", tag: "Break" },
    { start: "14:00", end: "15:00", label: "Auth bug", state: "pending", tag: "Deep work" },
  ]);
  render(<DayView now={FIXED_NOW} />);
  await waitFor(() => expect(screen.getByText("Auth bug")).toBeInTheDocument());
  expect(screen.getByText("1 / 2 done")).toBeInTheDocument(); // progress
  expect(screen.getByText("37:00")).toBeInTheDocument();      // countdown to 15:00 from 14:23
});

test("marks the active block done via Complete", async () => {
  mockDay([{ start: "14:00", end: "15:00", label: "Auth bug", state: "pending", tag: "Deep work" }]);
  const mark = vi.spyOn(api, "markBlock").mockResolvedValue({
    date: "2026-05-24",
    blocks: [{ start: "14:00", end: "15:00", label: "Auth bug", state: "done", tag: "Deep work" }],
  });
  render(<DayView now={FIXED_NOW} />);
  fireEvent.click(await screen.findByRole("button", { name: /complete/i }));
  await waitFor(() =>
    expect(mark).toHaveBeenCalledWith("2026-05-24", "14:00", { state: "done" })
  );
});

test("shows the empty state when there are no blocks", async () => {
  mockDay([]);
  render(<DayView now={FIXED_NOW} />);
  await waitFor(() => expect(screen.getByText(/no blocks/i)).toBeInTheDocument());
});
```

- [ ] **Step 2: Run to verify failure**

Run (from `web/`): `npm test -- DayView`
Expected: FAIL — current DayView has no countdown/Complete and doesn't accept a `now` prop.

- [ ] **Step 3: Create `web/src/TimelineBlock.jsx`**

```jsx
import { useEffect, useState } from "react";
import { Check, X } from "lucide-react";
import { PAL } from "./lib/palette.js";
import { tagIcon } from "./lib/tags.js";

const PX_PER_HR = 56;

export default function TimelineBlock({ block, axisStartMin, isActive, onMark }) {
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(block.label);
  useEffect(() => { setLabel(block.label); }, [block.label]);

  const startMin = toMin(block.start);
  const endMin = toMin(block.end);
  const top = ((startMin - axisStartMin) / 60) * PX_PER_HR;
  const height = Math.max(28, ((endMin - startMin) / 60) * PX_PER_HR - 4);
  const isDone = block.state === "done";
  const isSkip = block.state === "skipped";
  const stripe = isActive ? PAL.accent : isDone ? PAL.done : isSkip ? PAL.skip : PAL.hairline2;
  const TagIcon = tagIcon(block.tag);

  const toggle = (target) =>
    onMark(block.start, { state: block.state === target ? "pending" : target });
  const submitLabel = () => {
    setEditing(false);
    if (label !== block.label) onMark(block.start, { label });
  };

  return (
    <div
      className="group absolute left-2 right-2 flex overflow-hidden rounded-xl bg-white"
      style={{
        top, height,
        border: `1px solid ${isActive ? PAL.accent : isDone ? PAL.done : PAL.hairline2}`,
        boxShadow: isActive ? `0 1px 0 ${PAL.hairline}, 0 12px 28px -16px ${PAL.accent}55` : `0 1px 0 ${PAL.hairline}`,
        opacity: isDone ? 0.78 : 1,
      }}
    >
      <div style={{ width: 4, background: stripe, flexShrink: 0 }} />
      <div className="flex min-w-0 flex-1 items-center gap-3 px-3">
        <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg"
          style={{ background: isActive ? PAL.accentSoft : "#F2EEE5", color: isActive ? PAL.accentDeep : PAL.ink2 }}>
          <TagIcon className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px]" style={{ color: PAL.muted }}>{block.start}–{block.end}</span>
            <span className="rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide"
              style={pillStyle(isActive, isDone, block.tag)}>
              {isActive ? "Now" : isDone ? "Done" : block.tag || "Block"}
            </span>
          </div>
          {editing ? (
            <input autoFocus value={label} aria-label="edit label"
              className="w-full bg-transparent text-sm font-medium outline-none"
              onChange={(e) => setLabel(e.target.value)}
              onBlur={submitLabel}
              onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()} />
          ) : (
            <div className="truncate text-sm font-medium"
              style={{ textDecoration: isDone ? "line-through" : "none", color: isSkip ? PAL.muted : PAL.ink }}
              onClick={() => setEditing(true)}>
              {block.label}
            </div>
          )}
        </div>
        <div className="flex items-center gap-1 opacity-0 transition group-hover:opacity-100"
          style={{ opacity: isActive ? 1 : undefined }}>
          <button aria-label="done" onClick={() => toggle("done")}
            className="flex h-7 w-7 items-center justify-center rounded-md border" style={{ borderColor: PAL.hairline2 }}>
            <Check className="h-3.5 w-3.5" />
          </button>
          <button aria-label="skip" onClick={() => toggle("skipped")}
            className="flex h-7 w-7 items-center justify-center rounded-md border" style={{ borderColor: PAL.hairline2 }}>
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

function toMin(hm) { const [h, m] = hm.split(":").map(Number); return h * 60 + m; }

function pillStyle(isActive, isDone, tag) {
  if (isActive) return { background: PAL.accentSoft, color: PAL.accentDeep };
  if (isDone) return { background: PAL.doneSoft, color: "#2E5C46" };
  return { background: "transparent", color: PAL.muted, border: `1px solid ${PAL.hairline2}` };
}
```

- [ ] **Step 4: Create `web/src/DaySidebar.jsx`** (progress donut + Now card)

```jsx
import { Button } from "@/components/ui/button";
import { Check } from "lucide-react";
import { PAL } from "./lib/palette.js";
import { countdown, focusedMinutes, remainingMinutes, minOf } from "./lib/schedule.js";

function fmt(min) {
  const h = Math.floor(min / 60), m = min % 60;
  return `${h}h ${String(m).padStart(2, "0")}m`;
}

export default function DaySidebar({ blocks, active, nowMin, onComplete }) {
  const done = blocks.filter((b) => b.state === "done").length;
  const total = blocks.length;
  const pct = total ? done / total : 0;
  const size = 96, r = 38, c = 2 * Math.PI * r;

  return (
    <div className="flex flex-col gap-4 border-l p-5" style={{ borderColor: PAL.hairline }}>
      <div className="rounded-2xl border bg-white p-4" style={{ borderColor: PAL.hairline }}>
        <div className="mb-3 font-mono text-[10px] font-semibold uppercase tracking-widest" style={{ color: PAL.muted }}>Progress</div>
        <div className="flex items-center gap-4">
          <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
            <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={PAL.hairline} strokeWidth="8" />
            <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={PAL.done} strokeWidth="8"
              strokeDasharray={`${c*pct} ${c}`} strokeLinecap="round"
              transform={`rotate(-90 ${size/2} ${size/2})`} />
            <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle"
              fontFamily='"Geist Mono", monospace' fontSize="20" fontWeight="600" fill={PAL.ink}>
              {Math.round(pct * 100)}%
            </text>
          </svg>
          <div className="text-sm" style={{ color: PAL.ink2 }}>{`${done} / ${total} done`}</div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
          <Stat label="Focused" value={fmt(focusedMinutes(blocks))} accent />
          <Stat label="Remaining" value={fmt(remainingMinutes(blocks, nowMin))} />
        </div>
      </div>

      <div className="rounded-2xl border bg-white p-4" style={{ borderColor: PAL.hairline }}>
        <div className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-widest" style={{ color: PAL.muted }}>Now</div>
        {active ? (
          <>
            <div className="text-base font-semibold" style={{ color: PAL.ink }}>{active.label}</div>
            <div className="mt-3 flex items-baseline gap-1">
              <span className="font-mono text-3xl font-semibold" style={{ color: PAL.accent }}>
                {countdown(minOf(active.end), nowMin)}
              </span>
              <span className="text-xs" style={{ color: PAL.muted }}>left</span>
            </div>
            <Button className="mt-4 w-full" onClick={() => onComplete(active.start)}>
              <Check className="mr-1 h-4 w-4" /> Complete
            </Button>
          </>
        ) : (
          <div className="py-4 text-sm" style={{ color: PAL.muted }}>Nothing active right now.</div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, accent }) {
  return (
    <div className="rounded-lg border p-3" style={{ borderColor: PAL.hairline, background: "#FBF8F2" }}>
      <div className="font-mono text-[10px] uppercase tracking-wide" style={{ color: PAL.muted }}>{label}</div>
      <div className="mt-1 font-mono text-base font-semibold" style={{ color: accent ? PAL.accent : PAL.ink }}>{value}</div>
    </div>
  );
}
```

- [ ] **Step 5: Rewrite `web/src/DayView.jsx`** as the Timeline

```jsx
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PAL } from "./lib/palette.js";
import { axisRange, activeStart } from "./lib/schedule.js";
import { getDay, markBlock, addTemplateBlock } from "./api.js";
import TimelineBlock from "./TimelineBlock.jsx";
import DaySidebar from "./DaySidebar.jsx";
import BlockDialog from "./BlockDialog.jsx";

const PX_PER_HR = 56;
const toLocalISODate = (d) => {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};
const shiftDate = (iso, days) => { const d = new Date(iso + "T00:00:00"); d.setDate(d.getDate() + days); return toLocalISODate(d); };
const prettyDate = (iso) =>
  new Date(iso + "T00:00:00").toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" }).toUpperCase();

export default function DayView({ now: nowProp }) {
  const [clock, setClock] = useState(() => nowProp ?? new Date());
  useEffect(() => {
    if (nowProp) return;
    const id = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(id);
  }, [nowProp]);

  const todayISO = toLocalISODate(nowProp ?? clock);
  const [date, setDate] = useState(todayISO);
  const [blocks, setBlocks] = useState([]);

  const load = (d) => getDay(d).then((day) => setBlocks(day.blocks)).catch((e) => toast.error(e.message));
  useEffect(() => { load(date); }, [date]);

  const onMark = (start, mark) =>
    markBlock(date, start, mark).then((day) => setBlocks(day.blocks)).catch((e) => toast.error(e.message));
  const addBlock = (form) =>
    addTemplateBlock({ start: form.start, end: form.end, label: form.label, tag: form.tag }).then(() => load(date));

  const range = axisRange(blocks);
  const nowMin = clock.getHours() * 60 + clock.getMinutes() + clock.getSeconds() / 60;
  const isToday = date === todayISO;
  const activeKey = isToday ? activeStart(blocks, nowMin) : null;
  const active = blocks.find((b) => b.start === activeKey) ?? null;

  return (
    <div className="overflow-hidden rounded-2xl border bg-white" style={{ borderColor: PAL.hairline }}>
      {/* header */}
      <div className="flex items-center justify-between border-b px-6 py-4" style={{ borderColor: PAL.hairline }}>
        <div className="flex items-baseline gap-3">
          <div className="text-lg font-semibold tracking-tight">Planner</div>
          <div className="font-mono text-xs" style={{ color: PAL.muted }}>{prettyDate(date)}</div>
        </div>
        <div className="flex items-center gap-1.5">
          <Button variant="outline" size="icon" aria-label="previous day" onClick={() => setDate(shiftDate(date, -1))}><ChevronLeft className="h-4 w-4" /></Button>
          <Button variant="ghost" size="sm" onClick={() => setDate(todayISO)}>Today</Button>
          <Button variant="outline" size="icon" aria-label="next day" onClick={() => setDate(shiftDate(date, 1))}><ChevronRight className="h-4 w-4" /></Button>
          <Input type="date" className="h-9 w-auto" value={date} onChange={(e) => e.target.value && setDate(e.target.value)} />
          <BlockDialog title="Add block" initial={{ start: "", end: "", label: "", tag: "" }} onSubmit={addBlock}
            trigger={<Button size="sm"><Plus className="mr-1 h-4 w-4" />Block</Button>} />
        </div>
      </div>

      {/* body */}
      <div className="grid" style={{ gridTemplateColumns: "1fr 320px" }}>
        <div className="px-8 py-6">
          {!range ? (
            <p className="py-10 text-center text-sm" style={{ color: PAL.muted }}>No blocks. Add some with “+ Block” or in the Template tab.</p>
          ) : (
            <div className="relative" style={{ height: (range.endHour - range.startHour) * PX_PER_HR, marginLeft: 56 }}>
              {Array.from({ length: range.endHour - range.startHour + 1 }).map((_, i) => {
                const h = range.startHour + i;
                return (
                  <div key={i} className="absolute right-0 flex items-center" style={{ left: -56, top: i * PX_PER_HR, height: 1, background: PAL.hairline }}>
                    <span className="w-12 pr-2 text-right font-mono text-[11px]" style={{ color: PAL.muted, transform: "translateY(-50%)", background: PAL.bg }}>
                      {String(h).padStart(2, "0")}:00
                    </span>
                  </div>
                );
              })}
              {blocks.map((b) => (
                <TimelineBlock key={b.start} block={b} axisStartMin={range.startHour * 60}
                  isActive={b.start === activeKey} onMark={onMark} />
              ))}
              {isToday && nowMin >= range.startHour * 60 && nowMin <= range.endHour * 60 && (
                <div className="absolute" style={{ left: -56, right: 0, top: ((nowMin - range.startHour * 60) / 60) * PX_PER_HR, zIndex: 5 }}>
                  <div className="absolute font-mono text-[11px] font-semibold" style={{ left: 0, top: -7, width: 46, textAlign: "right", color: PAL.accent, paddingRight: 8 }}>
                    {String(Math.floor(nowMin / 60)).padStart(2, "0")}:{String(Math.floor(nowMin % 60)).padStart(2, "0")}
                  </div>
                  <div className="absolute" style={{ left: 50, right: 0, top: 0, height: 0, borderTop: `1.5px solid ${PAL.accent}` }} />
                  <div className="absolute" style={{ left: 46, top: -5, width: 10, height: 10, borderRadius: 999, background: PAL.accent, boxShadow: `0 0 0 4px ${PAL.bg}` }} />
                </div>
              )}
            </div>
          )}
        </div>
        <DaySidebar blocks={blocks} active={active} nowMin={nowMin} onComplete={(start) => onMark(start, { state: "done" })} />
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Remove the obsolete BlockRow**

```bash
git rm web/src/BlockRow.jsx web/src/BlockRow.test.jsx
```

- [ ] **Step 7: Run the full web suite**

Run (from `web/`): `npm test`
Expected: PASS — `schedule`, `DayView` (3), `TemplateEditor` (2), `App` (1), `api` (2). (No more BlockRow tests.)

- [ ] **Step 8: Verify the build**

Run (from `web/`): `npm run build`
Expected: build succeeds.

- [ ] **Step 9: Commit**

```bash
git add web/src/TimelineBlock.jsx web/src/DaySidebar.jsx web/src/DayView.jsx web/src/DayView.test.jsx
git commit -m "feat(web): timeline Day view with NOW line, active block, sidebar"
```

---

## Phase F: Verification

### Task F1: Full suites, build, live smoke test

**Files:** none (verification only)

- [ ] **Step 1: Full Python suite** — `python -m pytest -q` → PASS.
- [ ] **Step 2: Full web suite + build** — from `web/`: `npm test` then `npm run build` → all pass, build clean.
- [ ] **Step 3: Live smoke test.** Start backend on a temp dir and the dev server:
  - PowerShell: `$env:PLAN_DATA_DIR="$env:TEMP\plan-smoke4"; python -m uvicorn api:app --port 8000`
  - `cd web && npm run dev`; open http://localhost:5173.
  Verify by hand:
  1. Template tab → Add a block `14:00–15:00` "Auth bug" type **Deep work**; it lists with the brain icon.
  2. Day tab → the block appears on the timeline at the 14:00 row; if the real local time is within the day's range a NOW line shows.
  3. The block whose time contains "now" shows the orange **Now** highlight and the sidebar **Now** card counts down; click **Complete** → it turns done and the donut updates.
  4. Add another block in Template → it appears on today's timeline immediately (live-template model intact).
  5. Click a block's label, edit, Enter → persists; ◀/▶ navigate days.
- [ ] **Step 4: Final commit (if any tweaks needed)**

```bash
git add -A
git commit -m "chore: verify timeline redesign end-to-end"
```
