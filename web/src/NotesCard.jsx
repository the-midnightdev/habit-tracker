import { useState } from "react";
import { Flag, Trash2, Plus } from "lucide-react";
import { PAL } from "./lib/palette.js";

export default function NotesCard({ notes, onAdd, onToggleFlag, onDelete }) {
  const [text, setText] = useState("");
  const [flag, setFlag] = useState(false);
  const submit = () => {
    const t = text.trim();
    if (!t) return;
    onAdd({ text: t, flagged: flag });
    setText("");
    setFlag(false);
  };
  const flagStyle = (on) => ({ color: on ? PAL.accent : PAL.hairline2, fill: on ? PAL.accent : "none" });

  return (
    <div className="rounded-2xl border bg-white p-4" style={{ borderColor: PAL.hairline }}>
      <div className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-widest" style={{ color: PAL.muted }}>
        Notes
      </div>
      {notes.length > 0 && (
        <ul className="mb-3 flex flex-col gap-2">
          {notes.map((n) => (
            <li key={n.id} className="flex items-start gap-2">
              <button aria-label={n.flagged ? "unflag note" : "flag note"} onClick={() => onToggleFlag(n)} className="mt-0.5 flex-shrink-0">
                <Flag className="h-3.5 w-3.5" style={flagStyle(n.flagged)} />
              </button>
              <span className="min-w-0 flex-1 text-sm" style={{ color: PAL.ink }}>{n.text}</span>
              <button aria-label="delete note" onClick={() => onDelete(n)} className="flex-shrink-0">
                <Trash2 className="h-3.5 w-3.5" style={{ color: PAL.muted }} />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex items-center gap-2">
        <input value={text} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Add a note…" aria-label="new note"
          className="min-w-0 flex-1 rounded-md border bg-transparent px-2 py-1 text-sm outline-none"
          style={{ borderColor: PAL.hairline2 }} />
        <button aria-label="flag for tomorrow" onClick={() => setFlag((f) => !f)} className="flex-shrink-0">
          <Flag className="h-4 w-4" style={flagStyle(flag)} />
        </button>
        <button aria-label="add note" onClick={submit}
          className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md border" style={{ borderColor: PAL.hairline2 }}>
          <Plus className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
