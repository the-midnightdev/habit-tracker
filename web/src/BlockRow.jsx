import { useState } from "react";

export default function BlockRow({ block, onMark }) {
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(block.label);

  const toggle = (target) =>
    onMark(block.start, { state: block.state === target ? "pending" : target });

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
          onKeyDown={(e) => e.key === "Enter" && submitLabel()}
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
