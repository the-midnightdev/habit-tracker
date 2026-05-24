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
