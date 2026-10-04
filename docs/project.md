# Noetloom project framework

Noetloom supplies a method, bootstrap kit, and small local helpers for existing coding
agents. An agent creates or adopts the user's workspace and implements the requested
deliverable. Each resulting project owns its requirements, decisions, skills, plan,
feedback, checkpoint, and evidence without this conversation or private installations.

Product documentation and distributed guidance describe the current framework directly.
Use the faceted diamond symbol from ShardLoom's published GitHub as Noetloom's logo,
with its applicable asset notices and source provenance.

## Required behavior

- One active plan connects user intent, coherent outcomes, acceptance, and verification.
  Architecture reviews supply findings for intake; they do not become another queue.
- Reconcile new messages before resuming. Questions, suggestions, instructions,
  corrections, review evidence, and pause/resume have different effects.
- Preserve explicit reversals and deferred scope. Record capture, application, and
  delivered acknowledgement separately. Reopen only affected completed work.
- Keep generated projects self-contained and proportionate. Combined document roles
  are supported; decision and evidence directories appear when used.
- Supply a minimal template, lifecycle skills, small domain overlays, portable host
  instructions, and one canonical skill source with thin Claude compatibility entries.
- Demonstrate real generated applications and durable feedback/resume behavior. File
  generation, marker checks, and compatibility adapters alone are insufficient proof.
- Use this framework to operate Noetloom itself. Validate locally and through GitHub CI.
- Default to Apache-2.0 for framework implementation, lifecycle skills, helpers,
  documentation, and plugin integration. Designated original starter templates use
  MIT-0. Do not assign Noetloom's license or copyright owner to an independent user's
  application; preserve third-party terms. See [licensing.md](licensing.md).
- Build a reproducible skills-only OpenAI plugin from the same canonical sources,
  using the current portable manifest. Test installation, generation, feedback, and
  continuation. Prepare it for review; do not publish or submit it without further
  explicit authority. Keep hooks outside the public package and add no MCP server
  or runtime merely to package a plugin.

## Authority and boundaries

The user explicitly authorized this framework, scoped commits/pushes, GitHub CI repair,
and merge after completion. This does not authorize changing reference repositories,
deleting external artifacts, paid services, application deployment, or publishing
private skills. Generated projects receive their own user
authority; the template grants no external permissions.

No model API, daemon, agent runtime, vector database, marketplace, or orchestration
service is part of this scope. Native hooks are deferred until a real need and a
host-specific implementation can distinguish message origins. A plain continuation
does not add them back. Hosted Claude execution requires an available Claude host;
compatibility-file checks are reported separately. See [hosts.md](hosts.md).
