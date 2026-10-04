# ToolShelf

Build a functioning local command-line application for a neighborhood tool library.
The volunteer should be able to keep a catalog of tools with unique asset IDs and
names; see what is available; lend a tool to a named borrower with a due date; return
it while preserving loan history; and list overdue loans relative to an explicit
date. Prevent double loans and invalid state transitions.

The volunteer also needs safe CSV catalog import with a preview before writing,
clear row errors, and no partial writes when a batch is invalid. Export inventory
and loan history in useful files for recovery or transfer. Save data across process
restarts and keep invalid requests from corrupting it. Make the program easy to run
with Python 3.11+ and the standard library on this machine. Choose the module layout,
command design, and storage approach using ordinary engineering judgment.

Completion means the working local application, meaningful automated tests, and
clear usage instructions, with a representative full user journey and failure paths
actually exercised. Derive and maintain a project-specific phased implementation plan
and relevant local guidance while implementing. Use the supplied readable operating
method in reference/OPERATING-METHOD.md. There is no prepared plan or application code.

Keep the application offline and local. Shared dashboards, authentication, cloud sync,
web interfaces, and notifications are deferred unless a later explicit request changes
that decision. Local file changes and ordinary application/test commands are authorized.
Remote publication, deployment, external services, spending, and messaging people are
outside this exercise. Do not install third-party dependencies.
