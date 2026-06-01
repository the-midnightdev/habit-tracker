// Pure helpers for the hourly check-in prompt. No React, no DOM — easy to test.

// True only in the first minute of the hour (nowMin % 60 < 1), when a block is
// active, and we have not already prompted for that block. `lastStart` is the
// start of the last block we prompted for, used to dedupe so the 1-second clock
// can't fire the prompt more than once per hour.
export function shouldCheckIn(nowMin, active, lastStart) {
  if (!active) return false;
  if (active.start === lastStart) return false;
  return nowMin % 60 < 1;
}

// Scripted content for the modal + notification.
// AI SEAM: to add a real assistant later, replace the body with an async call
// that returns the same { title, question, defaultLabel } shape — the modal and
// the DayView wiring stay unchanged.
export function composeCheckIn(block) {
  return {
    title: `${block.start} — new hour`,
    question: "What are you working on this hour?",
    defaultLabel: block.label,
  };
}
