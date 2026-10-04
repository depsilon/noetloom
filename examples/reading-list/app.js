"use strict";
(() => {
  const core = window.ReadingListCore;
  const get = id => document.getElementById(id);
  const form = get("entry-form"), list = get("entries"), status = get("status"), storageError = get("storage-error");
  let entries = [], damagedStorage = false;
  function render(focusID) {
    list.replaceChildren();
    const shown = core.visible(entries, get("unread-only").checked);
    get("count").textContent = `(${entries.length})`;
    get("empty").hidden = shown.length > 0;
    get("empty").querySelector("p").textContent = entries.length ? "All caught up." : "Room for your next discovery.";
    get("empty").querySelector("span").textContent = entries.length ? "Show all entries or add something new." : "Add a title to start your list.";
    for (const entry of shown) {
      const row = document.createElement("li");
      row.className = "entry" + (entry.read ? " read" : "");
      const content = document.createElement("div"), title = document.createElement("h3");
      title.className = "entry-title";
      if (entry.url) {
        const link = document.createElement("a");
        link.href = entry.url; link.target = "_blank"; link.rel = "noopener noreferrer"; link.textContent = entry.title;
        title.append(link);
      } else title.textContent = entry.title;
      const meta = document.createElement("p");
      meta.className = "entry-meta";
      meta.textContent = (entry.read ? "Read" : "Unread") + (entry.url ? " · " + new URL(entry.url).hostname : "");
      content.append(title, meta);
      const actions = document.createElement("div"); actions.className = "entry-actions";
      const toggle = document.createElement("button");
      toggle.type = "button"; toggle.dataset.entry = entry.id; toggle.textContent = entry.read ? "Mark unread" : "Mark read";
      toggle.setAttribute("aria-label", `${toggle.textContent}: ${entry.title}`);
      toggle.addEventListener("click", () => commit(core.toggle(entries, entry.id), entry.read ? "Marked unread." : "Marked read.", entry.id));
      const remove = document.createElement("button");
      remove.type = "button"; remove.className = "remove"; remove.textContent = "Remove";
      remove.setAttribute("aria-label", `Remove: ${entry.title}`);
      remove.addEventListener("click", () => commit(core.remove(entries, entry.id), "Entry removed.", entry.id));
      actions.append(toggle, remove); row.append(content, actions); list.append(row);
    }
    if (focusID) {
      const button = [...list.querySelectorAll("button[data-entry]")].find(element => element.dataset.entry === focusID);
      (button || get("list-heading")).focus();
    }
  }
  function commit(next, message, focusID) {
    if (damagedStorage) return false;
    try {
      window.localStorage.setItem(core.KEY, core.encode(next));
    } catch {
      storageError.textContent = "Your browser could not save this change. The list is unchanged. Check available storage or browser permissions, then try again.";
      status.textContent = "";
      return false;
    }
    entries = next; storageError.textContent = ""; status.textContent = message + " Saved on this device.";
    render(focusID); return true;
  }
  form.addEventListener("submit", event => {
    event.preventDefault(); get("form-error").textContent = "";
    get("title").removeAttribute("aria-invalid"); get("url").removeAttribute("aria-invalid");
    try {
      const next = core.add(entries, get("title").value, get("url").value, crypto.randomUUID());
      if (commit(next, "Added to your list.")) { form.reset(); get("title").focus(); }
    } catch (error) {
      get("form-error").textContent = error.message;
      const input = !get("title").value.trim() ? get("title") : get("url");
      input.setAttribute("aria-invalid", "true"); input.focus();
    }
  });
  get("unread-only").addEventListener("change", () => {
    render();
    const count = core.visible(entries, get("unread-only").checked).length;
    status.textContent = `${count} ${count === 1 ? "entry" : "entries"} shown.`;
  });
  get("reset").addEventListener("click", () => {
    if (!window.confirm("Remove the unreadable saved list from this browser? This cannot be undone.")) return;
    try {
      window.localStorage.removeItem(core.KEY);
      damagedStorage = false; entries = []; storageError.textContent = ""; get("reset").hidden = true;
      form.querySelector("button").disabled = false; render(); status.textContent = "Saved list reset. Add a new entry to begin.";
    } catch { storageError.textContent = "The saved list could not be reset. Check browser storage permissions."; }
  });
  try { entries = core.decode(window.localStorage.getItem(core.KEY)); }
  catch (error) {
    damagedStorage = true; storageError.textContent = error.message || "Browser storage is unavailable. Nothing was overwritten.";
    form.querySelector("button").disabled = true; get("reset").hidden = false;
  }
  render();
  if (location.protocol === "file:") {
    get("offline-state").textContent = "Local files. No account.";
  } else if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("./sw.js").then(() => navigator.serviceWorker.ready)
      .then(() => { get("offline-state").textContent = "Ready for offline use."; })
      .catch(() => { get("offline-state").textContent = "Offline refresh unavailable."; });
  }
})();
