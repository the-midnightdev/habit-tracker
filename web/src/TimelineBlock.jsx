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
              style={pillStyle(isActive, isDone)}>
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

function pillStyle(isActive, isDone) {
  if (isActive) return { background: PAL.accentSoft, color: PAL.accentDeep };
  if (isDone) return { background: PAL.doneSoft, color: "#2E5C46" };
  return { background: "transparent", color: PAL.muted, border: `1px solid ${PAL.hairline2}` };
}
