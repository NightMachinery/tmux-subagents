#!/bin/sh
# tmux-subagent-status.sh TASK_ID NODE_ID STATE [SUMMARY|-]
#
# Child side (also usable from provider hooks such as Codex `notify` via
# tmux-subagent-codex-notify.sh, or Claude Stop/Notification hooks). Appends one
# JSON line to the shared status log
# ${TMUX_SUBAGENTS_STATE:-$XDG_STATE_HOME/tmux-subagents}/status.jsonl.
# STATE: started | progress | needs_input | blocked | completed | failed | turn_end
# SUMMARY "-" reads stdin (Claude hooks deliver their JSON payload there).
# Both forms of SUMMARY are truncated to 2000 characters, because hook payloads
# carry whole assistant messages; the log is a signal, not an archive.
# A parent can `tail -f` this file (Claude Code: Monitor) filtered by TASK_ID.
# A status line never publishes a result: only the result file does that.
set -eu
umask 077
task="$1"; node="$2"; state="$3"; summary="${4:-}"
# Drain the rest of stdin so a hook writing a large payload does not get EPIPE.
if [ "$summary" = "-" ]; then summary=$(head -c 2000; cat >/dev/null 2>&1); fi
dir="${TMUX_SUBAGENTS_STATE:-${XDG_STATE_HOME:-$HOME/.local/state}/tmux-subagents}"
mkdir -p "$dir"; chmod 700 "$dir"
python3 - "$dir/status.jsonl" "$task" "$node" "$state" "$summary" <<'PY'
import json, os, sys, time
path, task, node, state, summary = sys.argv[1:6]
line = json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "task_id": task,
                   "node_id": node, "state": state, "summary": summary[:2000]})
fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
os.fchmod(fd, 0o600)  # also narrows a log left over from an older version
with os.fdopen(fd, "a") as f: f.write(line + "\n")
PY
