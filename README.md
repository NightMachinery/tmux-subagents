# tmux-subagents

A shared Claude Code, Codex, and Google Antigravity (`agy`) skill for interactive subagents in tmux.
Children stay inspectable, can launch grandchildren, and inherit their parent's
provider and profile unless explicitly overridden.

**Status:** instruction skill plus shell/Python helpers in
`skills/tmux-subagents/scripts/`: `tmux-subagent-launch.sh` creates a session,
wires hooks, registers it, and prepares exact-conversation resume; `tmux-subagent-wait.sh`
blocks until a child's result, needs-input file, or pane death;
`tmux-subagent-status.sh` appends a status line for hooks; and
`tmux-subagent-codex-notify.sh` adapts Codex `notify` to it. Follow-up dispatch
is still planned. Closure is a documented procedure rather than a packaged
command: the picker `agent-clean-fz` and `agent-subagents-close` exist as local
zsh functions on the author's machine, deriving every state on read, and
elsewhere the parent performs the steps in the skill's Cleanup section by
hand.

## Install

Requires tmux, zsh, Python 3, the authenticated coding CLIs you want to use,
and the portable `agent-session` plugin from `NightMachinery/.shells`.
The plugin uses no personal shell setup. Install its subdirectory using the
[plugin README](https://github.com/NightMachinery/.shells/tree/master/scripts/zshlang/plugins/agent-session),
then export `AGENT_SESSION_PLUGIN` as the absolute path to
`agent-session.plugin.zsh`. The local `~/scripts` installation is detected by
default. Dependencies are installed separately; launches never download them.

```sh
npx skills add NightMachinery/tmux-subagents --global \
  --agent claude-code codex --skill tmux-subagents
```

For another Claude profile, rerun with `CLAUDE_CONFIG_DIR` set to its config
directory and `--agent claude-code`. One profile per invocation.

For local development, symlink `skills/tmux-subagents` from this checkout into
`~/.agents/skills/tmux-subagents` and each Claude profile's `skills/` directory.
Do not overwrite an existing installation accidentally.

For AGY CLI, expose this checkout's `skills/tmux-subagents/SKILL.md` as
`~/.gemini/antigravity-cli/skills/tmux-subagents.md` and verify the slash command
appears. This is the CLI-specific path; see [Google's guide](https://antigravity.google/docs/cli/plugins/).

## Use

Invoke `/tmux-subagents` in Claude Code or AGY, or `$tmux-subagents` in Codex:

> Launch a child to review the parser. Use the same provider and profile,
> keep this worktree, and leave the child open when it finishes.

The skill guides the agent to launch a detached interactive session, provide
its attach command, track parentage, and collect an explicit task result.
A child receives this same skill and its parent context before delegating again.

AGY children default to **Gemini Flash Latest**. Request **Gemini Pro Latest**
explicitly to use Pro. Latest is resolved from `agy models` at launch, with the
concrete model recorded in metadata and the tmux name. A Pro parent does not
automatically make its children Pro.

## Names and inspection

```text
ag--<project>--<task>--<provider-model>--<suffix>
ag--demo--review-parser--claude-opus--a73f20
```

Names show the project, readable task, and launch model; run and ancestry stay
in registry metadata. `tmux-subagent-name.sh PROJECT TASK PROVIDER-MODEL`
sanitizes the labels and adds a random six-character suffix. Stable tmux IDs
identify sessions internally. The launcher refuses collisions; generate another
name and retry.

```sh
tmux list-sessions
tmux attach-session -r -t '<session-name>'   # observe
tmux attach-session -t '<session-name>'      # interact
```

Tell the parent when taking control and when handing control back. It must not
send instructions while you own the child.

## Restart the same conversation

Inside a launched session, `Ctrl-b r` restarts the agent into its exact recorded
conversation. Your tmux prefix may differ. The required binding is:

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

Include the same profile, model and permission settings in both commands; keep
the initial prompt out of the resume command. Hooks are reapplied automatically.
The child runs `tmux-subagent-register.sh claude` (or `codex` / `agy`) as its
first task action. Claude startup hooks, Codex notify, and local identity hooks
also capture identity. No identity means a visible error, never a fresh or
“most recent” conversation. A process lock refuses overlapping resumes.

This applies to newly launched sessions; existing panes keep their original
commands. Pressing the shortcut interrupts active work. In the local scripts
integration, `/done` also preserves the managed pane's resume settings.

## Children notify the parent

A tmux pane cannot wake its parent, so the skill sets up a push channel at
launch. Verified 2026-09-09: Claude children on the **same profile** (same
`CLAUDE_CONFIG_DIR`) `SendMessage` the parent's peer name on COMPLETED /
BLOCKED / NEEDS-INPUT and the parent's `notify_when_idle` yields one idle
notice. Across profiles neither side lists or can reach the other, so those
children, like Codex and agy, write a result file that the parent waits on in
the background with `tmux-subagent-wait.sh`. Turn-end hooks
(`codex -c notify=[...]` via `tmux-subagent-codex-notify.sh`, Claude
`--settings` Stop hook via `tmux-subagent-status.sh`) append to a shared
`status.jsonl` without editing user config; the launch helper adds them for the
children it starts when given a task ID. Details and the measurements are in the
skill's "Notifications" section.

## Finished children

Keep them open for follow-ups. The agreed central registry lives at
`${XDG_STATE_HOME:-$HOME/.local/state}/tmux-subagents/agents.json`, outside repos.
Its `process_state` and `task_outcome` fields are written at launch and never
updated, so a child's state is derived on every read instead: from its tmux
session, its pane, its result file, the status log, and the agent's own live
listing. Closing verifies by PID before the entry is removed. Conversation
history and result artifacts remain. Busy children and unselected descendants
are protected. On the author's machine that is `agent-clean-fz` (a preview and
multi-select picker) and `agent-subagents-close`; elsewhere it is the Cleanup
procedure done by hand.

## Privacy and design

Published examples use generic labels. Keep profile mappings, workspace paths,
briefs, transcripts, results, and runtime metadata in private local storage.
Before a non-work parent hands off to a work profile, minimize personal context
and confirm any possible private-personal-data access with the user unless that
scope was already explicitly authorized. This includes files, memory, and tools,
not just the prompt. Loading the skill grants no additional permissions and does
not switch branches.

- [Skill](skills/tmux-subagents/SKILL.md)
- [Design and remaining automation](docs/design.md)
- [Related projects and integration choices](docs/related-projects.md)
- [Skills CLI installation formats](https://github.com/vercel-labs/skills#source-formats)
