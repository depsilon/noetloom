# Approach

A static HTML form and list use plain CSS and JavaScript. `core.js` owns validation
and immutable state operations and also runs under Node's built-in test runner.
`app.js` owns DOM rendering, keyboard focus, and localStorage persistence. Titles are
inserted with textContent; links must be HTTP(S) without embedded credentials.

An operation persists successfully before replacing the displayed state. Storage
failures leave the previous list intact. Invalid stored data disables editing and
offers an explicit destructive reset with confirmation. The app does not send entries
to a server. A service worker caches only the known app shell at the local origin,
updates it while online, and supplies it when offline. There is no caching of saved
external links or unrelated paths.

The interface uses a two-column layout on wider screens and a single column below
620 pixels. Native controls have visible focus styles and explicit labels. Status
announcements and sensible focus after deletion preserve keyboard continuity.

## Framework maintenance

This maintained example retains the optional Noetloom helper profile. The readable
`.noetloom/operating-model.md` is the complete development method; `.noetloom/helpers.md`
documents the profile's records and checks. The marked plan JSON is the representation
of the single project plan. This framework refresh changes no application requirements
or deferred scope.
