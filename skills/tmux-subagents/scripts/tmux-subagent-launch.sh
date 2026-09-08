#!/bin/sh
# tmux-subagent-launch.sh NAME WORKDIR COMMAND
#
# Create one detached tmux session per agent, retain the pane on exit, and
# register it in the central registry. COMMAND runs under `zsh -ic` so shell
# functions (claude-work, codex-m, ...) resolve. Because an interactive zsh may
# change directory on startup, `cd WORKDIR &&` is prepended to COMMAND; do not
# rely on tmux's -c alone.
#
# Prints: NAME SESSION_ID PANE_ID
set -eu
name="$1"; dir="$2"; cmd="$3"
if tmux has-session -t "=$name" 2>/dev/null; then
  echo "collision: session $name exists" >&2; exit 2
fi
ids=$(tmux new-session -d -P -F '#{session_id} #{pane_id}' -s "$name" -c "$dir" \
      zsh -ic "cd \"$dir\" && $cmd")
sid=${ids% *}; pid=${ids#* }
tmux set-option -t "$sid" remain-on-exit on >/dev/null
tmux set-option -t "$sid" allow-rename off >/dev/null
reg_dir="${TMUX_SUBAGENTS_STATE:-${XDG_STATE_HOME:-$HOME/.local/state}/tmux-subagents}"
mkdir -p "$reg_dir"
python3 - "$reg_dir/agents.json" "$name" "$dir" "$sid" "$pid" "${TMUX_SUBAGENT_PARENT:-}" "${TMUX_SUBAGENT_ROOT:-}" <<'PY'
import json, sys, time, fcntl, os
reg, name, d, sid, pid, parent, root = sys.argv[1:8]
entry = {"node_id": name, "root_id": root or name, "parent": parent, "tmux_session_id": sid,
         "tmux_pane_id": pid, "workdir": d, "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "process_state": "running", "task_outcome": "unknown"}
with open(reg, "a+") as f:
    fcntl.flock(f, fcntl.LOCK_EX); f.seek(0); txt = f.read().strip()
    data = json.loads(txt) if txt else {}
    data[name] = entry
    tmp = reg + ".tmp"
    with open(tmp, "w") as g: json.dump(data, g, indent=1)
    os.replace(tmp, reg)
PY
echo "$name $sid $pid"
