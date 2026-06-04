import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { PAL } from "./lib/palette.js";

export default function InsightCard({ insight, onKeep, onTweak, onDrop }) {
  if (!insight) return null;

  if (!insight.ready) {
    const pct = Math.min(100, Math.round((insight.daysChecked / 14) * 100));
    return (
      <div className="rounded-2xl border bg-white p-4" style={{ borderColor: PAL.hairline }}>
        <div className="text-sm" style={{ color: PAL.ink2 }}>Building confidence</div>
        <div className="mt-1 text-xs" style={{ color: PAL.muted }}>
          {insight.daysChecked} / 14 days · {insight.completions} / 10 completions
        </div>
        <Progress value={pct} className="mt-2" />
      </div>
    );
  }

  return (
    <div className="rounded-2xl border bg-white p-4" style={{ borderColor: PAL.hairline }}>
      <p className="text-sm" style={{ color: PAL.ink2 }}>{insight.headline}</p>
      {insight.suggestion && (
        <div className="mt-3 flex gap-2">
          <Button size="sm" variant="default" onClick={() => onKeep(insight.suggestion)}>Keep</Button>
          <Button size="sm" variant="outline" onClick={() => onTweak(insight.suggestion)}>Tweak</Button>
          <Button size="sm" variant="ghost" onClick={() => onDrop(insight.suggestion)}>Drop</Button>
        </div>
      )}
    </div>
  );
}
