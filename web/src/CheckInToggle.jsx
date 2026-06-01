import { Bell, BellOff } from "lucide-react";
import { PAL } from "./lib/palette.js";

export default function CheckInToggle({ enabled, onToggle }) {
  return (
    <button
      onClick={onToggle}
      aria-label={enabled ? "disable hourly check-ins" : "enable hourly check-ins"}
      className="flex items-center justify-between rounded-2xl border bg-white p-4 text-left"
      style={{ borderColor: PAL.hairline }}
    >
      <div>
        <div className="font-mono text-[10px] font-semibold uppercase tracking-widest" style={{ color: PAL.muted }}>
          Hourly check-ins
        </div>
        <div className="mt-1 text-sm" style={{ color: PAL.ink2 }}>
          {enabled ? "On — asked at the top of each hour" : "Off"}
        </div>
      </div>
      {enabled
        ? <Bell className="h-4 w-4 flex-shrink-0" style={{ color: PAL.accent }} />
        : <BellOff className="h-4 w-4 flex-shrink-0" style={{ color: PAL.muted }} />}
    </button>
  );
}
