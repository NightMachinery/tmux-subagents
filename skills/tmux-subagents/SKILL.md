---
name: tmux-subagents
description: Launch and coordinate Claude Code, Codex, or Google Antigravity (agy) agents in tmux when delegated work should remain inspectable and interactively usable by the user, including recursive child agents.
---

# tmux subagents

## Shared workflow

Prepare a private brief, launch one detached interactive tmux session, verify
startup, arm notifications, and validate the child's result. Every child stays
attachable, holds one bounded assignment, and reports through its assigned
result file. In order: brief and task ID (Prepare), data access (Privacy), name
and registry entry (Identity), launch and inspect (Launch), arm the push channel
(Notifications), validate the result (Results), follow up or hand over
(Ownership), leave open until closure is authorized (Cleanup).

Use the host's shell and file tools, and read the provider section for the
child, which may differ from the parent's. Needs tmux, zsh, Python 3, and the
authenticated CLI you launch, plus the portable `agent-session` zsh plugin.
Set `AGENT_SESSION_PLUGIN` to its absolute `.plugin.zsh` entrypoint; the launcher
also accepts `--plugin` and detects `~/scripts/zshlang/plugins/agent-session`
locally. Installation instructions are in the repository README. Missing plugin
is a setup error; never substitute a new conversation for unavailable resume. `$skill_dir` is the directory holding this
SKILL.md; its helpers are not on PATH, so call them by absolute path (Scripts).
This skill installs no cleanup command; Cleanup is a procedure, with a local
implementation named there.

## Prepare a delegation

Write the child's brief with the inherited provider and profile, authorized
scope, owned files, root limits, task ID, and artifact paths.

Children inherit their immediate parent's provider and profile unless the user
explicitly overrides it, at every depth, including children of an overridden
parent. Record the resolution in the brief; never rely on the ambient tmux
environment, never import a parent environment into the tmux server. Model
selection is separate and follows the child provider's policy.

A child never widens its own permissions, recursion, or concurrency allowance,
and a parent never bypasses permissions to make a launch succeed. Root limits
bind the whole tree; per-parent limits do not bound fan-out. Reserve and release
shared slots under the registry lock, counting failed launches.

Create the private task directory before writing into it:

    umask 077
    state_dir="${TMUX_SUBAGENTS_STATE:-${XDG_STATE_HOME:-$HOME/.local/state}/tmux-subagents}"
    task_dir="$state_dir/tasks/$task_id"
    mkdir -p "$task_dir"; chmod 700 "$state_dir" "$state_dir/tasks" "$task_dir"

It holds `brief.md`, `checkpoint.md`, `result.md`, `result.needs-input.md`, and
the launch context; an existing directory needs the same permissions. The brief
is a file the child reads, since the helper's environment variables brief
nobody. It states:

- objective, verification expectations, deliverable;
- owned paths, and the assumptions the child may make unasked, so it never
  stalls on a question nobody will answer; blocking questions go to the
  needs-input file;
- resolved provider, profile, model, launcher, and the permission flag used;
- root, parent, node and task IDs, and this skill's absolute path, so
  grandchildren use the same workflow;
- registry, result, needs-input and checkpoint paths, and who to notify.

Give every child the parent's checkpoint duty: a progress note at that path
after each milestone, so a restart or compaction can resume. Keep the current
branch and worktree unless authorized otherwise; a new CLI session does not
inherit the parent's conversation. Resolve overlapping writes before dispatch,
and check delegated work before folding it into the parent's output.

## Privacy and the work-profile handoff

Minimize the child's data access, and obtain any missing authorization before
exposing personal information to a work profile. A tmux session, a profile
switch, and a separate repository are organizational boundaries, not data
isolation, and this skill enforces none of them.

Before a non-work parent delegates to a work profile, review what the child
receives and what it can reach — workspace files, inherited instructions, memory
and history, attachments, connected tools — using the user's local profile
classification; a display name does not prove account scope, and a sanitized
prompt closes none of those routes.

Prepare the smallest useful brief and access scope. If private personal data
could still be reached, confirm first: say what could be exposed, why it may be
needed, and whether a sanitized handoff or staying on the non-work profile would
do, without quoting sensitive contents. Choosing a work profile is not consent.
Authorization already given for this scope is enough; ask again only when it
expands. Until answered, keep the handoff pending and continue only work that
does not expose the information. Carry these boundaries into descendant
delegations.

