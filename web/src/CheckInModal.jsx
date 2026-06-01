import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { PAL } from "./lib/palette.js";

// Controlled, presentation-only. Timing lives in DayView; this just shows the
// question and reports the user's choice via onSave(label) / onSkip().
export default function CheckInModal({ open, onOpenChange, content, block, onSave, onSkip }) {
  const [label, setLabel] = useState("");

  // Re-seed the input each time the modal opens for a (new) block.
  useEffect(() => {
    if (open && content) setLabel(content.defaultLabel ?? "");
  }, [open, content]);

  if (!block || !content) return null;

  const save = (e) => {
    e.preventDefault();
    onSave(label.trim() || content.defaultLabel);
    onOpenChange(false);
  };
  const skip = () => {
    onSkip();
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{content.title}</DialogTitle>
          <DialogDescription>
            {block.start}–{block.end}{block.tag ? ` · ${block.tag}` : ""}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={save} className="space-y-3">
          <p className="text-sm" style={{ color: PAL.muted }}>{content.question}</p>
          <Input aria-label="hour label" autoFocus value={label}
            onChange={(e) => setLabel(e.target.value)} />
          <DialogFooter className="gap-2">
            <Button type="button" variant="outline" onClick={skip}>Skip this hour</Button>
            <Button type="submit">Save</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
