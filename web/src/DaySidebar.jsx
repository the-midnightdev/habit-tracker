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
            <div className="flex items-baseline gap-1">
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
