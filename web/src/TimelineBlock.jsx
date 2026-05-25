import { useEffect, useState } from "react";
import { Check, X, MessageSquare, Flag } from "lucide-react";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { PAL } from "./lib/palette.js";
import { tagIcon } from "./lib/tags.js";
import { minOf } from "./lib/schedule.js";

const PX_PER_HR = 64;

export default function TimelineBlock({ block, axisStartMin, isActive, onMark }) {
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(block.label);
  useEffect(() => { setLabel(block.label); }, [block.label]);

  const startMin = minOf(block.start);
  const endMin = minOf(block.end);
  const top = ((startMin - axisStartMin) / 60) * PX_PER_HR;
  const slot = ((endMin - startMin) / 60) * PX_PER_HR;
  // Leave a 3px gap below each block so adjacent blocks read as separate.
  // Short blocks switch to a one-line layout that fits the smaller box.
  const height = Math.max(30, slot - 3);
  const compact = height < 50;
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

  const [noteOpen, setNoteOpen] = useState(false);
  const [noteText, setNoteText] = useState(block.comment ?? "");
  const [noteFlag, setNoteFlag] = useState(block.flagged ?? false);
  useEffect(() => {
    setNoteText(block.comment ?? "");
    setNoteFlag(block.flagged ?? false);
  }, [block.comment, block.flagged]);
  const saveNote = () => {
    onMark(block.start, { comment: noteText.trim(), flagged: noteText.trim() ? noteFlag : false });
    setNoteOpen(false);
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
      <div className={cn("flex min-w-0 flex-1 items-center px-3", compact ? "gap-2" : "gap-3")}>
        <span className={cn("flex flex-shrink-0 items-center justify-center rounded-lg", compact ? "h-6 w-6" : "h-8 w-8")}
          style={{ background: isActive ? PAL.accentSoft : "#F2EEE5", color: isActive ? PAL.accentDeep : PAL.ink2 }}>
          <TagIcon className={compact ? "h-3.5 w-3.5" : "h-4 w-4"} />
        </span>
        <div className={cn("min-w-0 flex-1", compact && "flex items-center gap-2")}>
          <div className="flex items-center gap-2">
            <span className="flex-shrink-0 font-mono text-[11px]" style={{ color: PAL.muted }}>{block.start}–{block.end}</span>
            {!compact && (
              <span className="rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide"
                style={pillStyle(isActive, isDone)}>
                {isActive ? "Now" : isDone ? "Done" : block.tag || "Block"}
              </span>
            )}
            {block.flagged ? (
              <Flag aria-label="flagged" className="h-3 w-3 flex-shrink-0" style={{ color: PAL.accent, fill: PAL.accent }} />
            ) : block.comment ? (
              <span aria-label="has comment" className="h-1.5 w-1.5 flex-shrink-0 rounded-full" style={{ background: PAL.hairline2 }} />
            ) : null}
          </div>
          {editing ? (
            <input autoFocus value={label} aria-label="edit label"
              className={cn("bg-transparent text-sm font-medium outline-none", compact ? "min-w-0 flex-1" : "w-full")}
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
        <div className={cn("flex flex-shrink-0 items-center gap-1 transition",
          isActive ? "opacity-100" : "opacity-0 group-hover:opacity-100")}>
          <Popover open={noteOpen} onOpenChange={(open) => {
            if (!open) {
              setNoteText(block.comment ?? "");
              setNoteFlag(block.flagged ?? false);
            }
            setNoteOpen(open);
          }}>
            <PopoverTrigger asChild>
              <button aria-label="comment"
                className="flex h-7 w-7 items-center justify-center rounded-md border" style={{ borderColor: PAL.hairline2 }}>
                <MessageSquare className="h-3.5 w-3.5" />
              </button>
            </PopoverTrigger>
            <PopoverContent align="end">
              <textarea aria-label="comment text" value={noteText} rows={3}
                onChange={(e) => setNoteText(e.target.value)} placeholder="Add a comment…"
                className="w-full resize-none rounded-md border bg-transparent p-2 text-sm outline-none"
                style={{ borderColor: PAL.hairline2 }} />
              <button aria-label="flag for tomorrow" aria-pressed={noteFlag}
                onClick={() => setNoteFlag((f) => !f)}
                className="mt-2 flex items-center gap-2 text-xs" style={{ color: PAL.ink2 }}>
                <Flag className="h-3 w-3" style={noteFlag ? { color: PAL.accent, fill: PAL.accent } : {}} />
                Flag for tomorrow
              </button>
              <Button size="sm" className="mt-3 w-full" onClick={saveNote}>Save</Button>
            </PopoverContent>
          </Popover>
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

function pillStyle(isActive, isDone) {
  if (isActive) return { background: PAL.accentSoft, color: PAL.accentDeep };
  if (isDone) return { background: PAL.doneSoft, color: "#2E5C46" };
  return { background: "transparent", color: PAL.muted, border: `1px solid ${PAL.hairline2}` };
}
