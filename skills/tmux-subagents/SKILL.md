---
name: tmux-subagents
description: Launch and coordinate Claude Code, Codex, or Google Antigravity (agy) agents in tmux when delegated work should remain inspectable and interactively usable by the user, including recursive child agents.
---

# tmux subagents

## Shared workflow

Use full interactive agent sessions in detached tmux sessions. Each delegated
agent must be independently attachable, have a bounded assignment, and retain
its connection to the parent. Read the provider section for the child being
launched, which may differ from the parent provider.

This is an instruction skill: perform the workflow using the host's shell and
file tools. A bundled launcher and central-registry automation are not provided.
The rich cleanup command is a planned integration; do not claim it is installed.

Use a common operation vocabulary across providers: start, inspect, send, wait,
interrupt, and stop. Keep provider-specific launch and input delivery details in
the relevant section below. Waiting may be on demand or bounded in the
background; choose according to the parent's task rather than imposing a patrol
loop or leaving an assigned task unattended.

### Prepare a delegation

Children inherit their immediate parent's provider and profile unless the user
explicitly specifies an override. Apply this at every depth, including children
of a parent launched with an override. Record the resolved provider and profile
in child context rather than relying on ambient tmux environment. Model selection
is separate: agy children default to Gemini Flash Latest; Gemini Pro Latest
requires an explicit user request covering that child or subtree.

Honor explicit model choices within their stated scope, and otherwise apply the
child provider's model policy. Carry forward the project directory, permissions,
and delegation limits. Local profile configuration supplies the
trusted launcher executable or shell function and any required shell. Do not
assume a shell function is an executable or that the system shell can load the
user's configuration. Do not import an entire parent environment into the tmux
server or bypass permissions to make a child launch succeed.

Give the child a task brief with the objective, relevant context, allowed file
ownership, expected deliverable, verification expectations, and a unique task
ID and result-file path. Include the location of this skill and the inherited
root and parent identity so grandchildren can use the same workflow. A new CLI
session does not automatically inherit the parent's conversation.

Keep the current branch and worktree unless the user authorized another
arrangement. Coordinate ownership when agents share a checkout; a tmux session
provides terminal separation, not filesystem isolation. Check delegated work
before incorporating it into the parent's answer or changes.

### Personal-to-work profile handoff

Before a non-work parent delegates to a work profile, check whether the child
might receive or access private personal information. Use the user's local
profile classification; do not assume that a display name proves account scope.
Review the brief and the context the child may load: workspace files, inherited
instructions, memory/history, attachments, and connected tools. A sanitized
prompt alone does not prevent access through those other routes.

Prepare the smallest useful brief and access scope, excluding unrelated personal
information. If the child might still need or encounter private personal data,
confirm with the user before launch or before granting the additional access.
Explain which information could be exposed, why it may be needed, and whether a
sanitized handoff or staying on the non-work profile would suffice. Do not quote
sensitive contents merely to ask the question. Choosing a work profile alone is
not consent to expose personal information. Existing explicit authorization for
this delegation's data and access scope suffices; do not ask again for that same
scope. If the scope expands, obtain confirmation for the additional exposure.

Carry these boundaries into the child brief and descendant delegations. When
confirmation is needed, keep the work-profile handoff pending and continue only
work that does not expose that information. A profile switch or tmux session is
not a data-isolation boundary, and this instruction skill does not enforce one.

### Identity and names

Use one tmux session per agent. Name it:

    ag--<project>--<run>--<lineage>--<provider-model>--<role>

A fictional child and grandchild:

    ag--demo--review-k7m2--r-a3--claude-opus--review
    ag--demo--review-k7m2--r-a3-b8--codex-modelx--tests

The project is a short, non-sensitive alias. The run combines a human-readable
session label with a collision-resistant run ID. Lineage starts at r and
appends a unique node token at each delegation. The provider-model field is a
sanitized display label; retain the exact model string separately. Use only
lowercase ASCII letters, digits, and single hyphens within each field, with
double hyphens separating fields. Normalize punctuation such as model-version
periods; reject empty or ambiguous fields.

Store stable node ID, root ID, immediate parent ID, full lineage, requested
model, observed model when available, provider, local profile reference, task
ID, working directory, and tmux socket/session/pane IDs in private local
metadata. Capture tmux IDs at creation, for example with new-session -P -F.
Use those IDs for subsequent operations. Names are useful labels, not the
identity database. Record an external parent without inventing a tmux pane.

Check the intended socket for an exact existing session name before creation,
including running agents and retained completed sessions. Never replace a
pre-existing session on a name collision. A preflight check can race with another
launcher: treat tmux's creation result as authoritative, and on duplicate-name
failure allocate another ID and retry creation. Coordinate any
shared counters or registry updates atomically. Do not silently adopt a session
from an earlier run. Keep labels short without discarding required identity;
if depth makes full lineage unwieldy, agree on abbreviated ancestry first.

