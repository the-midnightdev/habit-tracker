import { Check } from "lucide-react";
import { PAL } from "./lib/palette.js";

const prettyOrigin = (iso) =>
  new Date(iso + "T00:00:00").toLocaleDateString(undefined, {
    weekday: "short", month: "short", day: "numeric",
  });

export default function RemindersCard({ reminders, onDismiss }) {
  if (!reminders.length) return null;
  return (
    <div className="rounded-2xl border bg-white p-4" style={{ borderColor: PAL.hairline }}>
      <div className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-widest" style={{ color: PAL.muted }}>
        Reminders
      </div>
      <ul className="flex flex-col gap-2">
        {reminders.map((r) => (
          <li key={`${r.origin_date}-${r.kind}-${r.ref}`}
            className="flex items-start gap-2 rounded-lg border p-2"
            style={{ borderColor: PAL.hairline2, background: "#FBF8F2" }}>
            <div className="min-w-0 flex-1">
              <div className="text-sm" style={{ color: PAL.ink }}>{r.text}</div>
              <div className="mt-0.5 font-mono text-[10px]" style={{ color: PAL.muted }}>
                from {prettyOrigin(r.origin_date)}
                {r.block_time ? ` · ${r.block_time}${r.block_label ? ` ${r.block_label}` : ""}` : ""}
              </div>
            </div>
            <button aria-label="dismiss reminder" onClick={() => onDismiss(r)}
              className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md border"
              style={{ borderColor: PAL.hairline2 }}>
              <Check className="h-3.5 w-3.5" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
