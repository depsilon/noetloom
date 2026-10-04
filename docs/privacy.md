# Noetloom privacy

Noetloom is a local instruction and template package. It operates on the workspace
and input that you provide to your coding agent. Noetloom has no hosted service,
analytics, accounts, network client, or data collection endpoint. Its maintainer does
not receive your project files or conversations through the framework.

The local helper stores project requirements, selected feedback text, checkpoints,
test output, timestamps, and file hashes inside the selected workspace. These records
remain there until you edit or remove them. Keep credentials and unrelated sensitive
information out of feedback receipts and test output. The helper does not inspect
other conversations or automatically send records elsewhere.

Your chosen agent host processes the input and files you make available under its
own policies and permissions. Project checks are commands you or the agent configure;
inspect their behavior before executing an unfamiliar project. Git commits, cloud
sync, deployment, and sharing can transmit local records when you choose those actions.
Noetloom itself grants no authority for them.

You control local retention and sharing. Preserve any project evidence you need before
removing records. For support, use [GitHub issues](https://github.com/depsilon/noetloom/issues)
and share only a minimal, redacted example; public issues are visible to others and
are handled under GitHub's policies. No support account or additional login is
required to run Noetloom locally.
