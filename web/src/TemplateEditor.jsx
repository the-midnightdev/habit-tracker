import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  addTemplateBlock, deleteTemplateBlock, editTemplateBlock, getTemplate,
} from "./api.js";

const EMPTY = { start: "", end: "", label: "" };

function BlockDialog({ trigger, title, initial, onSubmit }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(initial);

  // Seed the form only when the dialog opens; `initial` is a one-time seed, not a
  // live sync target (it's a fresh object each render and would reset mid-edit).
  useEffect(() => {
    if (open) setForm(initial);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const submit = (e) => {
    e.preventDefault();
    onSubmit(form)
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
            Set the block's start time, end time, and label.
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
          <DialogFooter>
            <Button type="submit">Save</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function TemplateEditor() {
  const [blocks, setBlocks] = useState([]);

  const refresh = () =>
    getTemplate().then(setBlocks).catch((e) => toast.error(e.message));

  useEffect(() => { refresh(); }, []);

  const add = (form) => addTemplateBlock(form).then(refresh);
  const edit = (start) => (form) =>
    editTemplateBlock(start, {
      new_start: form.start, new_end: form.end, label: form.label,
    }).then(refresh);
  const remove = (start) =>
    deleteTemplateBlock(start).then(refresh).catch((e) => toast.error(e.message));

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Template</CardTitle>
        <BlockDialog
          title="Add block"
          initial={EMPTY}
          onSubmit={add}
          trigger={<Button size="sm">Add block</Button>}
        />
      </CardHeader>
      <CardContent className="space-y-2">
        {blocks.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No template blocks yet.
          </p>
        ) : (
          blocks.map((b) => (
            <div key={b.start}
              className="flex items-center gap-3 rounded-md border px-3 py-2 text-sm">
              <span className="tabular-nums text-muted-foreground">
                {b.start}–{b.end}
              </span>
              <span className="flex-1">{b.label}</span>
              <BlockDialog
                title="Edit block"
                initial={{ start: b.start, end: b.end, label: b.label }}
                onSubmit={edit(b.start)}
                trigger={<Button size="sm" variant="outline">Edit</Button>}
              />
              <Button size="sm" variant="ghost" onClick={() => remove(b.start)}>
                Remove
              </Button>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
