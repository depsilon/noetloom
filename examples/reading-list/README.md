# Reading list

Open `index.html` in a current desktop browser. All application files are local;
there are no remote assets, accounts, or application server. Add a title and optional
HTTP(S) link, mark it read/unread, filter unread entries, and remove entries.

Entries persist in this browser's local storage. Clearing browser data removes them.
Linked articles are not downloaded and may need a network connection. Browser policy
for storage under `file://` varies. For a stable localhost origin, run
`python3 -m http.server 8765 --bind 127.0.0.1` and open `http://127.0.0.1:8765/`.
That server only serves static files; it stores no data. Once the page says
“Ready for offline use,” its local service worker has cached the application files
for offline reloads. This browser cache is not a Noetloom agent or background worker
and performs no sync. Clearing site data removes both the list and offline cache.

If a write fails, the app keeps the previous list and reports that the change was not
saved. Unreadable saved data is preserved until the user explicitly resets it.

Run `node --test tests/core.test.cjs` for the state and persistence-contract tests.
Browser exercises are recorded in the project's validation owner. The local framework
is independent of the Noetloom source checkout; start a new session with `AGENTS.md`.