Distinguish the requested model from an observed effective model. Update the
model label when a switch is known. If no reliable model-change signal exists,
identify the label as the launch model rather than asserting it is current.
Disable automatic renaming only on windows owned by this workflow.

### Launch and inspect

Launch detached without selecting the user's terminal or detaching an existing
client. Pass command arguments as an argv array where supported; otherwise use
correct shell quoting. Do not interpolate task text as executable shell code.
For sensitive briefs, prefer a private file and a short instruction to read it
rather than embedding its contents in a process command line.

Retain the pane on process exit so startup failures remain inspectable. Verify
that the requested agent actually started; creation of a tmux session alone is
not proof. Record blocked authentication or permission prompts accurately.

Give the user the session name and commands to inspect and attach. Read-only
inspection can use tmux capture-pane or tmux attach-session -r. Normal attach
allows interaction. Within tmux, switching clients is a human choice; the
parent must not silently switch the user's session.

### Results, follow-ups, and human control

Track process state independently from task outcome. A live CLI may have
finished its assignment; an exited CLI may have failed without a result.

Require a per-assignment result file containing task_id, node_id, outcome
(completed, blocked, or failed), summary, artifacts, and verification. Write a
complete temporary file beside the result and atomically rename it into place
before ending the turn. Repeat this instruction in follow-up assignments. Use
new task IDs so a previous result cannot satisfy a new assignment.

Lifecycle hooks, where supported and verified, can report working, waiting,
or input-needed states. A turn-ending hook is not proof that the assignment
finished: use the explicit task result, and account for background work. An
optional status-plugin bridge should consume these states without becoming the
source of truth for results or cleanup.

The parent validates the IDs and reads the artifact. Terminal captures are for
inspection and diagnosis, not a machine completion protocol. A missing result
is unknown; silence, a prompt, or a timeout does not prove completion. Report a
missing or blocked result and investigate rather than automatically restarting
an agent that may still be working.

Use explicit human ownership before accepting human input. While a user owns
a child, the parent queues follow-ups and does not inject input, resume another
copy of its conversation, interrupt it, or close it. Hand-back is explicit;
detachment or elapsed time alone does not grant ownership back. This convention
requires cooperation and does not technically prevent typing through raw tmux.

Prefer verified provider message delivery over terminal keystrokes. When only
terminal input is available, coordinate ownership and known input readiness,
and use literal text or a private paste buffer. Do not paste into an unknown
permission modal or while the user is typing. Ownership checks and delivery
must share a lock if automated; separate check-then-send operations can race.

Leave finished children open and register them centrally for user-selected
cleanup. Use one private registry shared across projects and providers, keyed
by stable node IDs, with explicit task outcome and process state. The canonical
location is ${XDG_STATE_HOME:-$HOME/.local/state}/tmux-subagents/agents.json;
permit an explicit local override. Record its absolute path in child context. Serialize
updates so concurrent children cannot overwrite one another. Atomically publish
updates; an append-only completion log alone cannot support safe removal.

The planned agent-clean-fz command selects finished children with a rich preview
of task/result, project, provider/model/profile alias, ancestry, timestamps,
process state, and recent terminal output. Keep preview data local. A follow-up
must mark the child busy again; re-check state and ownership under the dispatch
lock before closing anything selected from an older list. Coordinate cleanup
with new child creation too. Close selected nodes only; do not silently close
unselected descendants. Block parent cleanup while live descendants depend on
it unless a subtree cleanup was explicitly selected.

After authorized closure, verify the owned processes and tmux session are gone,
then remove the entry from the central cleanup registry. Preserve failed-close
entries with a useful error. Already closed sessions may be reconciled only
after identity and process checks. Closing a terminal does not delete provider
conversation history or result artifacts. Killing a pane does not prove its
subprocesses died. agent-clean-fz and the registry are specified here but are
not yet implemented by this instructions-only draft.

### Recursive delegation

A child inherits the run and project identity, records itself as the immediate
parent of its children, and uses these same instructions. Pass identity through
an explicit task context or per-child environment; do not mutate the global
tmux server environment to announce the current parent. Verify context reaches
the child's shell tools because provider environment filtering can remove it.

Respect the root's limits across the whole tree. Local per-parent limits do not
bound total fan-out. If enforcing shared limits, reserve and release slots
atomically and account for failed launches. A child must not increase its own
permissions, recursion allowance, or concurrency allowance.

## Claude Code instructions

Use the selected local profile launcher. CLAUDE_CONFIG_DIR selects an alternate
configuration directory; default-profile configuration can depend on leaving
that variable unset. Keep account paths and launcher mappings in local config,
and do not accidentally inherit a different profile from the tmux server.

