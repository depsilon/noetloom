const test = require("node:test");
const assert = require("node:assert/strict");
const core = require("../core.js");

test("add, mark, filter, remove and reload preserve real reading state", () => {
  const empty = [];
  let entries = core.add(empty, " The Dispossessed ", "https://example.org/book", "one");
  entries = core.add(entries, "A paper to read", "", "two");
  assert.deepEqual(empty, []);
  assert.equal(entries[0].title, "The Dispossessed");
  const toggled = core.toggle(entries, "one");
  assert.equal(entries[0].read, false);
  assert.deepEqual(core.visible(toggled, true).map(entry => entry.id), ["two"]);
  const reloaded = core.decode(core.encode(toggled));
  assert.deepEqual(reloaded, toggled);
  assert.equal(core.remove(reloaded, "one").length, 1);
  assert.equal(core.toggle(reloaded, "one")[0].read, false);
});

test("reject blank titles, unsafe links, credentials, oversize fields and duplicate identifiers", () => {
  for (const [title, url] of [[" ", ""], ["x".repeat(201), ""], ["Title", "javascript:alert(1)"],
    ["Title", "file:///etc/passwd"], ["Title", "bad URL"], ["Title", "https://user:pass@example.org"],
    ["Title", "x".repeat(2049)]]) {
    assert.throws(() => core.add([], title, url, "id"));
  }
  const list = core.add([], "Title", "", "id");
  assert.throws(() => core.add(list, "Title 2", "", "id"));
});

test("storage validation refuses malformed data instead of silently losing it", () => {
  assert.deepEqual(core.decode(null), []);
  for (const raw of ["garbage", "{}", "null", '{"version":2,"entries":[]}',
    '{"version":1,"entries":[{"id":"a","title":"x","url":"","read":"false"}]}']) {
    assert.throws(() => core.decode(raw));
  }
  const entry = { id: "a", title: "x", url: "", read: false };
  assert.throws(() => core.decode(JSON.stringify({ version: 1, entries: [entry, entry] })));
});

test("user strings remain data, including markup and Unicode", () => {
  const title = '<img src=x onerror="alert(1)"> — 読書';
  assert.equal(core.decode(core.encode(core.add([], title, "", "id")))[0].title, title);
});
