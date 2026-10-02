---
name: tmux-subagents
description: Launch and coordinate Claude Code, Codex, or Google Antigravity (agy) agents in tmux when delegated work should remain inspectable and interactively usable by the user, including recursive child agents.
---

# tmux subagents

When the shared `delegate` skill is installed, read it for worker mode/model
selection, account boundaries, briefs, ownership, and result review. This skill
provides the native tmux backend. Explicit user choices take precedence; model
routing does not change the selected account or provider. If `delegate` is
unavailable, say so and use this skill's standalone safeguards below. Keep its
required result-file, resume, notification, and cleanup mechanics either way.

## Shared workflow

Prepare a private brief, launch one detached interactive tmux session, verify
startup, arm notifications, and validate the child's result. Every child stays
attachable, holds one bounded assignment, and reports through its assigned
result file. In order: brief and task ID (Prepare), data access (Privacy), name
and registry entry (Identity), launch and inspect (Launch), arm the push channel
(Notifications), validate the result (Results), follow up or hand over
(Ownership), leave open until closure is authorized (Cleanup).

Needs tmux, zsh, Python 3, the authenticated CLI you launch, and the portable
`agent-session` zsh plugin: set `AGENT_SESSION_PLUGIN` to its absolute
`.plugin.zsh` entrypoint (the launcher also accepts `--plugin` and detects
`~/scripts/zshlang/plugins/agent-session`); the repository README covers
installation. A missing plugin is a setup error; never substitute a new
conversation for unavailable resume. Read the provider section for the child,
which may differ from the parent's. `$skill_dir` is the directory holding this
SKILL.md; its helpers are not on PATH, so call them by absolute path (Scripts).
This skill installs no cleanup command (Cleanup).

## Prepare a delegation

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

It holds `brief.md`, `checkpoint.md`, `events.log`, `result.md`,
`result.needs-input.md`, and the launch context; an existing directory needs the
same permissions. The brief is a file the child reads, since the helper's
environment variables brief nobody. It states:

- objective, verification expectations, deliverable;
- authorized scope, owned paths, and the assumptions the child may make unasked,
  so it never stalls on a question nobody will answer; blocking questions go to
  the needs-input file;
- resolved provider, profile, model, launcher, and the permission flag used;
- root limits; root, parent, node and task IDs; this skill's absolute path, so
  grandchildren use the same workflow;
- registry, result, needs-input, checkpoint and events-log paths, and who to
  notify;
- the child's three duties: a checkpoint note after each milestone, so a
  restart or compaction can resume; one timestamped line in `events.log` per
  event the parent should hear about (milestone reached, blocked, result
  written), such as `[2026-01-31 14:05:00 UTC] tests pass`, each of which wakes
  the parent through the watcher, so events and not a diary; and the result
  file (Results).

Keep the current branch and worktree unless authorized otherwise; a new CLI
session does not inherit the parent's conversation. Resolve overlapping writes
before dispatch, and check delegated work before folding it into the parent's
output.

## Privacy and the work-profile handoff

Minimize the child's data access, and obtain any missing authorization before
exposing personal information to a work profile. A tmux session, a profile
switch, and a separate repository are organizational boundaries, not data
isolation, and this skill enforces none of them.

Before a non-work parent delegates to a work profile, review what the child
receives and what it can reach (workspace files, inherited instructions, memory
and history, attachments, connected tools) using the user's local profile
classification; a display name does not prove account scope, and a sanitized
prompt closes none of those routes. Prepare the smallest useful brief and access
scope. If private personal data could still be reached, confirm first: say what
could be exposed, why it may be needed, and whether a sanitized handoff or
staying on the non-work profile would do, without quoting sensitive contents.
Choosing a work profile is not consent. Authorization already given for this
scope is enough; ask again only when it expands. Until answered, keep the
handoff pending and continue only work that does not expose the information.
Carry these boundaries into descendant delegations.

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

Generate the name with `tmux-subagent-name.sh PROJECT TASK PROVIDER-MODEL` from
short non-sensitive labels describing the work; it normalizes punctuation and
whitespace to hyphens and adds a random six-character suffix. Keep the run and
full ancestry in metadata (`--run`, `--lineage`), not the name, and keep the
`ag--` prefix so local autonaming hooks leave the session alone.

