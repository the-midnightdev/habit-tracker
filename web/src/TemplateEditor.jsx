import { useEffect, useState } from "react";
import {
  addTemplateBlock,
  deleteTemplateBlock,
  getTemplate,
} from "./api.js";

export default function TemplateEditor() {
  const [blocks, setBlocks] = useState([]);
  const [form, setForm] = useState({ start: "", end: "", label: "" });
  const [error, setError] = useState(null);

  const refresh = () =>
    getTemplate()
      .then(setBlocks)
      .catch((e) => setError(e.message));

  useEffect(() => {
    refresh();
  }, []);

  const submit = (e) => {
    e.preventDefault();
    setError(null);
    addTemplateBlock(form)
      .then(() => {
        setForm({ start: "", end: "", label: "" });
        refresh();
      })
      .catch((err) => setError(err.message));
  };

  const remove = (start) =>
    deleteTemplateBlock(start)
      .then(refresh)
      .catch((e) => setError(e.message));

  return (
    <section className="template">
      <h2>Template</h2>
      {error && <p className="error">{error}</p>}
      <ul className="template__list">
        {blocks.map((b) => (
          <li key={b.start}>
            <span>{b.start}–{b.end}</span>
            {" · "}
            <span>{b.label}</span>
            <button onClick={() => remove(b.start)}>Remove</button>
          </li>
        ))}
      </ul>
      <form onSubmit={submit} className="template__form">
        <input
          type="time"
          aria-label="start"
          value={form.start}
          onChange={(e) => setForm({ ...form, start: e.target.value })}
          required
        />
        <input
          type="time"
          aria-label="end"
          value={form.end}
          onChange={(e) => setForm({ ...form, end: e.target.value })}
          required
        />
        <input
          type="text"
          aria-label="label"
          placeholder="label"
          value={form.label}
          onChange={(e) => setForm({ ...form, label: e.target.value })}
          required
        />
        <button type="submit">Add</button>
      </form>
    </section>
  );
}
