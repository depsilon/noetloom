---
name: project-website
description: Design and verify a small website around its user flows, accessible interactions, responsive behavior, and explicit offline and data-storage choices.
---

# Website project guidance

Use this guidance for a website or browser-based interface. Choose the smallest architecture that supports the requested user flows; no framework, authentication system, or backend is compulsory.

## Record in the project and architecture owners

- Name the intended users, key flows, pages or views, and the important state each flow reads or changes.
- Record the accessibility behavior for navigation, keyboard focus, forms, validation, and loading, success, empty, and error status.
- Specify responsive layouts and the supported device or viewport range.
- Explicitly choose offline and network behavior, and where user data is stored, for how long, and how it can be cleared.

## Implementation boundaries

- Make each requested flow understandable and operable without relying on color, pointer input, or transient visual cues alone.
- Label form controls, associate errors with fields, preserve useful user input on recoverable errors, and announce changing status accessibly.
- Handle unavailable network or storage according to the recorded choice; do not imply that data was saved or sent when it was not.
- Keep data collection and dependencies within the stated project scope.

## Verify

- Exercise primary browser interactions, including navigation, form success, validation errors, and relevant empty or failure states.
- Check keyboard-only use, visible focus, labels and status announcements, and responsive behavior at narrow and wide viewports.
- Reload after state-changing flows and confirm persistence, reset, and offline behavior match the documented choices.
- Test the rendered site in a browser on desktop and a mobile-sized viewport.
