import { PAL } from "./lib/palette.js";

export default function OutcomeCheckinCard({ outcomes, onRate }) {
  const active = (outcomes ?? []).filter((o) => o.status === "active");
  if (active.length === 0) return null;
  return (
    <div className="rounded-2xl border bg-white p-4" style={{ borderColor: PAL.hairline }}>
      <div className="font-mono text-[10px] font-semibold uppercase tracking-widest" style={{ color: PAL.muted }}>
        Today
      </div>
      <div className="mt-3 space-y-3">
        {active.map((o) => (
          <div key={o.id}>
            <div className="text-sm" style={{ color: PAL.ink2 }}>{o.name}</div>
            <div className="mt-1.5 flex gap-1.5">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  aria-label={`rate ${o.name} ${n}`}
                  onClick={() => onRate(o.id, n)}
                  className="h-8 w-8 rounded-full border text-sm font-semibold transition-colors"
                  style={{
                    borderColor: PAL.hairline,
                    background: o.todayRating === n ? PAL.accent : "transparent",
                    color: o.todayRating === n ? "#fff" : PAL.ink2,
                  }}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
