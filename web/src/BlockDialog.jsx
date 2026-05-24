import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";

const TAGS = ["Deep work", "Break", "Shallow"];

// initial: { start, end, label, tag } where tag may be null/"".
export default function BlockDialog({ trigger, title, initial, onSubmit }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(initial);

  // Seed only on open; `initial` is a one-time seed, not a live sync target.
  useEffect(() => {
    if (open) setForm({ ...initial, tag: initial.tag ?? "" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const submit = (e) => {
    e.preventDefault();
    onSubmit({ ...form, tag: form.tag || null })
      .then(() => setOpen(false))
      .catch((err) => toast.error(err.message));
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription className="sr-only">
            Set the block's start time, end time, label, and type.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="flex gap-3">
            <div className="flex-1">
              <Label htmlFor="start">Start</Label>
              <Input id="start" type="time" aria-label="start" required
                value={form.start}
                onChange={(e) => setForm({ ...form, start: e.target.value })} />
            </div>
            <div className="flex-1">
              <Label htmlFor="end">End</Label>
              <Input id="end" type="time" aria-label="end" required
                value={form.end}
                onChange={(e) => setForm({ ...form, end: e.target.value })} />
            </div>
          </div>
          <div>
            <Label htmlFor="label">Label</Label>
            <Input id="label" aria-label="label" required value={form.label}
              onChange={(e) => setForm({ ...form, label: e.target.value })} />
          </div>
          <div>
            <Label htmlFor="tag">Type</Label>
            <select id="tag" aria-label="tag" value={form.tag ?? ""}
              onChange={(e) => setForm({ ...form, tag: e.target.value })}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm">
              <option value="">No type</option>
              {TAGS.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <DialogFooter>
            <Button type="submit">Save</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
