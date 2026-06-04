async function request(url, options) {
  const resp = options ? await fetch(url, options) : await fetch(url);
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      detail = (await resp.json()).detail ?? detail;
    } catch {
      // non-JSON error body; keep statusText
    }
    throw new Error(detail);
  }
  if (resp.status === 204) return null;
  return resp.json();
}

const jsonPost = (body) => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const getTemplate = () => request("/api/template");

export const addTemplateBlock = (block) =>
  request("/api/template", jsonPost(block));

export const editTemplateBlock = (start, edit) =>
  request(`/api/template/${start}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(edit),
  });

export const deleteTemplateBlock = (start) =>
  request(`/api/template/${start}`, { method: "DELETE" });

export const getDay = (date) => request(`/api/days/${date}`);

export const getHistory = () => request("/api/days");

export const markBlock = (date, start, mark) =>
  request(`/api/days/${date}/blocks/${start}`, jsonPost(mark));

export const addNote = (date, note) =>
  request(`/api/days/${date}/notes`, jsonPost(note));

export const editNote = (date, id, edit) =>
  request(`/api/days/${date}/notes/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(edit),
  });

export const deleteNote = (date, id) =>
  request(`/api/days/${date}/notes/${id}`, { method: "DELETE" });

export const dismissReminder = (payload) =>
  request("/api/reminders/dismiss", jsonPost(payload));

export const getPushKey = () => request("/api/push/key");

export const subscribePush = (subscription) =>
  request("/api/push/subscribe", jsonPost(subscription));

export const unsubscribePush = (endpoint) =>
  request("/api/push/unsubscribe", jsonPost({ endpoint }));

export const getOutcomes = () => request("/api/outcomes");

export const createOutcome = (outcome) =>
  request("/api/outcomes", jsonPost(outcome));

export const updateOutcome = (id, edit) =>
  request(`/api/outcomes/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(edit),
  });

export const deleteOutcome = (id) =>
  request(`/api/outcomes/${id}`, { method: "DELETE" });

export const rateOutcome = (date, id, rating) =>
  request(`/api/days/${date}/outcomes/${id}`, jsonPost({ rating }));

export const getInsights = (id) => request(`/api/outcomes/${id}/insights`);
