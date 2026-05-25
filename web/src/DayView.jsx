import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PAL } from "./lib/palette.js";
import { axisRange, activeStart } from "./lib/schedule.js";
import { getDay, markBlock, addTemplateBlock, addNote, editNote, deleteNote, dismissReminder } from "./api.js";
import TimelineBlock from "./TimelineBlock.jsx";
import DaySidebar from "./DaySidebar.jsx";
import BlockDialog from "./BlockDialog.jsx";

const PX_PER_HR = 64;
const toLocalISODate = (d) => {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};
const shiftDate = (iso, days) => { const d = new Date(iso + "T00:00:00"); d.setDate(d.getDate() + days); return toLocalISODate(d); };
const prettyDate = (iso) =>
  new Date(iso + "T00:00:00").toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" }).toUpperCase();
const relativeDay = (iso, todayIso) => {
  const day = (s) => new Date(s + "T00:00:00").getTime();
  const diff = Math.round((day(iso) - day(todayIso)) / 86_400_000);
  return { 0: "Today", "-1": "Yesterday", 1: "Tomorrow" }[diff] ?? null;
};

export default function DayView({ now: nowProp }) {
  const [clock, setClock] = useState(() => nowProp ?? new Date());
  useEffect(() => {
    if (nowProp) return;
    const id = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(id);
  }, [nowProp]);

  const todayISO = toLocalISODate(nowProp ?? clock);
  const [date, setDate] = useState(todayISO);
  const [blocks, setBlocks] = useState([]);
  const [notes, setNotes] = useState([]);
  const [reminders, setReminders] = useState([]);

  const applyDay = (day) => {
    setBlocks(day.blocks);
    setNotes(day.notes ?? []);
    setReminders(day.reminders ?? []);
  };
  const load = (d) => getDay(d).then(applyDay).catch((e) => toast.error(e.message));
  useEffect(() => { load(date); }, [date]);

  const onMark = (start, mark) =>
    markBlock(date, start, mark).then(applyDay).catch((e) => toast.error(e.message));
  const onAddNote = (note) => addNote(date, note).then(applyDay).catch((e) => toast.error(e.message));
  const onToggleNoteFlag = (n) =>
    editNote(date, n.id, { flagged: !n.flagged }).then(applyDay).catch((e) => toast.error(e.message));
  const onDeleteNote = (n) => deleteNote(date, n.id).then(() => load(date)).catch((e) => toast.error(e.message));
  const onDismissReminder = (r) =>
    dismissReminder({ origin_date: r.origin_date, kind: r.kind, ref: r.ref })
      .then(() => load(date)).catch((e) => toast.error(e.message));
  const addBlock = (form) =>
    addTemplateBlock({ start: form.start, end: form.end, label: form.label, tag: form.tag }).then(() => load(date));

  const range = axisRange(blocks);
  const nowMin = clock.getHours() * 60 + clock.getMinutes() + clock.getSeconds() / 60;
  const isToday = date === todayISO;
  const activeKey = isToday ? activeStart(blocks, nowMin) : null;
  const active = blocks.find((b) => b.start === activeKey) ?? null;

  return (
    <div className="overflow-hidden rounded-2xl border bg-background" style={{ borderColor: PAL.hairline }}>
      <div className="flex items-center justify-between border-b px-6 py-4" style={{ borderColor: PAL.hairline }}>
        <div className="flex items-baseline gap-3">
          <h2 className="text-lg font-semibold tracking-tight">Planner</h2>
          <div className="font-mono text-xs" style={{ color: PAL.muted }}>{prettyDate(date)}</div>
        </div>
        <div className="flex items-center gap-1.5">
          <Button variant="outline" size="icon" aria-label="previous day" onClick={() => setDate(shiftDate(date, -1))}><ChevronLeft className="h-4 w-4" /></Button>
          <Button variant="ghost" size="sm" aria-label="go to today" className="min-w-[5.5rem]" onClick={() => setDate(todayISO)}>
            {relativeDay(date, todayISO) ?? prettyDate(date)}
          </Button>
          <Button variant="outline" size="icon" aria-label="next day" onClick={() => setDate(shiftDate(date, 1))}><ChevronRight className="h-4 w-4" /></Button>
          <Input type="date" className="h-9 w-auto" value={date} onChange={(e) => e.target.value && setDate(e.target.value)} />
          <BlockDialog title="Add block" initial={{ start: "", end: "", label: "", tag: "" }} onSubmit={addBlock}
            trigger={<Button size="sm"><Plus className="mr-1 h-4 w-4" />Block</Button>} />
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: "1fr 320px" }}>
        <div className="px-8 py-6">
          {!range ? (
            <p className="py-10 text-center text-sm" style={{ color: PAL.muted }}>No blocks. Add some with "+ Block" or in the Template tab.</p>
          ) : (
            <div className="relative" style={{ height: (range.endHour - range.startHour) * PX_PER_HR, marginLeft: 56 }}>
              {Array.from({ length: range.endHour - range.startHour + 1 }).map((_, i) => {
                const h = range.startHour + i;
                // Hide an hour label when the NOW line sits right on it, so the
                // two time stamps don't print on top of each other.
                const nearNow = isToday && Math.abs(h * 60 - nowMin) < 18;
                return (
                  <div key={i} className="absolute right-0 flex items-center" style={{ left: -56, top: i * PX_PER_HR, height: 1, background: PAL.hairline }}>
                    <span className="w-12 pr-2 text-right font-mono text-[11px]" style={{ color: PAL.muted, transform: "translateY(-50%)", background: PAL.bg, visibility: nearNow ? "hidden" : "visible" }}>
                      {String(h).padStart(2, "0")}:00
                    </span>
                  </div>
                );
              })}
              {blocks.map((b) => (
                <TimelineBlock key={b.start} block={b} axisStartMin={range.startHour * 60}
                  isActive={b.start === activeKey} onMark={onMark} />
              ))}
              {isToday && nowMin >= range.startHour * 60 && nowMin <= range.endHour * 60 && (
                <div className="absolute" style={{ left: -56, right: 0, top: ((nowMin - range.startHour * 60) / 60) * PX_PER_HR, zIndex: 5 }}>
                  <div className="absolute font-mono text-[11px] font-semibold" style={{ left: 0, top: -7, width: 46, textAlign: "right", color: PAL.accent, paddingRight: 8 }}>
                    {String(Math.floor(nowMin / 60)).padStart(2, "0")}:{String(Math.floor(nowMin % 60)).padStart(2, "0")}
                  </div>
                  <div className="absolute" style={{ left: 50, right: 0, top: 0, height: 0, borderTop: `1.5px solid ${PAL.accent}` }} />
                  <div className="absolute" style={{ left: 46, top: -5, width: 10, height: 10, borderRadius: 999, background: PAL.accent, boxShadow: `0 0 0 4px ${PAL.bg}` }} />
                </div>
              )}
            </div>
          )}
        </div>
        <DaySidebar blocks={blocks} active={active} nowMin={nowMin}
          onComplete={(start) => onMark(start, { state: "done" })}
          reminders={reminders} notes={notes}
          onDismissReminder={onDismissReminder} onAddNote={onAddNote}
          onToggleNoteFlag={onToggleNoteFlag} onDeleteNote={onDeleteNote} />
      </div>
    </div>
  );
}
