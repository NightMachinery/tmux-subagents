#!/bin/sh
# agy Stop hook for a worker in tmux: tells its operator that the turn ended,
# so the operator can sleep until then instead of polling. Installed into a
# throwaway profile's config/hooks.json by tmux-subagent-agy-profile.sh.
#
# Target, from the agy process's environment: TMUX_SUBAGENT_AGY_NOTIFY is
# paseo:<agent-id> (sent with `paseo send --no-wait`) or log:<path> (one line
# appended to an events.log, which wakes tmux-subagent-watch.sh). With
# TMUX_SUBAGENT_TASK and TMUX_SUBAGENT_NODE set, as the launch helper sets
# them, a turn_end line also goes to status.jsonl.
#
# agy waits for a hook: drain stdin, start the sends in the background, print
# {} and return at once. The hook also touches the bell's mark file, so
# tmux-subagent-agy-bell.sh does not report the same turn end again.
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
command cat >/dev/null 2>&1
spec=${TMUX_SUBAGENT_AGY_NOTIFY:-}
state=${TMUX_SUBAGENTS_STATE:-${XDG_STATE_HOME:-$HOME/.local/state}/tmux-subagents}
name=agy
tail=
if [ -n "${TMUX_PANE:-}" ]; then
  name=$(command tmux display-message -p -t "$TMUX_PANE" '#S' 2>/dev/null || echo agy)
  sock=$(command basename "${TMUX%%,*}" 2>/dev/null)
  key=$(printf '%s-%s' "$sock" "${TMUX_PANE#%}" | command tr -c 'A-Za-z0-9_.-' '-')
  [ -d "$state/agy-bell" ] && command touch "$state/agy-bell/$key.mark" 2>/dev/null
  tail=$(command tmux capture-pane -p -t "$TMUX_PANE" 2>/dev/null |
    command grep -v '^[[:space:]]*$' | command tail -15 | command cut -c1-220)
fi
case $spec in
  paseo:?*)
    ( command paseo send "${spec#paseo:}" "[agy-bell] $name: the worker's turn ended. Last lines of its pane:
$tail" --no-wait >/dev/null 2>&1 & ) ;;
  log:?*)
    printf '[%s] [agy-bell] %s: turn ended\n' "$(command date -u '+%Y-%m-%d %H:%M:%S UTC')" "$name" \
      >> "${spec#log:}" 2>/dev/null ;;
esac
if [ -n "${TMUX_SUBAGENT_TASK:-}" ] && [ -n "${TMUX_SUBAGENT_NODE:-}" ]; then
  ( "$here/tmux-subagent-status.sh" "$TMUX_SUBAGENT_TASK" "$TMUX_SUBAGENT_NODE" turn_end agy \
      </dev/null >/dev/null 2>&1 & )
fi
printf '{}\n'
