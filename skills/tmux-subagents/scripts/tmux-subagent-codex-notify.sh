#!/bin/sh
# tmux-subagent-codex-notify.sh TASK_ID NODE_ID [CHAIN_CMD ARGS...] PAYLOAD
#
# Adapter for Codex's `notify` hook, which runs an argv array and appends one
# JSON payload argument (type "agent-turn-complete", thread-id, turn-id,
# last-assistant-message, ...). Records a turn_end line via
# tmux-subagent-status.sh, then execs the user's original notify command (the
# optional CHAIN_CMD ARGS) with the same payload so an existing bell keeps
# working. Launch a child with, for example:
#   codex -c 'notify=["/abs/tmux-subagent-codex-notify.sh","TASK","NODE","brishzq.zsh","h-codex-notify"]' ...
# Turn end is not task completion: the parent still needs the result file.
set -u
task="$1"; node="$2"; shift 2
eval "payload=\${$#}"
here=$(cd "$(dirname "$0")" && pwd)
"$here/tmux-subagent-status.sh" "$task" "$node" turn_end "$payload" || true
[ $# -le 1 ] && exit 0
# drop the trailing payload, keep the chain command
n=$(( $# - 1 )); i=1
for a in "$@"; do [ $i -le $n ] && set -- "$@" "$a"; i=$((i+1)); done
shift $((n+1))
exec "$@" "$payload"
