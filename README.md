# tmux-subagents

A shared Claude Code, Codex, and Google Antigravity (`agy`) skill for interactive subagents in tmux.
Children stay inspectable, can launch grandchildren, and inherit their parent's
provider and profile unless explicitly overridden.

**Status:** instruction skill plus three small POSIX helpers in
`skills/tmux-subagents/scripts/` (`tmux-subagent-launch.sh` creates and
registers a session, `tmux-subagent-wait.sh` blocks until a child's result,
needs-input file, or pane death, `tmux-subagent-status.sh` appends a status
line for hooks). `agent-clean-fz` and the rich cleanup preview are still planned.

## Install

Requires tmux and the authenticated coding CLIs you want to use.

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
ag--<project>--<run>--<lineage>--<provider-model>--<role>
ag--demo--review-k7m2--r-a3-b8--claude-opus--tests
```

Names show the project, session/run, ancestry, launch model, and role. Stable
tmux IDs identify sessions internally. Check collisions before creating a
session and retry if another launcher wins the race.

```sh
tmux list-sessions
tmux attach-session -r -t '<session-name>'   # observe
tmux attach-session -t '<session-name>'      # interact
```

Tell the parent when taking control and when handing control back. It must not
send instructions while you own the child.

## Children notify the parent

A tmux pane cannot wake its parent, so the skill sets up a push channel at
launch: Claude children `SendMessage` the parent's peer name on COMPLETED /
BLOCKED / NEEDS-INPUT and the parent arms `notify_when_idle`; Codex and agy
children write a result file that the parent waits on in the background with
`tmux-subagent-wait.sh`; provider hooks can append to a shared `status.jsonl`.
Details in the skill's "Notifications" section.

## Finished children

Keep them open for follow-ups. The agreed central registry lives at
`${XDG_STATE_HOME:-$HOME/.local/state}/tmux-subagents/agents.json`, outside repos.
The planned `agent-clean-fz` will offer rich previews and multi-selection, verify
closure, then remove closed agents from that registry. Conversation history and
result artifacts remain. Busy children and unselected descendants are protected.

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
