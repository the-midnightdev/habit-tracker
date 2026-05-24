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
