import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import { getDay, markBlock } from "./api.js";
import BlockRow from "./BlockRow.jsx";

function toLocalISODate(d) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function shiftDate(iso, days) {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + days);
  return toLocalISODate(d);
}

function prettyDate(iso) {
  return new Date(iso + "T00:00:00").toLocaleDateString(undefined, {
    weekday: "short", month: "short", day: "numeric",
  });
}

export default function DayView() {
  const [date, setDate] = useState(() => toLocalISODate(new Date()));
  const [blocks, setBlocks] = useState([]);

  useEffect(() => {
    getDay(date)
      .then((day) => setBlocks(day.blocks))
      .catch((e) => toast.error(e.message));
  }, [date]);

  const onMark = (start, mark) =>
    markBlock(date, start, mark)
      .then((day) => setBlocks(day.blocks))
      .catch((e) => toast.error(e.message));

  const done = blocks.filter((b) => b.state === "done").length;
  const pct = blocks.length ? (done / blocks.length) * 100 : 0;

  return (
    <Card>
      <CardHeader className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1">
            <Button variant="outline" size="icon" aria-label="previous day"
              onClick={() => setDate(shiftDate(date, -1))}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="icon" aria-label="next day"
              onClick={() => setDate(shiftDate(date, 1))}>
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="sm"
              onClick={() => setDate(toLocalISODate(new Date()))}>
              Today
            </Button>
          </div>
          <Input type="date" className="h-9 w-auto" value={date}
            onChange={(e) => e.target.value && setDate(e.target.value)} />
        </div>
        <div className="flex items-center gap-3">
          <span className="text-lg font-medium">{prettyDate(date)}</span>
          <span className="ml-auto text-sm text-muted-foreground">
            {`${done} / ${blocks.length} done`}
          </span>
        </div>
        <Progress value={pct} />
      </CardHeader>
      <CardContent className="space-y-2">
        {blocks.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No blocks. Add some in the Template tab.
          </p>
        ) : (
          blocks.map((b) => <BlockRow key={b.start} block={b} onMark={onMark} />)
        )}
      </CardContent>
    </Card>
  );
}
