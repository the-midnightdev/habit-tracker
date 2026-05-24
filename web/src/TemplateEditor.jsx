import { useEffect, useState } from "react";
import {
  addTemplateBlock,
  deleteTemplateBlock,
  editTemplateBlock,
  getTemplate,
} from "./api.js";

export default function TemplateEditor() {
  const [blocks, setBlocks] = useState([]);
  const [form, setForm] = useState({ start: "", end: "", label: "" });
  const [editingStart, setEditingStart] = useState(null);
  const [editForm, setEditForm] = useState({ start: "", end: "", label: "" });
  const [error, setError] = useState(null);

  const refresh = () => {
    setError(null);
    return getTemplate()
      .then(setBlocks)
      .catch((e) => setError(e.message));
  };

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

  const startEdit = (b) => {
    setError(null);
    setEditingStart(b.start);
    setEditForm({ start: b.start, end: b.end, label: b.label });
  };

  const cancelEdit = () => setEditingStart(null);

  const saveEdit = (e) => {
    e.preventDefault();
    setError(null);
    editTemplateBlock(editingStart, {
      new_start: editForm.start,
      new_end: editForm.end,
      label: editForm.label,
    })
      .then(() => {
        setEditingStart(null);
        refresh();
      })
      .catch((err) => setError(err.message));
  };

  return (
    <section className="template">
      <h2>Template</h2>
      {error && <p className="error">{error}</p>}
      <ul className="template__list">
        {blocks.map((b) =>
          editingStart === b.start ? (
            <li key={b.start}>
              <form onSubmit={saveEdit} className="template__edit">
                <input
                  type="time"
                  aria-label="edit start"
                  value={editForm.start}
                  onChange={(e) => setEditForm({ ...editForm, start: e.target.value })}
                  required
                />
                <input
                  type="time"
                  aria-label="edit end"
                  value={editForm.end}
                  onChange={(e) => setEditForm({ ...editForm, end: e.target.value })}
                  required
                />
                <input
                  type="text"
                  aria-label="edit label"
                  value={editForm.label}
                  onChange={(e) => setEditForm({ ...editForm, label: e.target.value })}
                  required
                />
                <button type="submit">Save</button>
                <button type="button" onClick={cancelEdit}>
                  Cancel
                </button>
              </form>
            </li>
          ) : (
            <li key={b.start}>
              <span>{b.start}–{b.end}</span>
              {" · "}
              <span>{b.label}</span>
              <button onClick={() => startEdit(b)}>Edit</button>
              <button onClick={() => remove(b.start)}>Remove</button>
            </li>
          )
        )}
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
