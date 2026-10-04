# Working examples

These are maintained examples, not the destination for projects created by users.
Copy one elsewhere to inspect its local records, or ask an agent to create a new
workspace using [BOOTSTRAP.md](../BOOTSTRAP.md).

| Project | Actual application | Evidence |
| --- | --- | --- |
| [Expense totals](expense-totals/README.md) | Python CSV CLI with exact decimal totals, refunds, category filtering, and strict input errors | Behavioral CLI tests; independent creation and fresh-session feedback/resume exercise; local completion history |
| [Reading list](reading-list/README.md) | Static offline reading list with local persistence, read toggles, filtering, and error states | Node behavioral tests; recorded desktop/mobile browser observations with source fingerprints and screenshots |

Each includes its own helper, canonical lifecycle/domain skills, thin Claude entries,
manifest, owners, and evidence. Neither needs this repository on Python's import path.
The CLI example combines document roles; the website keeps separate owners. The
examples' applications are Apache-2.0 as repository code. This does not assign the
same license to independent applications made with the generator.

The expense example's feedback log labels the simulated correction, question, pause,
and resume used to test the framework. The new agent received local project files
and “Continue,” without the original conversation or private skills. It preserved
deferred sharing, databases, and authentication while implementing the requested
filter. A later arithmetic review exposed and repaired a large-value precision bug.
Historical records are retained; current completion points to the revalidated result.

![Reading-list desktop result](reading-list/evidence/reading-list-desktop.jpg)
