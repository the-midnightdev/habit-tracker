import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import BlockDialog from "./BlockDialog.jsx";
import { tagIcon } from "./lib/tags.js";
import {
  addTemplateBlock, deleteTemplateBlock, editTemplateBlock, getTemplate,
} from "./api.js";

const EMPTY = { start: "", end: "", label: "", tag: "" };

export default function TemplateEditor() {
  const [blocks, setBlocks] = useState([]);

  const refresh = () =>
    getTemplate().then(setBlocks).catch((e) => toast.error(e.message));

  useEffect(() => { refresh(); }, []);

  const add = (form) =>
    addTemplateBlock({ start: form.start, end: form.end, label: form.label, tag: form.tag })
      .then(refresh);
  const edit = (start) => (form) =>
    editTemplateBlock(start, {
      new_start: form.start, new_end: form.end, label: form.label, tag: form.tag,
    }).then(refresh);
  const remove = (start) =>
    deleteTemplateBlock(start).then(refresh).catch((e) => toast.error(e.message));

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Template</CardTitle>
        <BlockDialog title="Add block" initial={EMPTY} onSubmit={add}
          trigger={<Button size="sm">Add block</Button>} />
      </CardHeader>
      <CardContent className="space-y-2">
        {blocks.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">No template blocks yet.</p>
        ) : (
          blocks.map((b) => {
            const TagIcon = tagIcon(b.tag);
            return (
              <div key={b.start}
                className="flex items-center gap-3 rounded-md border px-3 py-2 text-sm">
                <span className="font-mono text-muted-foreground">{b.start}–{b.end}</span>
                <span className="flex-1">{b.label}</span>
                {b.tag && (
                  <span className="flex items-center gap-1 text-muted-foreground">
                    <TagIcon className="h-3.5 w-3.5" /> {b.tag}
                  </span>
                )}
                <BlockDialog title="Edit block"
                  initial={{ start: b.start, end: b.end, label: b.label, tag: b.tag }}
                  onSubmit={edit(b.start)}
                  trigger={<Button size="sm" variant="outline">Edit</Button>} />
                <Button size="sm" variant="ghost" onClick={() => remove(b.start)}>Remove</Button>
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