Keep briefs, transcripts, absolute workspace paths, profile mappings, results,
and conversation IDs under `$state_dir`, owner-only (700 directories, 600
files), never in tracked skill sources. Never put a sensitive brief on a command
line, where the process table shows it: write it to the task directory and tell
the child to read it. Published examples use generic display aliases, because
terminal labels and screenshots leak names. Never copy credentials or
environment dumps into task context or metadata.

## Identity and the registry

Allocate node and task IDs, capture tmux IDs at creation, and store the mapping
in the private shared registry. One tmux session per agent, named:

    ag--<project>--<task>--<provider-model>--<suffix>
    ag--demo--review-parser--claude-opus--a73f20

Generate the name with `tmux-subagent-name.sh PROJECT TASK PROVIDER-MODEL`.
Use short non-sensitive project and task labels describing the work. The helper
normalizes punctuation and whitespace to hyphens and adds a random six-character
suffix. Keep the run and full ancestry in metadata (`--run`, `--lineage`), not
the name. Retain the `ag--` prefix so local autonaming hooks leave it alone.

Operate on captured tmux IDs, not names (`new-session -P -F` prints them; the
helper passes them through). The pane id (`%N`) is the stable handle for
inspection, input, and the waiter. A session name recorded at launch can go
stale: on the author's machine a SessionStart/UserPromptSubmit hook renames
non-`ag--*` sessions after the agent's title. Worse, tmux reads a target by its
first character, `%` a pane, `$` a session, `@` a window, so a renamed session
whose title happens to start with `@` is parsed as a window id and cannot be
addressed by name at all. Never address a child by session name after launch;
use `%N`, or the `$N` from `tmux display -p -t "$pane" '#{session_id}'`. Store
node, root and parent IDs, lineage, requested model, observed model when known,
provider, local profile reference, task ID, launcher, working directory, and
tmux socket/session/pane IDs. Record an external parent without inventing a tmux
pane. The name carries the launch model and stays stable; a known switch updates
the metadata.

The registry is one readable JSON file shared across projects and providers,
keyed by node ID, at
`${XDG_STATE_HOME:-$HOME/.local/state}/tmux-subagents/agents.json` unless
`TMUX_SUBAGENTS_STATE` overrides it; put its absolute path in the brief. Every
writer holds the stable `agents.json.lock` sidecar across the whole
read-update-replace cycle and publishes through a unique temporary file in the
same directory, as the launch helper does; an append-only log cannot support
safe removal, and follow-up dispatch and cleanup take the same lock.

The helper stores one entry per launch (identity, lineage, task ID, workdir,
socket, session and pane IDs, `created`, `process_state: running`,
`task_outcome: unknown`); the rest is manual. Two consequences, both seen
2026-09-09: `process_state` is never updated at session end and read `running`
for two finished Codex sessions, so take liveness from the pane or the status
log, never that field; and the key is the session name, so identical names on
two tmux sockets would overwrite one record.

Check the intended socket for that exact name before creating a session,
including retained finished ones, and never replace a pre-existing session. The
preflight can race another launcher: tmux's creation result is authoritative,
the helper exits 2 on a duplicate, and the caller then allocates another ID and
retries. Never silently adopt a session from an earlier run.

## Launch and inspect

Run the resolved launcher through the launch helper, then read the pane to
verify the working directory, the permission posture, and that the task started:

    TMUX_SUBAGENT_PARENT="$parent_id" TMUX_SUBAGENT_ROOT="$root_id" \
      "$skill_dir/scripts/tmux-subagent-launch.sh" --task "$task_id" \
      --resume-command "$resume_command" --run "$run_id" --lineage "$lineage" \
      "$name" "$workdir" "$launch_command"

It prints `NAME SESSION_ID PANE_ID`; capture all three. COMMAND is shell code,
not a prompt and not an argv array: it needs shell quoting, and task text is
never interpolated into it. The helper detaches without touching the user's
terminal, keeps the pane after exit, wires the turn-end hook (Notifications),
and registers the session.

Supply `resume_command` as shell code calling the shared plugin, for example:

    agent-session-resume-exact codex "$AGENT_SESSION_ID" "$AGENT_SESSION_CWD" codex-m --model MODEL

