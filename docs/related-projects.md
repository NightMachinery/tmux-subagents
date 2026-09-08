# Related projects

Reviewed project documentation and selected skill/source files. These are
references and optional integration candidates, not installed dependencies or
end-to-end validated alternatives. No upstream implementation was copied.

## Agent Deck

[Project](https://github.com/asheshgoplani/agent-deck) ·
[Skill](https://github.com/asheshgoplani/agent-deck/blob/main/skills/agent-deck/SKILL.md)

Supports parent-linked sessions, inherited context, profiles, and explicit
worker completion assertions. Adopt the distinction between an idle turn and a
finished assignment; keep our task-ID-scoped result artifacts. Its larger TUI,
conductor, channel, and worktree system is optional infrastructure rather than
something this skill needs. Some provider claims in the inspected skill differ
from currently installed CLI capabilities, so verify them independently.

## cc-tmux-agents

[Project](https://github.com/phuongduyphan/cc-tmux-agents) ·
[Codex skill](https://github.com/phuongduyphan/cc-tmux-agents/blob/main/skills/codex/SKILL.md)

Close match to persistent, human-steerable tmux workers. Adopt its small common
operation vocabulary and separation of provider-specific dispatch. The inspected
Codex skill uses a fixed default session name and a permissions-bypass launch;
our convention requires unique hierarchical names and retained permission
policy. This is a small project: use it as a design reference, not evidence of
production reliability.

## tmux-agent-status

[Project](https://github.com/samleeney/tmux-agent-status)

Provides lifecycle-hook tracking, an fzf switcher, previews, and cleanup in a
tmux UI. Adopt hook-derived activity as distinct from asserted task completion.
A future opt-in bridge could publish compatible status files. Do not install its
sidebar or change global key bindings as a side effect of loading this skill.
Its close action is broader than our finished-child cleanup contract. Reuse the
user's shared preview renderer once available rather than starting a competing
preview implementation here.

## obra/external-subagents

[Project](https://github.com/obra/external-subagents)

Uses noninteractive Codex execution with controller identity and persistent
metadata. Useful reference for separating controller state from worker output.
Its headless execution model does not provide the continuously interactive tmux
child required here, so it is not the default runtime.

## What changed in this skill

- Added a common operation vocabulary for both providers.
- Kept task completion explicit and separate from turn-end/activity hooks.
- Defined optional status integration without making it a dependency.
- Preserved provider/profile inheritance, recursive naming, current-worktree
  behavior, and local-only runtime data over incompatible upstream defaults.

Any future code reuse must verify the selected version and license and retain
required attribution. Prefer narrow adapters over adopting an entire manager.
