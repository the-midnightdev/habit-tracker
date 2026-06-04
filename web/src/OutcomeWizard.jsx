import { useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CURATED_OUTCOMES } from "./lib/outcomes.js";

export default function OutcomeWizard({ open, onOpenChange, blocks, onCreate }) {
  const [name, setName] = useState("");
  const [direction, setDirection] = useState("increase");
  const [linked, setLinked] = useState({}); // id -> bool

  const pickCurated = (c) => { setName(c.name); setDirection(c.direction); };
  const toggle = (id) => setLinked((p) => ({ ...p, [id]: !p[id] }));

  const submit = () => {
    const block_ids = (blocks ?? []).map((b) => b.id).filter((id) => linked[id]);
    onCreate({ name: name.trim(), description: "", direction, block_ids });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>New outcome</DialogTitle></DialogHeader>

        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {CURATED_OUTCOMES.map((c) => (
              <Button key={c.name} type="button" size="sm" variant="outline" onClick={() => pickCurated(c)}>
                {c.name}
              </Button>
            ))}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="outcome-name">Name</Label>
            <Input id="outcome-name" value={name} onChange={(e) => setName(e.target.value)}
                   placeholder="e.g. More energy" />
          </div>

          <div className="space-y-1.5">
            <Label>Which blocks serve this?</Label>
            <div className="space-y-1">
              {(blocks ?? []).map((b) => (
                <label key={b.id} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" aria-label={`link ${b.label}`}
                         checked={!!linked[b.id]} onChange={() => toggle(b.id)} />
                  <span>{b.start}–{b.end} {b.label}</span>
                </label>
              ))}
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button onClick={submit} disabled={!name.trim()}>Create outcome</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
