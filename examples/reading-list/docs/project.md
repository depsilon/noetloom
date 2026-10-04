# Reading list

Keep a small reading list on one device, including offline use after the first
successful local HTTP load. Add a title and optional HTTP(S) link, mark entries read
or unread, filter unread entries, and remove entries. Preserve the list across reloads.

Use no accounts, authentication, sync, database service, remote assets, or dependencies.
Those features stay deferred unless explicitly requested. The app shell works without
its preview server after caching; following a saved external link can need a connection.
Browser storage is local to its origin. Clearing that storage removes the list.

Show useful empty, validation, and storage-error states. Preserve unreadable saved
data until the user explicitly chooses to reset it. Support keyboard operation and
narrow screens. Do not interpret saved titles as markup or accept executable URL schemes.

This is a maintained Noetloom example. Local implementation and verification are
authorized; there is no deployment or external messaging authority. The application
is Apache-2.0 as part of this repository. The included framework and original starter
materials retain the boundaries explained in `.noetloom/licenses/README.md`.
