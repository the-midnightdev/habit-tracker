import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PAL } from "./lib/palette.js";
import {
  getOutcomes, getTemplate, getInsights, createOutcome, updateOutcome, addTemplateBlock,
} from "./api.js";
import InsightCard from "./InsightCard.jsx";
import OutcomeWizard from "./OutcomeWizard.jsx";

export default function OutcomesView() {
  const [outcomes, setOutcomes] = useState([]);
  const [blocks, setBlocks] = useState([]);
  const [insights, setInsights] = useState({}); // outcome id -> insight
  const [wizardOpen, setWizardOpen] = useState(false);

  const loadInsights = (list) =>
    Promise.all(list.map((o) => getInsights(o.id).then((i) => [o.id, i])))
      .then((pairs) => setInsights(Object.fromEntries(pairs)));

  const load = () =>
    Promise.all([getOutcomes(), getTemplate()])
      .then(([os, tmpl]) => { setOutcomes(os); setBlocks(tmpl); return loadInsights(os); })
      .catch((e) => toast.error(e.message));

  useEffect(() => { load(); }, []);

  const onCreate = (payload) =>
    createOutcome(payload).then(() => { setWizardOpen(false); return load(); }).catch((e) => toast.error(e.message));

  const onDrop = (outcome, suggestion) => {
    if (!suggestion?.blockId) { toast("Nothing linked to drop."); return; }
    const block_ids = outcome.block_ids.filter((id) => id !== suggestion.blockId);
    updateOutcome(outcome.id, { block_ids }).then(load).catch((e) => toast.error(e.message));
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setWizardOpen(true)}>
          <Plus className="mr-1 h-4 w-4" />Outcome
        </Button>
      </div>

      {outcomes.length === 0 ? (
        <p className="py-10 text-center text-sm" style={{ color: PAL.muted }}>
          No outcomes yet. Create one to start tracking progress.
        </p>
      ) : (
        outcomes.map((o) => (
          <div key={o.id} className="rounded-2xl border bg-background p-4" style={{ borderColor: PAL.hairline }}>
            <div className="mb-3 flex items-baseline justify-between">
              <h3 className="text-base font-semibold tracking-tight">{o.name}</h3>
              <span className="font-mono text-[10px] uppercase tracking-widest" style={{ color: PAL.muted }}>
                {o.status}
              </span>
            </div>
            <InsightCard
              insight={insights[o.id]}
              onKeep={() => toast("Keeping this one.")}
              onTweak={() => toast("Adjust this block in the Template tab, then watch for two weeks.")}
              onDrop={(s) => onDrop(o, s)}
            />
          </div>
        ))
      )}

      <OutcomeWizard open={wizardOpen} onOpenChange={setWizardOpen} blocks={blocks} onCreate={onCreate} onAddBlock={(form) => addTemplateBlock(form)} />
    </div>
  );
}
