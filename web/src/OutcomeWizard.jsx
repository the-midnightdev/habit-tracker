import { useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CURATED_OUTCOMES } from "./lib/outcomes.js";
import BlockDialog from "./BlockDialog.jsx";

export default function OutcomeWizard({ open, onOpenChange, blocks, onCreate, onAddBlock }) {
  const [name, setName] = useState("");
  const [direction, setDirection] = useState("increase");
  const [linked, setLinked] = useState({});  // id -> bool
  const [extra, setExtra] = useState([]);     // experiment blocks created in-session

  const pickCurated = (c) => { setName(c.name); setDirection(c.direction); };
  const toggle = (id) => setLinked((p) => ({ ...p, [id]: !p[id] }));

  const allBlocks = [...(blocks ?? []), ...extra];

  const addExperiment = (form) =>
    onAddBlock(form).then((blk) => {
      setExtra((p) => [...p, blk]);
      setLinked((p) => ({ ...p, [blk.id]: true }));
    });

  const submit = () => {
    const block_ids = allBlocks.map((b) => b.id).filter((id) => linked[id]);
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
            <Label>Direction</Label>
            <div className="flex gap-2">
              <Button type="button" size="sm" aria-label="direction increase"
                      variant={direction === "increase" ? "default" : "outline"}
                      onClick={() => setDirection("increase")}>More is better</Button>
              <Button type="button" size="sm" aria-label="direction decrease"
                      variant={direction === "decrease" ? "default" : "outline"}
                      onClick={() => setDirection("decrease")}>Less is better</Button>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Which blocks serve this?</Label>
            <div className="space-y-1">
              {allBlocks.map((b) => (
                <label key={b.id} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" aria-label={`link ${b.label}`}
                         checked={!!linked[b.id]} onChange={() => toggle(b.id)} />
                  <span>{b.start}–{b.end} {b.label}</span>
                </label>
              ))}
            </div>
            <BlockDialog title="Add an experiment"
              initial={{ start: "", end: "", label: "", tag: "" }}
              onSubmit={addExperiment}
              trigger={<Button type="button" size="sm" variant="outline">Add an experiment</Button>} />
          </div>
        </div>

        <DialogFooter>
          <Button onClick={submit} disabled={!name.trim()}>Create outcome</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
