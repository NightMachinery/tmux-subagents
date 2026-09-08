# tmux-subagents

A shared Claude Code and Codex skill for interactive subagents in tmux.
Children stay inspectable, can launch grandchildren, and inherit their parent's
provider and profile unless explicitly overridden.

**Status:** instruction skill. A bundled launcher, automated central registry,
and `agent-clean-fz` are planned; installing this skill does not install those
commands. The rich cleanup preview is waiting for an existing shared renderer.

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

## Use

Invoke `/tmux-subagents` in Claude Code or `$tmux-subagents` in Codex, then ask:

> Launch a child to review the parser. Use the same provider and profile,
> keep this worktree, and leave the child open when it finishes.

The skill guides the agent to launch a detached interactive session, provide
its attach command, track parentage, and collect an explicit task result.
A child receives this same skill and its parent context before delegating again.

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

## Finished children

Keep them open for follow-ups. The agreed central registry lives at
`${XDG_STATE_HOME:-$HOME/.local/state}/tmux-subagents/agents.json`, outside repos.
The planned `agent-clean-fz` will offer rich previews and multi-selection, verify
closure, then remove closed agents from that registry. Conversation history and
result artifacts remain. Busy children and unselected descendants are protected.

## Privacy and design

Published examples use generic labels. Keep profile mappings, workspace paths,
briefs, transcripts, results, and runtime metadata in private local storage.
Loading the skill grants no additional permissions and does not switch branches.

- [Skill](skills/tmux-subagents/SKILL.md)
- [Design and remaining automation](docs/design.md)
- [Related projects and integration choices](docs/related-projects.md)
- [Skills CLI installation formats](https://github.com/vercel-labs/skills#source-formats)
