# tmux subagents design draft

Status: instruction skill with a planned automation layer. No bundled launcher
or cleanup command has been implemented. Launching one interactive Claude consultation
validated basic tmux use only, not the proposed recursive protocol.

## Accepted direction

- Use a standalone repository named tmux-subagents, with source under
  skills/tmux-subagents and a concise repository README.
- Children inherit their immediate parent's provider and profile unless
  explicitly overridden; this applies recursively.
- A non-work-to-work handoff must minimize private personal context and obtain
  confirmation before possible personal-data exposure unless that specific scope
  is already explicitly authorized. Check both supplied context and information
  the child may access, including automatically loaded instructions and memory.
  Carry the restriction into descendants and revisit it when access expands.
- Support Google Antigravity CLI (agy) alongside Claude Code and Codex. New agy
  children use Gemini Flash Latest by default; Pro Latest requires an explicit
  request scoped to the child or subtree. Provider/profile inheritance remains
  independent of model selection.
- Keep finished children open and record them in a central private registry.
  Provide agent-clean-fz to select and close agents, with rich preview, and
  remove entries only after verified closure.
- Check for exact-name collisions before spawning and handle tmux creation
  collisions as well, since two launchers can race after the preflight check.
- Defer agent-clean-fz rich preview implementation until the user reports that
  the parallel claude-code-session-resume-fz preview work is finished. Inspect
  and reuse its shared implementation then; do not create a duplicate now.

## Proposed packaging

Use skills/tmux-subagents/SKILL.md with any runtime scripts inside the skill
folder, so skill-only installation carries the necessary implementation.
Keep repo-level documentation and tests outside it. Keep local integration,
profile paths, actual project details, and runtime state outside public sources.

The skills CLI supports full GitHub tree URLs and direct local directory paths.
Thus a nested PE/skills/tmux-subagents folder is installable with an explicit
path even if root-level discovery misses it. A standalone repository simplifies
installation and independent releases. Installing skills is separate from
registering shell commands such as agent-clean-fz; document both explicitly.

Current skills CLI source honors CLAUDE_CONFIG_DIR for the global Claude skill
location. Installation can target each profile separately. A development checkout
can instead be symlinked into the documented agent skill directories.

## Automation work remaining

- One tmux session per agent remains the default design.
- Prefer a small portable helper for identity, central registry, spawn, results,
  ownership, and shutdown; the current draft is instructions only.
- Use one readable JSON registry at
  ${XDG_STATE_HOME:-$HOME/.local/state}/tmux-subagents/agents.json, overridable
  locally. It contains both working and finished records; the cleanup picker
  filters finished ones. Use a stable sidecar advisory lock and atomic file
  replacement for every update. SQLite is an alternative if transactional
  complexity outgrows this small registry; do not maintain competing stores.
- Explicit human hand-back remains the recommended default.
- Root-wide concurrency/depth defaults remain unspecified. Provider/profile
  inheritance and the agy Flash/Pro selection policy are settled.

## Cleanup behavior

List finished entries with outcome, project, provider/model/profile alias,
lineage, timestamps, result summary, artifact paths, and bounded terminal preview.
Revalidate selection under the same lock used by follow-up dispatch and child
creation, so a stale picker cannot close a newly busy agent or parent. Do not
implicitly close unselected descendants. Remove an entry after closure is
verified; failed closure remains visible. Preserve provider session history and
result artifacts. Preview functions must not interpret terminal output as shell
code and should remove unsafe terminal control sequences while preserving the
intended rendering.

## Consultation findings and decisions

A second agent recommended explicit task result artifacts and stable tmux IDs.
It preferred shorter names without model or ancestry. The draft retains those
fields because they are explicit user requirements, and distinguishes launch
model from effective model. It also suggested process restart for follow-ups;
that needs careful lifecycle handling and must not create simultaneous writable
copies of a provider conversation.

The installed Codex CLI exposes queue, resume, profile, and model options.
Queue delivery has not been behaviorally tested. The installed Claude CLI
exposes model, name, session-id, and resume. A real interactive consultation was
launched through an alternate local profile and remained open after answering.
Shell compatibility mattered: the first launcher selected an incompatible
system shell; the installed compatible shell succeeded.

## Validation before release

Validate skill frontmatter and cross-provider discovery. For a bundled helper,
exercise fake interactive children in a separate tmux socket: simultaneous
spawns, collisions, child/grandchild identity, result freshness, failed starts,
process exit without results, explicit human ownership, and subtree shutdown.
Then run authorized real CLI smoke checks for each configured provider/profile.
Do not describe fake-process checks or CLI help inspection as provider validation.

## Sources

- [Codex skill discovery](https://learn.chatgpt.com/docs/build-skills)
- [Claude skills and symlinks](https://code.claude.com/docs/en/skills)
- [Claude environment variables](https://code.claude.com/docs/en/env-vars)
- [Claude agent-team limitations](https://code.claude.com/docs/en/agent-teams)
- Installed Claude and Codex CLI help, inspected during design.

## Installation sources

- [Skills CLI source formats](https://github.com/vercel-labs/skills#source-formats)
- [Skills discovery implementation](https://github.com/vercel-labs/skills/blob/main/src/skills.ts)
- [Agent profile directories](https://github.com/vercel-labs/skills/blob/main/src/agents.ts)
- [Superpowers installation](https://github.com/obra/superpowers#installation)

## Packaging boundary

This release packages instructions, not an orchestration application. The skill
can guide direct tmux operations now. Automated register/finish/close operations
and agent-clean-fz are follow-up work, with preview implementation explicitly
waiting for the shared renderer to become available. Installing a SKILL.md does
not automatically put shell commands on PATH.

Keep local shell integration separate from the portable skill. Reuse the
completed session-resume preview renderer through that adapter; avoid an
undeclared dependency on a personal scripts checkout in the public skill.

## AGY support and validation

Verified installed agy help and the live agy models listing. The CLI exposes
--model, --prompt-interactive, --conversation, --effort, and --sandbox. Its model
listing uses versioned slugs, so Latest is a selection policy rather than an
assumed CLI alias. Filter by the requested Gemini family and resolve at launch;
store the result rather than hardcoding today's version in the skill.

The specific Flash default takes precedence over inheriting a Pro parent's
model. Explicit tree-wide Pro selection may propagate within that user-defined
scope. A request only for the parent does not authorize Pro for descendants.
This keeps delegation predictable while preserving explicit model choices.

The CLI's global Markdown skill directory differs from the app's documented
global skill directory. Document the CLI path separately instead of treating
the Skills CLI's antigravity target as proven AGY CLI installation support.

Checked instruction consistency and skill validation. An interactive AGY worker
and AGY skill discovery have not been smoke-tested in this change; no model
task was launched and no global profile or skill installation was modified.

Sources:

- [AGY model selection and resume](https://antigravity.google/docs/cli/headless/)
- [AGY CLI skills](https://antigravity.google/docs/cli/plugins/)
- [Antigravity app skills](https://antigravity.google/docs/skills/)
- Installed agy --help and agy models output.
