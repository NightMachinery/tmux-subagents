#!/bin/sh
# tmux-subagent-status.sh TASK_ID NODE_ID STATE [SUMMARY]
#
# Child side (also usable from provider hooks such as Codex `notify` or Claude
# Stop/Notification hooks). Appends one JSON line to the shared status log
# ${TMUX_SUBAGENTS_STATE:-$XDG_STATE_HOME/tmux-subagents}/status.jsonl.
# STATE: started | progress | needs_input | blocked | completed | failed
# A parent can `tail -f` this file (Claude Code: Monitor) filtered by TASK_ID.
set -eu
task="$1"; node="$2"; state="$3"; summary="${4:-}"
dir="${TMUX_SUBAGENTS_STATE:-${XDG_STATE_HOME:-$HOME/.local/state}/tmux-subagents}"
mkdir -p "$dir"
python3 - "$dir/status.jsonl" "$task" "$node" "$state" "$summary" <<'PY'
import json, sys, time
path, task, node, state, summary = sys.argv[1:6]
line = json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "task_id": task,
                   "node_id": node, "state": state, "summary": summary})
with open(path, "a") as f: f.write(line + "\n")
PY
