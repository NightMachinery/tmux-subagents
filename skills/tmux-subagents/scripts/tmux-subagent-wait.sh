#!/bin/sh
# tmux-subagent-wait.sh RESULT_FILE [PANE_ID] [POLL_SECONDS]
#
# Parent side. Blocks until ONE of: the result file exists, a sibling
# needs-input file (RESULT_FILE with .needs-input.md appended) exists, or the
# child's tmux pane is dead / gone. Prints one line describing which, then
# exits. Run it in the background (Claude Code: Bash with run_in_background)
# so the parent gets exactly one completion notification instead of polling.
set -u
result="$1"; pane="${2:-}"; poll="${3:-15}"
need="${result%.md}.needs-input.md"
while :; do
  [ -f "$result" ] && { echo "RESULT $result"; exit 0; }
  [ -f "$need" ] && { echo "NEEDS-INPUT $need"; exit 0; }
  if [ -n "$pane" ]; then
    if ! tmux has-session -t "$pane" 2>/dev/null; then echo "GONE $pane (no result)"; exit 1; fi
    if [ "$(tmux display-message -p -t "$pane" '#{pane_dead}' 2>/dev/null)" = "1" ]; then
      echo "DEAD $pane (process exited, no result)"; exit 1
    fi
  fi
  sleep "$poll"
done
