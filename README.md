# tmux-subagents

A shared Claude Code, Codex, and Google Antigravity (`agy`) skill for interactive subagents in tmux.
Children stay inspectable, can launch grandchildren, and inherit their parent's
provider and profile unless explicitly overridden.

**Status:** an instruction skill plus helpers in `skills/tmux-subagents/scripts/`:

- `tmux-subagent-launch.sh` creates a session, wires turn-end hooks, registers
  it, and prepares exact-conversation resume;
- `tmux-subagent-watch.sh` watches every child the registry lists under a
  parent and exits on the first batch of events (dead pane, menu on screen,
  result, needs-input, events-log line) without replaying earlier ones;
- `tmux-subagent-wait.sh` waits on one child's result, needs-input file, or
  pane death;
- `tmux-subagent-send.sh` types one follow-up into a Claude child's input box
  and reports `SENT`, `NOT-SUBMITTED` or `REFUSED`;
- `tmux-subagent-status.sh` appends a status line for hooks, and
  `tmux-subagent-codex-notify.sh` adapts Codex `notify` to it.

Ownership-checked follow-up dispatch is still planned. Closure is a documented
procedure rather than a packaged command (see "Finished children").

## Install

Requires tmux, zsh, Python 3, the authenticated coding CLIs you want to use,
and the portable `agent-session` plugin from `NightMachinery/.shells`, which
uses no personal shell setup. Install its subdirectory using the
[plugin README](https://github.com/NightMachinery/.shells/tree/master/scripts/zshlang/plugins/agent-session),
then export `AGENT_SESSION_PLUGIN` as the absolute path to
`agent-session.plugin.zsh` (a `~/scripts` installation is detected by default).
Launches never download dependencies.

```sh
npx skills add NightMachinery/tmux-subagents --global \
  --agent claude-code codex --skill tmux-subagents
```

For another Claude profile, rerun with `CLAUDE_CONFIG_DIR` set to its config
directory and `--agent claude-code`, one profile per invocation.

For local development, symlink `skills/tmux-subagents` from this checkout into
`~/.agents/skills/tmux-subagents` and each Claude profile's `skills/` directory,
without overwriting an existing installation. For the agy CLI, symlink
`skills/tmux-subagents/SKILL.md` to
`~/.gemini/config/skills/tmux-subagents/SKILL.md`; see
[Google's guide](https://antigravity.google/docs/cli/plugins/).

## Use

Invoke `/tmux-subagents` in Claude Code or agy, or `$tmux-subagents` in Codex:

> Launch a child to review the parser. Use the same provider and profile,
> keep this worktree, and leave the child open when it finishes.

The skill guides the agent to launch a detached interactive session, give you
its attach command, track parentage, and collect an explicit task result. A
child receives this same skill and its parent context before delegating again.

agy children default to **Gemini Flash Latest**; request **Gemini Pro Latest**
explicitly to use Pro. Latest is resolved from `agy models` at launch and the
concrete model is recorded in metadata and the tmux name. A Pro parent does not
make its children Pro.

## Names and inspection

```text
ag--<project>--<task>--<provider-model>--<suffix>
ag--demo--review-parser--claude-opus--a73f20
```

Names show the project, readable task, and launch model; run and ancestry stay
in registry metadata. `tmux-subagent-name.sh PROJECT TASK PROVIDER-MODEL`
sanitizes the labels and adds a random six-character suffix. The launcher
refuses collisions; generate another name and retry. Internally, stable tmux
IDs identify sessions.

```sh
tmux list-sessions
tmux attach-session -r -t '<session-name>'   # observe
tmux attach-session -t '<session-name>'      # interact
```

Tell the parent when taking control and when handing it back. It must not send
instructions while you own the child.

## Restart the same conversation

Inside a launched session, `Ctrl-b r` restarts the agent into its exact recorded
conversation (your tmux prefix may differ). The required binding is:

```tmux
bind-key r respawn-pane -k
```

The launcher takes an explicit `--resume-command`: shell code that calls the
plugin with the recorded ID, original directory, launcher and resume settings.
For example, with `skill_dir` set to the installed skill directory:

```sh
name=$("$skill_dir/scripts/tmux-subagent-name.sh" demo review-parser claude-opus)
"$skill_dir/scripts/tmux-subagent-launch.sh" --task review-1 \
  --lineage root-review --run parser-review \
  --resume-command 'agent-session-resume-exact claude "$AGENT_SESSION_ID" "$AGENT_SESSION_CWD" claude --model opus' \
  "$name" "$PWD" 'claude --model opus "Read the assigned private brief"'
```

Include the same profile, model and permission settings in both commands, and
keep the initial prompt out of the resume command; hooks are reapplied
automatically. The child runs `tmux-subagent-register.sh claude` (or `codex` /
`agy`) as its first task action, and startup, notify, and local identity hooks
also capture identity. No identity means a visible error, never a fresh or
"most recent" conversation, and a process lock refuses overlapping resumes.
Pressing the shortcut interrupts active work. Existing panes keep their
original commands. In the local scripts integration, `/done` also preserves the
managed pane's resume settings.

## Children notify the parent

A tmux pane cannot wake its parent, so the skill sets up a push channel at
launch. Claude children on the **same profile** (same `CLAUDE_CONFIG_DIR`)
`SendMessage` the parent on COMPLETED / BLOCKED / NEEDS-INPUT, and the parent's
`notify_when_idle` yields one idle notice. Across profiles neither side can
reach the other, so those children, like Codex and agy, are file-only: they
write a result file and a timestamped `events.log`, and the parent runs the
one-shot `tmux-subagent-watch.sh` as a background task, re-running it after
each event. Turn-end hooks (Codex `-c notify=[...]`, Claude `--settings` Stop
hook) append to a shared `status.jsonl` without editing user config. Details
are in the skill's Notifications section.

## Finished children

Keep them open for follow-ups. The central registry lives at
`${XDG_STATE_HOME:-$HOME/.local/state}/tmux-subagents/agents.json`, outside repos.
Its `process_state` and `task_outcome` fields are written at launch and never
updated, so a child's state is derived on every read: from its tmux session,
its pane, its result file, the status log, and the agent's own live listing.
Closing verifies by PID before the entry is removed; conversation history and
result artifacts remain, and busy children and unselected descendants are
protected. On the author's machine that is `agent-clean-fz` (a preview and
multi-select picker) and `agent-subagents-close`; elsewhere it is the skill's
Cleanup procedure, done by hand.

## Privacy and design

Published examples use generic labels. Keep profile mappings, workspace paths,
briefs, transcripts, results, and runtime metadata in private local storage.
Before a non-work parent hands off to a work profile, minimize personal context
and confirm any possible private-personal-data access with the user unless that
scope was already explicitly authorized. This covers files, memory, and tools,
not just the prompt. Loading the skill grants no additional permissions and does
not switch branches.

- [Skill](skills/tmux-subagents/SKILL.md)
- [Design and remaining automation](docs/design.md)
- [Related projects and integration choices](docs/related-projects.md)
- [Skills CLI installation formats](https://github.com/vercel-labs/skills#source-formats)