Keep these variables literal until resume. Use the same launcher, profile,
model and permission settings as the initial command, without its initial
prompt. The helper persists and reapplies notification flags automatically.
Pass `--provider claude|codex|agy` for an unfamiliar wrapper; `--hook-launcher`
identifies its exact launcher token when the shell setup is complex.

The brief requires the child to run
`"$skill_dir/scripts/tmux-subagent-register.sh" PROVIDER` inside its own shell
before starting task work. It captures the provider's exported conversation ID.
Claude startup, Codex notify and local identity hooks provide additional capture.
Verify `identity.json` under the registry entry's `resume_state` before declaring
resume ready; if registration fails, report that limitation and resolve it.

`Ctrl-b r` with `bind-key r respawn-pane -k` restarts into the recorded
conversation in the same pane. It interrupts a running agent; preserve the
ownership rules. Missing identity or a process still holding the pane lock gives
a visible error, never a new session or a most-recent-session fallback. Leave
existing panes alone; they keep their original commands.

Launch under an interactive zsh, as the managed pane runner does. tmux's
`default-shell` may be something else entirely (`/bin/dash` on the author's
machine), so a pane without an explicit zsh sees neither the user's shell
functions nor environment. Use `-i` here specifically, against the general rule
that `zsh -c` is the right non-interactive form: this pane is a user-facing
shell hosting a full-screen TUI, so it wants job control and interactive signal
handling. Because an interactive zsh `cd`s during startup, `tmux new-session -c
DIR` alone does not put the child in the right tree. Confirm the working
directory from the pane.

Pass the permission flag explicitly in every launch command, then confirm it in
the pane; a child inherits no usable posture. Verified 2026-09-09 (Claude Code
2.1.266) on this machine: both Claude profiles default to `"defaultMode":
"plan"`, so a bare `claude-m` child cannot write until someone approves a plan,
while an interactive child started with `--permission-mode auto` in an
already-trusted directory shows `auto mode on` in its status line on either
profile; `claude -p ... --permission-mode auto` reported
`"permission_mode":"default"` in its Stop payload, so print mode does not run
auto mode. Read the pane's status line after launch (`auto mode on`, `accept
edits on`, `plan mode on`) and fall back to `--permission-mode acceptEdits` only
if it says otherwise. On the Codex side the local `codex-m` already passes
`--approve-for-me` (approvals auto-reviewed inside the workspace-write sandbox),
while a bare `codex` needs `--approve-for-me` or `-a on-failure -s
workspace-write` in the command. Inference, not verified: under workspace-write
a result path outside the child's workdir goes through the automatic reviewer,
so prefer a result path inside the workdir.

Bound an unattended child's retries. The local `claude` wrapper reads a zsh
dynamic variable, `claude_max_retries=30 claude-m ...`, setting
`CLAUDE_CODE_MAX_RETRIES` for that launch; its default is effectively infinite,
so a child sitting out an API outage looks alive forever and never trips the
waiter. Otherwise `CLAUDE_CODE_MAX_RETRIES=30 claude ...`, noting that a wrapper
setting the variable itself overrides the environment. A dead pane under
`remain-on-exit` is then the recovery signal: relaunch with `claude --resume` or
`codex resume`.

Answer the first prompts deliberately, and prefer a directory the profile
already trusts, such as the parent's. A first launch elsewhere triggers a trust
question: Codex asks "Do you trust the contents of this directory?" and `codex
exec` refuses an untrusted non-git directory outright ("Not inside a trusted
directory and --skip-git-repo-check was not specified", 2026-09-09), while an
interactive Claude child opens with "Quick safety check: Is this a project you
created or one you trust? ... No, exit / Yes, I trust this folder / Enter to
confirm" (verified 2026-09-09, Claude Code 2.1.266; the `-p` path never shows
it). Its default is "No, exit", so a bare Enter kills the child: capture the
pane, wait until "Enter to confirm" is rendered, then send `tmux send-keys -t
"$pane_id" Down` and `Enter` separately, since keys sent before the prompt
renders are lost or land on the default. Read every prompt before answering: a
wrapper whose instruction-file sync failed instead asks "Launch anyway, with
possibly stale instructions?", which also defaults to No. Answer only within the
existing authorization, then verify the task started; a created tmux session
proves nothing. Report blocked authentication or permission prompts accurately.

Inspect with `tmux capture-pane -p -t "$pane_id" -S -80`, watch with `tmux
attach-session -r -t "$session_id"`, interact with `tmux attach-session -t
"$session_id"`. Give the user those commands, judge readiness from the pane
rather than elapsed time, and never silently switch the user's client.

**Local launcher configuration (example).** Machine-specific: an example of what
a launch context records, not a portable interface. On the author's machines the
preferred launchers are the zsh wrappers `claude-m` (default Claude profile),
`claude-work` (`CLAUDE_CONFIG_DIR` pointed at the work configuration), and
`codex-m` (local sandbox and approval options; verified 2026-09-09 across four
launches to open with a directory-trust question before the prompt runs). They
are shell functions, not executables: `command -v` from a bash launcher or a
non-zsh child reports nothing, so detect them with `zsh -c 'whence -w claude-m
codex-m claude-work'`. Where a wrapper is absent, fall back to the bare `claude`
/ `codex` and supply what it would have added: `CLAUDE_CONFIG_DIR=<dir> claude
...` for a profile, plus the permission, approval and sandbox flags above.
Record the resolved launcher in the launch metadata and have the brief point at
it.

