import { useEffect, useState } from "react";
import { getDay, markBlock } from "./api.js";
import BlockRow from "./BlockRow.jsx";

function shiftDate(iso, days) {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export default function DayView() {
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [blocks, setBlocks] = useState([]);
  const [error, setError] = useState(null);

  const refresh = (d) => {
    setError(null);
    return getDay(d)
      .then((day) => setBlocks(day.blocks))
      .catch((e) => setError(e.message));
  };

  useEffect(() => {
    refresh(date);
  }, [date]);

  const onMark = (start, mark) =>
    markBlock(date, start, mark)
      .then((day) => setBlocks(day.blocks))
      .catch((e) => setError(e.message));

  return (
    <section className="day">
      <header className="day__nav">
        <button onClick={() => setDate(shiftDate(date, -1))}>←</button>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />
        <button onClick={() => setDate(shiftDate(date, 1))}>→</button>
      </header>
      {error && <p className="error">{error}</p>}
      {blocks.length === 0 ? (
        <p>No blocks. Add some in the Template tab.</p>
      ) : (
        blocks.map((b) => <BlockRow key={b.start} block={b} onMark={onMark} />)
      )}
    </section>
  );
}