Never address a child by session name after launch. Use the captured pane id
`%N`, the stable handle for inspection, input and the watcher, or the `$N` from
`tmux display -p -t "$pane" '#{session_id}'`. A recorded name can go stale (on
the author's machine a hook renames non-`ag--*` sessions after the agent's
title), and tmux reads a target by its first character (`%` pane, `$` session,
`@` window), so a session renamed to a title starting with `@` cannot be
addressed by name at all. Single-quote captured ids in shell code: in double
quotes `"$661"` expands `${6}` followed by `61`, and a kill silently targets the
wrong session.

The registry is one readable JSON file shared across projects and providers,
keyed by node ID, at
`${XDG_STATE_HOME:-$HOME/.local/state}/tmux-subagents/agents.json` unless
`TMUX_SUBAGENTS_STATE` overrides it; put its absolute path in the brief. Every
writer, including follow-up dispatch and cleanup, holds the stable
`agents.json.lock` sidecar across the whole read-update-replace cycle and
publishes through a unique temporary file in the same directory, as the launch
helper does; an append-only log could not support safe removal.

The launch helper writes one entry per launch: node, root and parent IDs,
lineage, run, task ID, provider, the resolved launcher token, working directory,
tmux socket, session and pane IDs, `requested_model` (parsed from `--model`), an
empty `observed_model`, `notify` (`hook` when a turn-end hook is wired at
launch, `file-only` when not, agy today; a separate question from the push
channel in Notifications), `created`, `process_state: running` and
`task_outcome: unknown`. The rest is manual: the local profile reference, the
observed model when known (the name keeps the launch model), an external parent
recorded without inventing a tmux pane. Two consequences: `process_state` is
never updated, so take liveness from the pane or the status log, never that
field; and the key is the session name, so identical names on two tmux sockets
would overwrite one record.

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
and registers the session. It also sets the session option `@agent_role` to
`sub`, which local tooling such as notification hooks can read to tell a child
from a main session.

Supply `resume_command` as shell code calling the shared plugin, for example:

    agent-session-resume-exact codex "$AGENT_SESSION_ID" "$AGENT_SESSION_CWD" codex-m --model MODEL

Keep these variables literal until resume. Use the same launcher, profile,
model and permission settings as the initial command, without its initial
prompt; the helper persists and reapplies notification flags. Pass `--provider
claude|codex|agy` for an unfamiliar wrapper, and `--hook-launcher` to name its
exact launcher token when the shell setup is complex.

The brief requires the child to run
`"$skill_dir/scripts/tmux-subagent-register.sh" PROVIDER` in its own shell
before task work; it captures the provider's exported conversation ID, as do
Claude startup, Codex notify and local identity hooks. Verify `identity.json`
under the entry's `resume_state` before declaring resume ready; if registration
fails, report that limitation and resolve it.

`Ctrl-b r` with `bind-key r respawn-pane -k` restarts into the recorded
conversation in the same pane. It interrupts a running agent, so the ownership
rules apply. Missing identity or a process still holding the pane lock gives a
visible error, never a new session or a most-recent-session fallback. Existing
panes keep their original commands.

Launch under an explicit `zsh -c`, as the managed pane runner does, not `zsh
-ic`. tmux's `default-shell` may be something else entirely (`/bin/dash` on the
author's machine), which sees neither the user's shell functions nor
environment. A full-screen TUI needs no job control (`zsh -c 'less <file>'`
renders and takes keystrokes), and `zsh -c` inherits the caller's directory, so
`tmux new-session -c DIR` puts the child where you asked, whereas an
interactive zsh may `cd` away during startup. Confirm the working directory from
the pane regardless.

