import { useEffect, useState } from "react";
import { Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

const STATE_RING = {
  done: "border-l-primary",
  skipped: "border-l-destructive",
  pending: "border-l-border",
};

export default function BlockRow({ block, onMark }) {
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(block.label);

  useEffect(() => {
    setLabel(block.label);
  }, [block.label]);

  const toggle = (target) =>
    onMark(block.start, { state: block.state === target ? "pending" : target });

  const submitLabel = () => {
    setEditing(false);
    if (label !== block.label) onMark(block.start, { label });
  };

  return (
    <div
      className={cn(
        "flex items-center gap-3 border-l-4 rounded-md bg-card px-3 py-2",
        STATE_RING[block.state]
      )}
    >
      <span className="w-[104px] shrink-0 tabular-nums text-sm text-muted-foreground">
        {block.start}–{block.end}
      </span>
      {editing ? (
        <Input
          className="h-8 flex-1"
          value={label}
          autoFocus
          onChange={(e) => setLabel(e.target.value)}
          onBlur={submitLabel}
          onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
        />
      ) : (
        <span className="flex-1 cursor-text text-sm" onClick={() => setEditing(true)}>
          {block.label}
        </span>
      )}
      <Button
        size="sm"
        variant={block.state === "done" ? "default" : "outline"}
        aria-pressed={block.state === "done"}
        onClick={() => toggle("done")}
      >
        <Check className="mr-1 h-4 w-4" /> Done
      </Button>
      <Button
        size="sm"
        variant={block.state === "skipped" ? "destructive" : "outline"}
        aria-pressed={block.state === "skipped"}
        onClick={() => toggle("skipped")}
      >
        <X className="mr-1 h-4 w-4" /> Skip
      </Button>
    </div>
  );
}