## Providers

Select the child's provider recipe; the sections above hold the policy, these
the syntax.

**Claude Code.** Launch with the resolved profile and a unique peer name:
`--name` sets it, `--model` selects a model, `--session-id` takes a UUID; check
installed help before depending on a flag. `CLAUDE_CONFIG_DIR` selects an
alternate configuration directory, and default-profile configuration can depend
on leaving it unset, so check that the tmux server did not hand the child
another profile. Resume by explicit session ID under the same profile, never by
"most recent session here" and never as a second writable copy of a running
conversation. `--print` and its JSON modes are non-interactive, so they give
none of the live TUI this workflow needs; native agent teams are a separate
feature that may not support nested teammates.

**Codex.** Launch interactive `codex` with the resolved profile, sandbox, and
approval settings, checking its help independently of Claude's syntax: it takes
an initial prompt and `--model`, its configuration profile and `CODEX_HOME` are
unrelated to Claude's, and `codex exec` is non-interactive. Resume with an
explicit conversation ID, not `--last`, when other agents create sessions
concurrently, and record that ID rather than inventing a Claude-style launch
flag. A parent sandbox may deny access to the tmux socket: use the host's
authorized approval mechanism and report real failures. If help exposes `codex
queue --thread ID --message TEXT`, evaluate it as a follow-up transport
(Ownership) before automating it; help availability is not delivery.

**Google Antigravity (agy).** Launch Google's `agy` executable, or the local
launcher for it, using its own account configuration; do not substitute the
separate `gemini` CLI, invent an `agy --profile` flag, or assume Claude/Codex
profile variables apply.

*Model policy.* Resolve Gemini Flash Latest through `agy models` in the selected
profile at launch, unless the user explicitly requested Pro for that child or
its subtree. A Pro parent does not make its children Pro, and difficulty, quota
failures, or an unavailable Flash model never justify an upgrade. Choose the
newest version inside the requested family and pass its exact slug to `--model`;
literal `gemini-flash-latest` aliases are not assumed to work, and Flash-Lite,
another family, or a non-Gemini model is a different choice. Honor a requested
effort and verify supported values against `agy --help`. If family or effort
cannot be resolved, report that instead of substituting. Record policy and exact
slug in metadata, keep the sanitized model in the session name, and keep today's
version out of defaults.

*Interactive launch and resume.* Start the initial turn inside the owned session
with `agy --model "$resolved_model" --prompt-interactive "$initial_prompt"`,
where a sensitive prompt points at the private brief instead of containing it.
`--prompt-interactive` keeps the session interactive; `--print` and `--prompt`
are headless. Resume with `agy --conversation "$conversation_id"` under its
owning profile, never `--continue`, which can select another agent's most recent
conversation. With no verified message-queue interface, follow-ups go through
the ownership rules.

**Skill loading.** Put this skill in the provider's discovery location and its
absolute path in every child brief, so a child can still read it when discovery
fails. Claude Code and Codex read `~/.agents/skills` (symlinked skill
directories work; optional `agents/openai.yaml` metadata is Codex's and must not
be required by the shared file). AGY CLI reads
`~/.gemini/antigravity-cli/skills/`: expose this file there as
`tmux-subagents.md` and verify `/tmux-subagents` in the installed CLI. That CLI
path differs from the Antigravity app's, so an installer target for the app does
not configure agy. Keep frontmatter portable: Claude-specific substitutions,
`context: fork`, and tool-permission fields must not redefine the workflow.