Inspect installed CLI help before depending on flags. Interactive Claude Code
accepts an initial prompt; --model selects a model, --name supplies a display
name, and --session-id accepts a UUID. Retain the provider session ID separately
from the tmux and workflow IDs. Resume a stopped session using its explicit ID
and the same profile; do not use a directory's most recent session implicitly.
Do not resume a second writable copy of an already running conversation.

--print and its JSON output modes are noninteractive and do not by themselves
provide the live TUI required by this workflow. Native agent teams are a
separate feature; do not assume they support nested teammates.

Install the shared skill through a symlink in the profile's personal skills
directory. Keep shared frontmatter portable; Claude-specific substitutions,
context: fork, and tool-permission fields must not redefine the common workflow.

## Codex instructions

Inspect installed CLI help independently of Claude's syntax. Interactive codex
accepts an initial prompt and --model. Its configuration profile and CODEX_HOME
are separate concepts from Claude's configuration directory. Use the approved
local launcher and preserve the selected sandbox and approval policy.

Use an explicit provider session ID for codex resume. Do not use --last when
other agents can create sessions concurrently. Record the Codex conversation ID
when available rather than inventing a Claude-style --session-id launch flag.

If installed help exposes codex queue --thread ID --message TEXT, evaluate it
as the preferred follow-up transport. Verify delivery, idle-session behavior,
and interaction with human ownership before automating it. Help availability
alone does not establish reliable end-to-end behavior.

codex exec is noninteractive. Native agent tools, when available, have their own
lifecycle and do not automatically produce the tmux sessions described here.
A parent sandbox may deny access to the tmux socket; use the host's authorized
approval mechanism and report actual launch failures.

The documented user skill discovery directory is ~/.agents/skills, and symlinked
skill directories are supported. Optional agents/openai.yaml metadata belongs
to Codex; keep the shared SKILL.md usable by Claude without it.

## Google Antigravity (agy) instructions

Use Google's agy executable or the selected local launcher; do not substitute
the separate gemini CLI. Inherit the parent's provider and profile as above.
Keep local account selection in the launcher configuration: do not invent an
agy --profile flag or assume Claude/Codex profile variables apply to it.

### Model policy

Default every new agy child to Gemini Flash Latest. Use Gemini Pro Latest only
when the user explicitly requests Pro for that child or its subtree. A Pro
parent alone does not select Pro for its children. Do not automatically upgrade
to Pro for task difficulty, quota failures, or unavailable Flash models.

Resolve Latest through agy models in the selected profile at launch time:
choose the newest available version in the requested Gemini Flash or Gemini
Pro family, then pass its exact supported slug to --model. Honor a requested
effort when selecting its variant, and verify supported effort values against
agy --help. Do not assume literal gemini-flash-latest or gemini-pro-latest aliases
are accepted. Treat Flash-Lite, non-Gemini models, and another model family as
different choices. If the requested family or effort cannot be resolved, report
the limitation instead of silently substituting a different one.

Record both the policy (Gemini Flash Latest or Gemini Pro Latest) and the exact
resolved slug in local metadata. Put agy and the sanitized concrete model in
the session name; leave the current version out of reusable defaults so Latest
continues to track available releases.

### Interactive launch and resume

Inspect agy --help before using flags. With a model resolved above, launch an
interactive initial turn inside the owned tmux session using:

    agy --model "$resolved_model" --prompt-interactive "$initial_prompt"

For sensitive context, initial_prompt should point to the private task brief
rather than contain it. --prompt-interactive keeps the session interactive;
--print, --prompt, and their structured-output modes are headless alternatives.
Preserve the user's sandbox and permission settings through the local launcher.

Record the conversation ID when available. Resume a stopped conversation with
agy --conversation "$conversation_id" under its owning profile. Avoid --continue,
which can select another agent's most recent conversation. Do not open concurrent
writable copies. If no verified message-queue interface exists, use the shared
human-ownership and coordinated terminal-input workflow for live follow-ups.

### Skill loading

AGY CLI documents global Markdown skills under
~/.gemini/antigravity-cli/skills/. Expose this SKILL.md there as
tmux-subagents.md and verify /tmux-subagents in the installed CLI. Its global
CLI path differs from the Antigravity app's documented skills path; do not
assume an installer target for the app also configures agy. For a delegated
worker, also provide the skill's absolute path in the brief so it can read the
same instructions if discovery is unavailable.

## Privacy

Keep published instructions and examples generic. Store runtime briefs,
transcripts, absolute workspace paths, profile mappings, result files, and
conversation IDs outside tracked skill sources with owner-only access. Do not
copy credentials or environment dumps into task context or metadata. Naming
uses display aliases because terminal labels and screenshots can expose them.
A separate repository is an organizational boundary, not a privacy guarantee.

## Design references

For installation, see the repository README. The repository's docs/design.md
records pending automation, and docs/related-projects.md explains evaluated
integrations. They are maintainer references; using the installed skill does
not require those repository-level files.
