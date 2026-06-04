import { Check, X } from "lucide-react";
import { PAL } from "./lib/palette.js";

export default function EndOfDayReview({ blocks, onMark }) {
  const pending = (blocks ?? []).filter((b) => b.state === "pending");
  if (pending.length === 0) return null;
  return (
    <div className="rounded-2xl border bg-white p-4" style={{ borderColor: PAL.hairline }}>
      <div className="font-mono text-[10px] font-semibold uppercase tracking-widest" style={{ color: PAL.muted }}>
        Loose ends
      </div>
      <div className="mt-3 space-y-2">
        {pending.map((b) => (
          <div key={b.start} className="flex items-center justify-between">
            <span className="text-sm" style={{ color: PAL.ink2 }}>{b.start} {b.label}</span>
            <div className="flex gap-1.5">
              <button aria-label={`mark ${b.label} done`} onClick={() => onMark(b.start, { state: "done" })}
                      className="rounded-full border p-1" style={{ borderColor: PAL.hairline }}>
                <Check className="h-4 w-4" style={{ color: PAL.accent }} />
              </button>
              <button aria-label={`mark ${b.label} skipped`} onClick={() => onMark(b.start, { state: "skipped" })}
                      className="rounded-full border p-1" style={{ borderColor: PAL.hairline }}>
                <X className="h-4 w-4" style={{ color: PAL.muted }} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
