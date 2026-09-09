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
file tools. `scripts/` holds four small POSIX helpers (launch and register,
wait, status line, Codex notify adapter); the rich cleanup command is a planned
integration; do not claim it is installed.

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

### Launchers: prefer the local wrappers, fall back to the bare CLIs

On the author's machines three wrappers exist and are the preferred way to
start a child, because they carry the approval policy and profile that a bare
CLI would not:

- `claude-m`: the default-profile Claude Code launcher (today a plain
  pass-through to `claude`; keep using it so local policy can be added in one
  place).
- `claude-work`: Claude Code on the work profile (`CLAUDE_CONFIG_DIR` set to
  the work configuration directory, a distinct tty title marker).
- `codex-m`: Codex with the local security options, detailed reasoning
  summaries, web search and auto-approval, e.g.
  `codex-m --model <model> -c model_reasoning_effort=low '<prompt>'`.
  It may open with an AGENTS.md sync question before the prompt runs; the
  parent must answer it (`tmux send-keys -t <session> Enter` after checking
  the pane) or the child sits idle. Verified 2026-09-09 on four launches.

They are zsh shell functions, not executables: `command -v` from a bash
launcher or from a child's non-zsh shell reports nothing. Detect them with
`zsh -ic 'whence -w claude-m codex-m claude-work'`, and run them through the
user's shell (a tmux session started with the login shell sees them; a
`bash -c` line does not). If a wrapper is absent on the machine, fall back to
the bare `claude` / `codex` and supply the pieces the wrapper would have added
explicitly: `CLAUDE_CONFIG_DIR=<dir> claude ...` for a profile, and the
approval and sandbox flags the local runbook prescribes for `codex`. Say in
the brief and the registry which launcher actually started the child.

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

### Notifications: children push, parents do not poll

A tmux pane cannot wake its parent, so every delegation sets up a push
channel at launch. What follows was verified on 2026-09-09 (Claude Code
2.1.265, Codex CLI, macOS); the matrix is in the subsection after this one.

- **Claude Code child, same profile (same CLAUDE_CONFIG_DIR).** Launch with
  `--name <role>`. The child then appears in the parent's `ListAgents` with its
  tmux `session:window.pane`, and the parent appears in the child's. Put the
  parent's peer name (as `ListAgents` prints it) in the brief and require the
  child to `SendMessage` it on completion, block, or question, first line
  `COMPLETED`, `BLOCKED` or `NEEDS-INPUT`, then a two-line summary and the
  result-file path. It arrives as
  `<cross-session-message from="uds:..." from-name="<child>" ...>` and wakes an
  idle parent as a new turn. After launch, and after every follow-up, the
  parent calls `SendMessage(to: <child>, notify_when_idle: true)`; one
  `[Cross-session idle notice]` arrives when the child next ends a turn, even
  if the child forgot to report. Idle is not completion: read the result file.
- **Claude Code child, other profile.** Sessions under different
  CLAUDE_CONFIG_DIR values do not see each other in `ListAgents`, and
  `SendMessage` fails with "No agent named '<x>' is reachable" in both
  directions, although the sockets share one directory. Treat a cross-profile
  child like a Codex child (next item). For input, `tmux send-keys -l` into
  the child's pane works even while it is busy (the TUI queues typed text);
  respect the ownership rules above.
- **Codex, agy, or cross-profile child.** The brief requires the result file;
  the parent runs `scripts/tmux-subagent-wait.sh RESULT_FILE PANE_ID` in the
  background (Claude Code: Bash with `run_in_background`). It exits, and so
  notifies, on the first of: result file present, needs-input file present,
  pane dead (`remain-on-exit`), session gone. One notification per assignment;
  re-arm after each follow-up.
- **Turn-end hooks, without touching user config.** Codex: launch with
  `-c 'notify=["<abs>/tmux-subagent-codex-notify.sh","TASK","NODE",<original
  notify argv...>]'`; the adapter appends a `turn_end` line with the Codex
  payload (`thread-id`, `turn-id`, `last-assistant-message`) to the shared
  `status.jsonl` and then execs the original notify command with the same
  payload, so an existing bell keeps ringing. Claude: launch with
  `--settings '{"hooks":{"Stop":[{"hooks":[{"type":"command","command":"<abs>/tmux-subagent-status.sh TASK NODE completed -"}]}]}}'`;
  the `-` reads the hook JSON from stdin. `--settings` merges with, and does
  not replace, the user's settings. A `Notification` hook with matcher
  `permission_prompt` or `idle_prompt` can record `needs_input` the same way
  (documented, not exercised). A parent with many children can `tail -f
  status.jsonl` filtered by task ID (Claude Code: Monitor) instead of one
  waiter each. A turn end is not task completion.
- **Needs input.** A child that must ask writes `<result stem>.needs-input.md`
  beside its result file with the question and its default if unanswered. The
  waiter fires on it. The parent answers through `SendMessage` (same-profile
  Claude) or, under the ownership rules, through terminal input, deletes the
  needs-input file, and re-arms the waiter.