**Permissions.** Pass the permission flag explicitly in every launch command and
confirm it in the pane's status line; a child inherits no usable posture. For
Claude use `--permission-mode auto`: a profile can default to plan mode (the
author's do), where a child cannot write until someone approves a plan, while an
interactive child in an already-trusted directory shows `auto mode on`. Print
mode (`claude -p`) does not run auto mode. If the status line shows `accept
edits on` or `plan mode on` instead, fall back to `--permission-mode
acceptEdits`. For Codex, the local `codex-m` passes `--approve-for-me`
(approvals auto-reviewed inside the workspace-write sandbox); a bare `codex`
needs `--approve-for-me` or `-a on-failure -s workspace-write`. Inference, not
verified: under workspace-write a write outside the child's workdir, such as its
task directory, goes through the automatic reviewer. agy is under Providers.

**Retries.** Bound an unattended Claude child's retries with
`CLAUDE_CODE_MAX_RETRIES=30 claude ...` (the local wrapper takes the zsh dynamic
variable `claude_max_retries=30 claude-m ...` and sets it; a wrapper that sets
the variable itself overrides the environment). The default is effectively
infinite, so a child sitting out an API outage looks alive forever and never
trips the watcher. A dead pane under `remain-on-exit` is then the recovery
signal: relaunch with `claude --resume` or `codex resume`.

**First prompts.** Prefer a directory the profile already trusts, such as the
parent's; elsewhere each CLI first asks whether to trust it. Claude's question
("Quick safety check: Is this a project you created or one you trust?")
defaults to "No, exit", so a bare Enter kills the child: capture the pane, wait
until "Enter to confirm" is rendered, then send `Down` and `Enter` as separate
`send-keys`, since keys sent before the prompt renders are lost or land on the
default. Codex ("Do you trust the contents of this directory?") and agy ("Do you
trust the contents of this project?") both highlight Yes, so a bare Enter
accepts; `codex exec` refuses an untrusted non-git directory outright.
`--dangerously-skip-permissions` does not suppress these prompts; it only
removes per-action tool prompts. Read every prompt before answering: a wrapper
whose instruction-file sync failed asks "Launch anyway, with possibly stale
instructions?", which also defaults to No. Answer only within the existing
authorization, then verify the task started; a created tmux session proves
nothing. Report blocked authentication or permission prompts accurately.

Inspect with `tmux capture-pane -p -t "$pane_id" -S -80`, watch with `tmux
attach-session -r -t "$session_id"`, interact with `tmux attach-session -t
"$session_id"`. Give the user those commands, judge readiness from the pane
rather than elapsed time, and never silently switch the user's client.

**Local configuration (example).** Machine-specific, not a portable interface.
On the author's machines the launchers are zsh functions: `claude-m` (default
Claude profile), `claude-work` (`CLAUDE_CONFIG_DIR` pointed at the work
configuration) and `codex-m` (local sandbox and approval options). A non-zsh
shell's `command -v` does not see them; detect them with `zsh -c 'whence -w
claude-m codex-m claude-work'`. Where a wrapper is absent, use the bare `claude`
or `codex` and supply what it would have added: `CLAUDE_CONFIG_DIR=<dir>` for a
profile, plus the permission, approval and sandbox flags above. Record the
resolved launcher in the launch metadata and have the brief point at it. Add
`--prompt-suggestions false` to every Claude launch, wrapper or bare (Ownership).
`subagents-of-fz [-r] [AGENT]` picks an agent that has launched children, from
the registry's `parent` and `lineage`, then one of its children to go to,
read-only with `ctrl-r`; elsewhere read the registry directly.

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
profile variables apply. agy has no auto-approve mode (`--mode accept-edits`
still confirms destructive actions); its only unattended posture is
`--dangerously-skip-permissions`, which the user authorized for unattended agy
children on 2026-09-18. Pass it explicitly in every unattended launch and
confirm it in the pane.

*Model policy.* Resolve Gemini Flash Latest through `agy models` in the selected
profile at launch, unless the user explicitly requested Pro for that child or
its subtree. A Pro parent does not make its children Pro, and difficulty, quota
failures, or an unavailable Flash model never justify an upgrade. `agy models`
prints exact slugs, not aliases (for example `gemini-3.8-flash-low`,
`gemini-3.1-pro-high`); re-run it at launch and pass the newest slug in the
requested family to `--model`. Literal `gemini-flash-latest` aliases are not
assumed to work, and Flash-Lite, another family, or a non-Gemini model is a
different choice. Honor a requested effort, checking `agy --help`: a separate
`--effort low|medium|high` flag exists alongside the effort baked into some
slugs, so check which the selected model expects. If family or effort cannot be
resolved, report that instead of substituting. Record policy and exact slug in
metadata, keep the sanitized model in the session name, and keep today's
version out of defaults.

*Interactive launch and resume.* Start the initial turn inside the owned
session with, for example:

    zsh -c 'agy --model gemini-3.8-flash-low --dangerously-skip-permissions --prompt-interactive "Read /abs/path/brief.md and carry it out"'

substituting the resolved slug and pointing at the private brief rather than
putting sensitive text on the command line. `--prompt-interactive` keeps the
session interactive; `--print` and `--prompt` are headless. Resume under the
same profile with:

    agent-session-resume-exact agy "$AGENT_SESSION_ID" "$AGENT_SESSION_CWD" agy --model "$resolved_model" --dangerously-skip-permissions

never `--continue`, which can select another agent's most recent conversation.
agy has no equivalent of Claude's `ListAgents`/`SendMessage`, so an agy child is
file-only for notifications (Notifications), and with no verified message
queue, follow-ups go through the ownership rules.

**Skill loading.** Put this skill in the provider's discovery location and its
absolute path in every child brief, so a child can still read it when discovery
fails. Claude Code and Codex read `~/.agents/skills` (symlinked skill
directories work; optional `agents/openai.yaml` metadata is Codex's and must not
be required by the shared file). The agy CLI reads
`~/.gemini/config/skills/<name>/SKILL.md`, and a symlinked `SKILL.md` works
there too; `~/.gemini/antigravity-cli/` is runtime state, not a skills
directory, and an installer target for the separate Antigravity app does not
configure the CLI. Keep frontmatter portable: Claude-specific substitutions,
`context: fork`, and tool-permission fields must not redefine the workflow.

## Results

Each assignment ends by atomically publishing its result file: process exit,
turn-end hooks, idle notices, prompts, and terminal captures establish no
completion. Track process state and task outcome as independent facts, since a
live CLI may have finished and an exited CLI may have failed silently.

The result carries `task_id`, `node_id`, `outcome` (completed, blocked or
failed), summary, artifacts, and verification. The child writes a complete
temporary file beside it, under a name not ending in `.md`, and renames it into
place before ending the turn. The needs-input file is exactly the result path
with `.md` replaced by `.needs-input.md`, published the same way. Every
assignment, follow-ups included, gets a new task ID *and* a new result path,
since an old file would satisfy a new assignment; keep a follow-up's result in
the child's original task directory as `result.<follow-up task id>.md`, where
the watcher looks.

The parent validates the IDs inside the file before believing it, then reads the
artifact. A missing result is unknown: silence, a prompt, or a timeout proves
nothing. Report a missing or blocked result and investigate rather than
restarting an agent that may still be working.

## Ownership and follow-ups

Confirm ownership before dispatching a follow-up with a fresh task ID and result
path. Ownership is an explicit registry field, changed only on explicit
hand-back; detachment or elapsed time grants nothing back. While the user owns
a child, the parent queues follow-ups and does not inject input, interrupt it,
resume another copy of its conversation, or close it. The convention needs
cooperation: nothing stops typing into a raw tmux pane.

Prefer verified provider delivery (`SendMessage`, same Claude profile only).
Otherwise send follow-ups with `scripts/tmux-subagent-send.sh` (Scripts). Its
one-line status is the delivery check: do not also read the pane for every
message, and let the periodic supervision ping catch strays. It reaches a busy
Claude child, whose TUI queues typed text, and refuses a permission or trust
menu or text someone is already typing. It recognizes Claude Code's `❯` input
box; for another TUI it refuses rather than guess, so extend it instead of
typing by hand. The ownership check and the send happen under the registry
lock, which is also held before closing anything selected from an older list.

**Suggested prompts are not pending messages.** A Claude Code pane can show dim
generated text after `❯` that nobody typed. Never treat it as a user message
or approval, and never press Enter or Tab on an idle prompt, which could submit
or accept it. `--prompt-suggestions false` does not silence the interactive TUI
(Claude Code 2.1.273); pass it anyway, and never change the user's global
settings to suppress suggestions.

## Notifications

Choose the child's push channel at launch and re-arm it after every assignment;
a tmux pane cannot wake its parent.

- **Claude child, same profile** (same `CLAUDE_CONFIG_DIR`): launch with `--name
  <role>`; parent and child then see each other in `ListAgents` with their tmux
  `session:window.pane`. Put the parent's peer name in the brief and require a
  `SendMessage` on completion, block, or question: first line `COMPLETED`,
  `BLOCKED`, or `NEEDS-INPUT`, then a two-line summary and the result path. It
  arrives as a `<cross-session-message ...>` and wakes an idle parent as a new
  turn. After launch and after every follow-up the parent calls
  `SendMessage(to: <child>, notify_when_idle: true)`; one idle notice arrives at
  the child's next turn end even if it forgot to report, and idle is not
  completion.
- **Claude child, other profile**: sessions under different `CLAUDE_CONFIG_DIR`
  values neither list nor reach each other ("No agent named ... is reachable",
  both directions), and no idle notice can be armed, so the child is file-only.
- **File-only children** (Codex, agy, other-profile Claude): the brief requires
  the result file and the events log, and the parent runs the watcher below,
  or `tmux-subagent-wait.sh RESULT PANE_ID` for a single result, as a background
  task that wakes it on exit (Claude Code: Bash with `run_in_background`; a bare
  shell `&` does not notify a Codex or agy parent, whose fallback is an explicit
  check at its next turn).
- **Needs input**: a child that must ask publishes the needs-input file with the
  question and its default if unanswered. The parent answers by `SendMessage`
  or, under the ownership rules, with the send helper, deletes the file, and
  re-runs the watcher.

**Turn-end hooks.** Wire them per launch, on the command line, so no user config
file is touched: `--task TASK` makes the launch helper insert them, and only for
the children it starts. Claude gets `--settings` with a `Stop` hook running
`tmux-subagent-status.sh TASK NODE turn_end -`, merging with rather than
replacing the user's settings; Codex gets `-c
'notify=["<abs>/tmux-subagent-codex-notify.sh","TASK","NODE"]'`, whose adapter
also execs the user's original notify command with the same payload so an
existing bell keeps ringing (pass its argv words as repeated `--notify-chain`
items). Both land in `status.jsonl` with the provider's payload. A turn end is
not task completion. Not verified: `Notification` hooks (matcher
`permission_prompt` or `idle_prompt` could record `needs_input` the same way; a
hook only appends a status line and never creates a result file), agy hooks,
`codex queue`, and message ordering while the parent stays busy.

**Supervising with the watcher.** One zero-token watcher covers every child of
a parent, however many there are and whenever they were launched:

    "$skill_dir/scripts/tmux-subagent-watch.sh" --parent "$my_node_id"

It re-reads the registry every cycle (default 15 s) and prints one line per
event, `EVENT <node> <kind> <detail>`: `pane-dead`, `pane-gone`, `menu` (a real
permission, trust or choice menu on screen, not text that merely quotes one),
`result`, `needs-input`, and `log` for each new `events.log` line, held 60 s so
a burst arrives together. `--turn-end` adds turn ends from `status.jsonl`; they
are off by default because they are noisy and not completion. Checkpoints are
not events. It exits after the first batch and remembers what it reported under
the state directory, so the loop is:

1. Run it as a tracked background task; its exit is the notification.
2. On exit, read the source before replying: the `events.log` line, the result
   file (validating its IDs), or the pane. Never act on the summary alone.
3. Act: answer a menu within the user's authorization (it stalls a child
   without a turn end), reply to a question, fold in a result.
4. Run the same command again. It never replays what it already reported, and
   baselines a child's existing files at first sight unless that child was
   registered after the watcher's record began.

It refuses to start when stdout is `/dev/null` (a `nohup` or detached copy
could never notify anyone), reports `NO-CHILDREN` and exits when the selection
is empty, and allows one watcher per selection. `--root ID` and `--node ID`
select differently; `--timeout S` bounds a run for a periodic recovery ping. It
reads `tasks/<task_id>/` under the state directory, or an entry's optional
`task_dir` field, set by hand.

## Coordinator handoff

Before a coordinator stops, give its successor the shared registry path and, for
every active assignment, the child's context, result path, ownership, and
notification state: a run longer than the parent's quota window ends with a
different session coordinating it. The full protocol is the `long-run-handoff`
skill, which this skill does not install; without it, write that list to a
handoff file in the state directory and name the successor in it. The plumbing
here adds:

- **The result file is the protocol.** Every child writes one at its assigned
  path, always, whatever else it does.
- **`SendMessage` is a courtesy.** A child that only messages its parent has
  reported to nobody once that parent is compacted, out of quota, or replaced.
- **Cross-profile children are file-only.** A successor on another profile
  inherits them as result files plus the send helper, so the old parent
  relays its own children's reports into the shared results directory first.
- **An in-process child can move profiles.** Local example: the author's
  scripts provide `claude-code-subagent-resume <agent-id> <profile>`, which
  copies an Agent-tool child's transcript into a new top-level session and
  resumes it; run it in a fresh tmux session and use the send helper. Only for
  a finished or stopped child whose parent will not `SendMessage` it again, so
  two copies never act. The copy gets the main-session system prompt and tools,
  and the launcher's default model unless given `--model`.

## Cleanup

Leave finished sessions open until the user authorizes closure. Then close the
child by node ID, following the procedure below; it is the same whether a
command runs it or the parent performs each step by hand.

**Establish the child's state by deriving it, never by reading the registry.**
`process_state` and `task_outcome` are written once at launch and never updated
(Identity). A child is finished when its result file exists *and* its front
matter names this task and this node; a result naming anything else is another
assignment's file and authorizes nothing. A child with no result is closable
only when its session is alive, its pane is not dead, the live listing does not
report it busy, and it has been silent (no new `status.jsonl` line, no new
transcript message) long enough that it cannot be mid-turn. A child waiting at
its needs-input file is not finished; answer it or hand it over instead.

**Then close it under the registry lock, in this order:**

- Re-derive that state inside the lock. Any list is stale the moment it is
  printed, and the child may have started a turn since it was read. Ownership
  is checked here too: while the user owns a child, the parent does not close
  it.
- Refuse a busy child, and refuse a parent while live descendants still run,
  unless the user chose a subtree cleanup; then close the descendants first,
  deepest first, each through this same procedure. Close selected nodes only,
  never an unselected descendant.
- Collect the session's pane PIDs *and every process below each of them* before
  killing anything; afterwards there is no tree left to walk and nothing to
  verify against. Send TERM, allow a few seconds, escalate to KILL, then
  `tmux kill-session`.
- Verify by PID, not by session name: a child process can outlive `tmux
  kill-session` for a moment, and killing a pane does not prove its
  subprocesses died. A failed verification leaves the entry in place with a
  useful error, so a half-closed agent stays visible instead of becoming a
  ghost.
- Only then remove the registry entry, and append one `closed` event through
  `tmux-subagent-status.sh` so that log keeps a single writer and one format.

Skip a child whose pane is already dead: `remain-on-exit` keeps that pane on
purpose so its last screen can still be read, and removing dead panes is a
separate, whole-server operation (`tmuxzombie-kill` on the author's machine);
reconcile the registry entry after it. An entry whose session is simply gone is
reconciled with none of the above: there is nothing left to kill.

Never touch a task directory. Closing a terminal deletes neither conversation
history nor result artifacts.

**Local cleanup commands (example).** On the author's machine this procedure is
`agent-subagents-close <node-id>...` and the multi-select picker
`agent-clean-fz`, zsh functions in a personal scripts checkout rather than
anything this skill installs. They derive every state on read, order the picker
by what is safest to close, hide busy children unless asked, and take
`agent_subagents_close_force` and `agent_subagents_close_subtree` for the two
refusals above; `docs/design.md` records the preview fields. Elsewhere the
parent performs the steps by hand.

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
  it for every spawn. Prints `NAME SESSION_ID PANE_ID`. Exit 2 is a name
  collision (allocate another ID and retry), 3 means the session runs but is
  unregistered.
- `tmux-subagent-watch.sh [--parent ID] [--root ID] [--node ID] [--interval S]
  [--debounce S] [--timeout S] [--turn-end] [--follow]` is the registry-driven
  watcher (Notifications). Exit 0 after printing events, 1 for `NO-CHILDREN` or
  a timeout, 2 for a usage error or a stdout of `/dev/null`, 3 when another
  watcher holds the same selection. The default selection is the caller's own
  children, from `TMUX_SUBAGENT_NODE`.
- `tmux-subagent-wait.sh RESULT_FILE [PANE_ID] [POLL_SECONDS]` waits on one
  result: RESULT and NEEDS-INPUT exit 0, DEAD and GONE exit 1, default interval
  15 s. It tests existence only: validate the IDs in the file after waking.
- `tmux-subagent-status.sh TASK_ID NODE_ID STATE [SUMMARY|-]` appends one status
  event, from a hook or directly; `-` reads stdin, and both forms are truncated
  to 2000 characters.
- `tmux-subagent-send.sh PANE_ID (--file PATH | -- TEXT)` sends one follow-up
  to a Claude child and prints one line: `SENT` (exit 0), `NOT-SUBMITTED` (1)
  or `REFUSED` (2: a menu, pre-typed text, an unknown TUI or a dead pane). Its
  comments hold the submit mechanics.
- `tmux-subagent-codex-notify.sh TASK_ID NODE_ID [CHAIN_CMD ARGS...] PAYLOAD`
  logs a Codex turn end and chains the user's own notify command.

Status events publish no results and update no registry lifecycle state.
Ownership checks are manual.

## References

The repository README covers installation, `docs/design.md` records pending
automation, `docs/related-projects.md` evaluated integrations; optional
maintainer background, not needed to use the installed skill.
