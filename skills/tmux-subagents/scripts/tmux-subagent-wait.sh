#!/bin/sh
# tmux-subagent-wait.sh RESULT_FILE [PANE_ID] [POLL_SECONDS]
#
# Parent side. Blocks until ONE of: the result file exists, its sibling
# needs-input file (the result path with .md replaced by .needs-input.md)
# exists, or the child's tmux pane is dead / gone. Prints one line describing
# which, then exits. Run it in the background (Claude Code: Bash with
# run_in_background) so the parent gets exactly one notification per
# assignment; the polling is not removed, only moved out of the parent's turn.
#
# Outcomes: RESULT and NEEDS-INPUT exit 0, DEAD and GONE exit 1; POLL_SECONDS
# defaults to 15. It tests existence only, so the child must publish both files
# atomically (write a sibling temp file, then rename) and the parent must
# validate task_id/node_id inside the file after waking.
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