- Terminal captures remain diagnosis, never the completion signal.

### Verified 2026-09-09

Each test used two throwaway Haiku sessions launched by
`scripts/tmux-subagent-launch.sh` into a scratch directory, briefed by file to
log every `ListAgents`/`SendMessage` result and every incoming message verbatim.

- work -> work (`claude-work --name msgP`, `claude-work --name msgC`):
  visibility both ways: yes; child->parent `SendMessage`: delivered, woke the
  idle parent; parent->child with `notify_when_idle`: delivered, then one
  `[Cross-session idle notice] "msgC" ... is idle now` arrived when the child
  ended its turn.
- default -> work (`claude --name msgD` in the same cwd): `ListAgents` showed
  only default-profile peers; `SendMessage(to:"msgP")` and `(to:"msgC")`:
  `{"success":false,"message":"No agent named 'msgP' is reachable..."}`.
- work -> default: `SendMessage(to:"msgD")` from msgP: "No agent named 'msgD'
  is reachable. Did you mean: msgC?". A separate coordinator saw the same for
  its own work->default pair. No idle notice can be armed in either direction.
- `tmux-subagent-wait.sh`: exited on RESULT (0), NEEDS-INPUT (0), DEAD pane
  under `remain-on-exit` (1), and GONE session (1).
- Codex: `codex exec -c 'notify=[adapter,TASK,NODE,logger]' "Reply ok"` fired
  `notify` at turn end (`"client":"codex_exec"`); `status.jsonl` got the
  `turn_end` line and the chained logger received the identical payload.
- Claude: `claude -p --model claude-haiku-4-5-20251001 --settings '{...Stop
  hook...}' "Reply ok"` fired the hook; `status.jsonl` got the Stop payload
  (`session_id`, `transcript_path`, `cwd`, ...). Interactive `Stop` not
  separately exercised; it is the same hook.
- Not verified: `Notification` hooks; agy hooks; `codex queue`; behaviour when
  the parent is itself busy for a long time (the message queues, as observed
  for typed input, but ordering under load was not tested).
- Observed on the way: `--permission-mode auto` silently stayed "manual" on the
  work profile (organization policy; the default profile has auto), so a
  child prompted for its first file write; `acceptEdits` worked on both.
  Right after `tmux kill-session` one child `claude` process was still listed
  and exited a second later, so verify closure by PID, not by session name.

### Launch pitfalls (each cost real time)

- An interactive zsh may `cd` on startup, so `tmux new-session -c DIR` is not
  enough: prepend `cd DIR &&` to the command (`scripts/tmux-subagent-launch.sh`
  does this). Confirm the child's working directory from the pane before
  handing off; a child that starts in the wrong directory silently works on
  the wrong tree.
- First launch in a directory triggers trust prompts (Codex: "Do you trust
  the contents of this directory?"; Claude: "Is this a project you trust?").
  Pre-trust the directory in the provider config, or watch the pane for ~20 s
  after launch and answer with `tmux send-keys` before the child is handed to
  anyone.
- Unattended children need a non-interactive permission posture
  (Claude: `--permission-mode acceptEdits`, or `auto` where the account
  allows it; an organization policy can silently leave `auto` in manual mode,
  so check the child's status line; Codex: the approved local launcher's
  approval policy). Say so in the brief, and say that design questions are
  settled by the brief, so the child does not stall on a question nobody will
  answer.
- Give every child the same checkpoint duty as the parent: a progress note at
  a known path after each milestone, so a restart or a compaction can resume.
- The registry's `process_state` is not updated when a session finishes, so it
  can read "running" for a session that ended (both Codex sessions on
  2026-09-09). Determine liveness from the status script or the pane, not from
  the registry field.

### Coordinator handoff

A run longer than the parent's quota window ends with a *different* session
coordinating it. The protocol (handoff brief, successor launched on the other
profile with `--name`, old parent demoted to relay duty) is the
`long-run-handoff` skill; three rules bind this skill's plumbing:

- **The result file is the protocol.** Every child writes one at an assigned
  path, always, whatever else it does.
- **`SendMessage` is a courtesy.** It is a fast wake-up for a parent that still
  exists. A child that only messages its parent has reported to nobody once
  that parent is compacted, out of quota, or replaced.
- **Cross-profile children are file-only.** Neither direction can see or reach
  the other, so a successor on another profile inherits them as result files
  plus `tmux send-keys -l`, and the old parent must relay its own in-process
  children's reports into the shared results directory before it stops.

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

Use the selected local profile launcher (`claude-m` / `claude-work` where they
exist, see Launchers above). CLAUDE_CONFIG_DIR selects an alternate
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
local launcher (`codex-m` where it exists, see Launchers above) and preserve
the selected sandbox and approval policy.

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
