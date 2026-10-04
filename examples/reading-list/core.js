/* Local state rules shared by the browser and Node's built-in tests. */
(function (root) {
  "use strict";
  const KEY = "noetloom-reading-list.v1";
  function fields(title, url) {
    if (typeof title !== "string" || !title.trim() || title.trim().length > 200) {
      throw new Error("Enter a title between 1 and 200 characters.");
    }
    if (typeof url !== "string" || url.length > 2048) throw new Error("Keep the link under 2,048 characters.");
    let cleanURL = url.trim();
    if (cleanURL) {
      let parsed;
      try { parsed = new URL(cleanURL); } catch { throw new Error("Use a complete http:// or https:// link."); }
      if (!["http:", "https:"].includes(parsed.protocol) || parsed.username || parsed.password) {
        throw new Error("Use an http:// or https:// link without sign-in details.");
      }
      cleanURL = parsed.href;
    }
    return { title: title.trim(), url: cleanURL };
  }
  function decode(raw) {
    if (raw === null) return [];
    let state;
    try { state = JSON.parse(raw); } catch { throw new Error("Saved reading data is unreadable. Nothing was overwritten."); }
    if (!state || state.version !== 1 || !Array.isArray(state.entries)) throw new Error("Saved reading data has an unsupported format. Nothing was overwritten.");
    const ids = new Set();
    return state.entries.map(entry => {
      if (!entry || typeof entry.id !== "string" || !entry.id || ids.has(entry.id) || typeof entry.read !== "boolean") {
        throw new Error("Saved reading data contains an invalid entry. Nothing was overwritten.");
      }
      ids.add(entry.id);
      return { id: entry.id, ...fields(entry.title, entry.url), read: entry.read };
    });
  }
  function encode(entries) {
    const value = JSON.stringify({ version: 1, entries });
    decode(value);
    return value;
  }
  function add(entries, title, url, id) {
    if (typeof id !== "string" || !id || entries.some(entry => entry.id === id)) throw new Error("Unable to create a unique entry. Try again.");
    return [...entries, { id, ...fields(title, url), read: false }];
  }
  function toggle(entries, id) {
    return entries.map(entry => entry.id === id ? { ...entry, read: !entry.read } : entry);
  }
  function remove(entries, id) { return entries.filter(entry => entry.id !== id); }
  function visible(entries, unreadOnly) { return entries.filter(entry => !unreadOnly || !entry.read); }
  const api = { KEY, fields, decode, encode, add, toggle, remove, visible };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ReadingListCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