## Results

Each assignment ends by atomically publishing its result file: process exit,
turn-end hooks, idle notices, prompts, and terminal captures establish no
completion. Track process state and task outcome as independent facts, since a
live CLI may have finished and an exited CLI may have failed silently.

The result carries `task_id`, `node_id`, `outcome` (completed, blocked or
failed), summary, artifacts, and verification. The child writes a complete
temporary file beside it and renames it into place before ending the turn. Every
assignment, follow-ups included, gets a new task ID *and* a new result path,
because the waiter tests existence only and an old file would satisfy a new
assignment. The needs-input file is exactly the result path with `.md` replaced
by `.needs-input.md`, published the same atomic way.

The parent validates the IDs inside the file before believing it, then reads the
artifact. A missing result is unknown: silence, a prompt, or a timeout proves
nothing. Report a missing or blocked result and investigate rather than
restarting an agent that may still be working.

## Ownership and follow-ups

**Suggested prompts are not pending messages.** Plain `capture-pane -p` loses
this distinction. For Claude Code, use `tmux capture-pane -p -e -t "$pane_id"`
and `tmux display-message -p -t "$pane_id" '#{cursor_x},#{cursor_y}'`: dim/gray
prompt text with the cursor before it is evidence of a generated suggestion
(observed: ANSI SGR 2, cursor immediately after `❯ `), not typed input or author
approval. [Claude documents](https://code.claude.com/docs/en/interactive-mode#prompt-suggestions)
Tab/Right to accept a suggestion and typing to dismiss it. Styling/cursor checks
are harness-specific heuristics, not a portable input-buffer API; if ambiguous,
report unknown and send no keys. Never press Enter/Tab to test the distinction
or execute a suggestion as an instruction. For new automated Claude sessions,
session-local `CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=false` avoids this ambiguity;
do not change the user's global settings.

Confirm ownership and input readiness before dispatching a follow-up with a
fresh task ID and result path. Ownership is an explicit registry field, changed
only on explicit hand-back; detachment or elapsed time grants nothing back.
While the user owns a child, the parent queues follow-ups and does not inject
input, interrupt it, resume another copy of its conversation, or close it. The
convention needs cooperation: nothing stops typing into a raw tmux pane.

Prefer verified provider message delivery over keystrokes. Where only the
terminal is available, send literal text with `tmux send-keys -t "$pane_id" -l
-- "$text"` and Enter separately, after confirming readiness from the pane;
`send-keys -l` reaches a busy Claude child, whose TUI queues typed text
(verified 2026-09-09). Never paste into an unknown permission modal or while the
user is typing. Automated check-then-send races: ownership check and delivery
happen under the registry lock, which is also held before closing anything
selected from an older list.

## Notifications

Choose the child's push channel at launch and re-arm it after every assignment;
a tmux pane cannot wake its parent. Verified 2026-09-09 (Claude Code 2.1.265,
Codex CLI, macOS) with two throwaway Haiku sessions launched by the launch
helper into a scratch directory, briefed by file to log every
`ListAgents`/`SendMessage` result and every incoming message verbatim.

- **Claude child, same profile** (same `CLAUDE_CONFIG_DIR`): launch with `--name
  <role>`; parent and child then see each other in `ListAgents` with their tmux
  `session:window.pane`. Put the parent's peer name in the brief and require a
  `SendMessage` on completion, block, or question: first line `COMPLETED`,
  `BLOCKED`, or `NEEDS-INPUT`, then a two-line summary and the result path. It
  arrives as `<cross-session-message from="uds:..." from-name="<child>" ...>`
  and wakes an idle parent as a new turn. After launch and after every follow-up
  the parent calls `SendMessage(to: <child>, notify_when_idle: true)`; one
  `[Cross-session idle notice]` arrives at the child's next turn end even if it
  forgot to report, and idle is not completion. Measured work -> work
  (`claude-work --name msgP` and `--name msgC`): visibility both ways, the
  child's message woke the idle parent, and `[Cross-session idle notice] "msgC"
  ... is idle now` arrived at its turn end.
- **Claude child, other profile**: sessions under different `CLAUDE_CONFIG_DIR`
  values do not list each other and `SendMessage` fails in both directions,
  although the sockets share one directory. Measured default -> work (`claude
  --name msgD`, same cwd): `ListAgents` showed only default-profile peers and
  `SendMessage(to:"msgP")` returned `{"success":false,"message":"No agent named
  'msgP' is reachable..."}`; work -> default: `SendMessage(to:"msgD")` returned
  "No agent named 'msgD' is reachable. Did you mean: msgC?", and a separate
  coordinator saw the same for its own pair. No idle notice can be armed either
  way. Treat such a child as file-only, like Codex and agy.
- **Codex, agy, or cross-profile child**: the brief requires the result file and
  the parent runs `"$skill_dir/scripts/tmux-subagent-wait.sh" RESULT PANE_ID` in
  the background (Claude Code: Bash with `run_in_background`, which turns the
  process exit into a new turn; a bare shell `&` does not by itself notify a
  Codex or agy parent, and with no runtime bridge the fallback is an explicit
  check at the parent's next turn). One notification per assignment.
- **Needs input**: a child that must ask publishes the needs-input file with the
  question and its default if unanswered; the waiter fires on it. The parent
  answers by `SendMessage` or, under the ownership rules, through the terminal,
  deletes the file, and re-arms the waiter.

**Turn-end hooks.** Wire them per launch, on the command line, so no user config
file is touched: `--task TASK` makes the launch helper insert them, and only for
the children it starts. Claude gets `--settings` with a `Stop` hook running
`tmux-subagent-status.sh TASK NODE turn_end -`, merging with rather than
replacing the user's settings; Codex gets `-c
'notify=["<abs>/tmux-subagent-codex-notify.sh","TASK","NODE"]'`, whose adapter
also execs the user's original notify command with the same payload so an
existing bell keeps ringing (not automatic: pass its argv words as repeated
`--notify-chain` items). A turn end is not task completion.

Verified 2026-09-09: `codex exec` fired `notify` at turn end
(`"client":"codex_exec"`), `status.jsonl` got the `turn_end` line with the
`thread-id`, `turn-id`, and `last-assistant-message` payload, and the chained
command received the identical payload; `claude -p --model
claude-haiku-4-5-20251001` fired the `Stop` hook and `status.jsonl` got its
payload (`session_id`, `transcript_path`, `cwd`, ...). Interactive `Stop` was
not separately exercised; it is the same hook. A `Notification` hook with
matcher `permission_prompt` or `idle_prompt` can record `needs_input` the same
way (documented, not exercised); a hook only appends a status line and never
creates the file the waiter watches. Not verified: `Notification` hooks, agy
hooks, `codex queue`, and behaviour when the parent is itself busy for a long
time (the message queues, as observed for typed input, but ordering under load
was not tested). A parent with many children can `tail -f status.jsonl` filtered
by task ID (Claude Code: Monitor) instead of one waiter each, provided that
stream actually wakes it.

## Coordinator handoff

Before a coordinator stops, give its successor the shared registry path and, for
every active assignment, the child's context, result path, ownership, and
notification state: a run longer than the parent's quota window ends with a
different session coordinating it. The full protocol is the `long-run-handoff`
skill, which this skill does not install; without it, write that list to a
handoff file in the state directory and name the successor in it. Three rules
bind the plumbing here:

- **The result file is the protocol.** Every child writes one at its assigned
  path, always, whatever else it does.
- **`SendMessage` is a courtesy.** A child that only messages its parent has
  reported to nobody once that parent is compacted, out of quota, or replaced.
- **Cross-profile children are file-only.** A successor on another profile
  inherits them as result files plus `tmux send-keys -l`, so the old parent
  relays its own children's reports into the shared results directory first.

## Cleanup

Leave finished sessions open until the user authorizes closure. Then close the
child by node ID, following the procedure below; it is the same whether a
command runs it or the parent performs each step by hand.

**Establish the child's state by deriving it, never by reading the registry.**
`process_state` and `task_outcome` are written once at launch and never updated
(Identity), so a finished child still reads `running`. A child is finished when
its result file exists *and* its front matter names this task and this node; a
result naming anything else is another assignment's file and authorizes
nothing. A child with no result is closable only when its session is alive, its
pane is not dead, the live listing does not report it busy, and it has been
silent — no new `status.jsonl` line, no new transcript message — long enough
that it cannot be mid-turn. A child waiting at its needs-input file is not
finished; answer it or hand it over instead.

**Then close it under the registry lock, in this order:**

- Re-derive that state inside the lock. Any list is stale the moment it is
  printed, and the child may have started a turn since it was read. Ownership
  is checked here too: while the user owns a child, the parent does not close
  it.
- Refuse a busy child, and refuse a parent while live descendants still run,
  unless the user chose a subtree cleanup — in which case close the descendants
  first, deepest first, each through this same procedure. Close selected nodes
  only, never an unselected descendant.
- Collect the session's pane PIDs *and every process below each of them* before
  killing anything; afterwards there is no tree left to walk and nothing to
  verify against. Send TERM, allow a few seconds, escalate to KILL, then
  `tmux kill-session`.
- Verify by PID, not by session name: right after a `tmux kill-session` on
  2026-09-09 one child `claude` process was still listed and exited a second
  later, and killing a pane does not prove its subprocesses died. A failed
  verification leaves the entry in place with a useful error, so a half-closed
  agent stays visible instead of becoming a ghost.
- Only then remove the registry entry, and append one `closed` event through
  `tmux-subagent-status.sh` so that log keeps a single writer and one format.

Skip a child whose pane is already dead. `remain-on-exit` keeps that pane on
purpose so its last screen can still be read, and removing dead panes is a
separate, whole-server operation on the author's machine (`tmuxzombie-kill`);
reconcile the registry entry after it. An entry whose session is simply gone is
reconciled with none of the above: there is nothing left to kill.

Never touch a task directory. Closing a terminal deletes neither conversation
history nor result artifacts.

**Local cleanup commands (example).** Machine-specific, in the same register as
the launcher wrappers above: on the author's machine this procedure is
`agent-subagents-close <node-id>...` and the multi-select picker
`agent-clean-fz`, zsh functions in a personal scripts checkout rather than
anything this skill installs. They derive every state on read, order the picker
by what is safest to close, hide busy children unless asked, and take
`agent_subagents_close_force` and `agent_subagents_close_subtree` for the two
refusals above; `docs/design.md` records the preview fields. Where they are
absent — which is every other machine — the parent performs the steps by hand.

## Scripts

Run these by absolute path from `$skill_dir/scripts`; they need tmux and Python
3, and launch also needs zsh. They share one state directory,
`TMUX_SUBAGENTS_STATE` or else
`${XDG_STATE_HOME:-$HOME/.local/state}/tmux-subagents`; pass the same resolved
directory to parent, child, and hooks.

- `tmux-subagent-name.sh PROJECT TASK PROVIDER-MODEL` generates a readable,
  collision-resistant name; run it again after a collision.
- `tmux-subagent-register.sh PROVIDER` records the child conversation from
  its own environment; run inside the child before task work.
- `tmux-subagent-launch.sh --resume-command SHELL_CODE [--task TASK]
  [--notify-chain ITEM]... [--provider PROVIDER] [--plugin FILE]
  [--hook-launcher TOKEN] [--run RUN] [--lineage LINEAGE] NAME WORKDIR COMMAND`
  creates, hooks, registers and prepares resume for one detached session; use
  it for every spawn. Prints `NAME SESSION_ID PANE_ID`. Exit 2 is a name collision (allocate
  another ID and retry), 3 means the session runs but is unregistered.
- `tmux-subagent-wait.sh RESULT_FILE [PANE_ID] [POLL_SECONDS]` is the background
  waiter: RESULT and NEEDS-INPUT exit 0, DEAD and GONE exit 1, default interval
  15 s, all four outcomes verified 2026-09-09. It polls, so it moves polling out
  of the parent's turn rather than removing it, and tests existence only:
  validate the IDs in the file after waking.
- `tmux-subagent-status.sh TASK_ID NODE_ID STATE [SUMMARY|-]` appends one status
  event, from a hook or directly for progress notes; `-` reads stdin, and both
  forms are truncated to 2000 characters.
- `tmux-subagent-codex-notify.sh TASK_ID NODE_ID [CHAIN_CMD ARGS...] PAYLOAD`
  logs a Codex turn end and chains the user's own notify command.

Status events publish no results and update no registry lifecycle state.
Follow-up dispatch and ownership are manual. Closure follows Cleanup, by hand
wherever the local commands named there are absent.

## References

The repository README covers installation, `docs/design.md` records pending
automation, `docs/related-projects.md` evaluated integrations; optional
maintainer background, not needed to use the installed skill.
