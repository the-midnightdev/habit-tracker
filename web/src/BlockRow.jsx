import { useEffect, useState } from "react";

export default function BlockRow({ block, onMark }) {
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(block.label);

  // Re-sync the editable label when the block prop changes (the parent reuses
  // this instance across refreshes because the key is stable).
  useEffect(() => {
    setLabel(block.label);
  }, [block.label]);

  const toggle = (target) =>
    onMark(block.start, { state: block.state === target ? "pending" : target });

  // Submission goes through onBlur only; Enter just blurs the input, so a single
  // keypress can't fire submitLabel twice (keydown + the resulting blur).
  const submitLabel = () => {
    setEditing(false);
    if (label !== block.label) onMark(block.start, { label });
  };

  return (
    <div className={`block block--${block.state}`}>
      <span className="block__time">
        {block.start}–{block.end}
      </span>
      {editing ? (
        <input
          className="block__label-input"
          value={label}
          autoFocus
          onChange={(e) => setLabel(e.target.value)}
          onBlur={submitLabel}
          onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
        />
      ) : (
        <span className="block__label" onClick={() => setEditing(true)}>
          {block.label}
        </span>
      )}
      <span className="block__actions">
        <button
          aria-pressed={block.state === "done"}
          onClick={() => toggle("done")}
        >
          Done
        </button>
        <button
          aria-pressed={block.state === "skipped"}
          onClick={() => toggle("skipped")}
        >
          Skip
        </button>
      </span>
    </div>
  );
}
