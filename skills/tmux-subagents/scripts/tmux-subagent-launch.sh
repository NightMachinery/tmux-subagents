#!/bin/sh
# tmux-subagent-launch.sh [--task TASK] [--notify-chain ITEM]... NAME WORKDIR COMMAND
#
# Create one detached tmux session per agent, retain the pane on exit, wire the
# provider's turn-end hook, and register the session in the private registry.
#
# COMMAND is shell code (not a prompt, not an argv array). It runs under
# `zsh -ic` so interactive shell functions (claude-work, codex-m, ...) resolve.
# COMMAND and WORKDIR are passed to zsh as positional arguments, never spliced
# into a generated command string, so spaces, quotes, `$` and backticks in a
# legitimate path are safe. Because an interactive zsh may change directory on
# startup, the pane cds to WORKDIR after shell startup; tmux's -c alone is not
# enough.
#
# --task TASK (or TMUX_SUBAGENT_TASK) turns on turn-end status wiring. The first
# word of COMMAND that is not a VAR=value assignment or `env` selects the
# provider, and the flag is inserted directly after that word (an unrecognized
# provider is reported on stderr and launched unchanged):
#   claude | claude-m | claude-work ->
#     --settings '{"hooks":{"Stop":[...tmux-subagent-status.sh TASK NAME turn_end -...]}}'
#   codex | codex-m ->
#     -c 'notify=["<abs>/tmux-subagent-codex-notify.sh","TASK","NAME"]'
# Both are command-line only: no user config file is edited, and Claude's
# --settings merges with the user's settings rather than replacing them.
# The chain to an existing notify command is NOT automatic: a user with a
# notify entry in ~/.codex/config.toml must pass each of its argv words as a
# repeated --notify-chain ITEM, in order, or that bell stops ringing.
# Without --task, COMMAND is launched exactly as given.
#
# remain-on-exit is enabled *before* COMMAND can run: the session is created
# with a placeholder holder process, the option is set, then the pane is
# respawned with COMMAND. A command that fails in its first millisecond still
# leaves an inspectable dead pane.
#
# The registry key is the session name on the current tmux socket; the socket
# path is recorded but is not part of the key, so identical names on two
# sockets would still overwrite one record. On an existing name this exits 2
# without touching the session: the caller allocates another ID and retries.
#
# Exit 0 launched and registered, 2 name collision, 3 session created and LEFT
# RUNNING but registration failed (its IDs are still printed), 64 usage error.
#
# Prints: NAME SESSION_ID PANE_ID
set -eu
umask 077
here=$(cd "$(dirname "$0")" && pwd)
RS=$(printf '\036')
task="${TMUX_SUBAGENT_TASK:-}"; chain=""
while [ $# -gt 0 ]; do
  case "$1" in
    --task) task="$2"; shift 2 ;;
    --task=*) task="${1#--task=}"; shift ;;
    --notify-chain) chain="$chain$2$RS"; shift 2 ;;
    --notify-chain=*) chain="$chain${1#--notify-chain=}$RS"; shift ;;
    --) shift; break ;;
    -*) echo "usage: $0 [--task TASK] [--notify-chain ITEM]... NAME WORKDIR COMMAND" >&2; exit 64 ;;
    *) break ;;
  esac
done
[ $# -eq 3 ] || { echo "usage: $0 [--task TASK] [--notify-chain ITEM]... NAME WORKDIR COMMAND" >&2; exit 64; }
name="$1"; dir="$2"; cmd="$3"
if tmux has-session -t "=$name" 2>/dev/null; then
  echo "collision: session $name exists" >&2; exit 2
fi
if [ -n "$task" ]; then
  word=$(set -f; for w in $cmd; do case "$w" in (*=*|env) continue ;; (*) printf %s "$w"; break ;; esac; done)
  flag=$(python3 - "${word##*/}" "$here" "$task" "$name" "$chain" <<'PY'
import json, shlex, sys
prog, here, task, node, chain = sys.argv[1:6]
if prog in ("claude", "claude-m", "claude-work"):
    hook = "%s/tmux-subagent-status.sh %s %s turn_end -" % (here, task, node)
    s = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": hook}]}]}}
    print("--settings " + shlex.quote(json.dumps(s, separators=(",", ":"))))
elif prog in ("codex", "codex-m"):
    argv = ["%s/tmux-subagent-codex-notify.sh" % here, task, node]
    argv += [i for i in chain.split("\x1e") if i]
    print("-c " + shlex.quote("notify=" + json.dumps(argv, separators=(",", ":"))))
PY
)
  if [ -n "$flag" ] && [ -n "$word" ]; then
    cmd="${cmd%%"$word"*}$word $flag${cmd#*"$word"}"
  else
    echo "no turn-end hook wired: unrecognized provider '${word:-?}'" >&2
  fi
fi
ids=$(tmux new-session -d -P -F '#{session_id} #{pane_id}' -s "$name" -c "$dir" \
      sh -c 'while :; do sleep 3600; done')
sid=${ids% *}; pane=${ids#* }
tmux set-option -t "$sid" remain-on-exit on >/dev/null
tmux set-option -t "$sid" allow-rename off >/dev/null
sock=$(tmux display-message -p -t "$sid" '#{socket_path}' 2>/dev/null || echo '')
tmux respawn-pane -k -t "$pane" -c "$dir" \
     zsh -ic 'cd "$1" && eval "$2"' tmux-subagent "$dir" "$cmd"
reg_dir="${TMUX_SUBAGENTS_STATE:-${XDG_STATE_HOME:-$HOME/.local/state}/tmux-subagents}"
mkdir -p "$reg_dir"; chmod 700 "$reg_dir"
if python3 - "$reg_dir/agents.json" "$name" "$dir" "$sid" "$pane" \
     "${TMUX_SUBAGENT_PARENT:-}" "${TMUX_SUBAGENT_ROOT:-}" "$sock" "$task" <<'PY'
import fcntl, json, os, sys, tempfile, time
reg, name, d, sid, pane, parent, root, sock, task = sys.argv[1:10]
entry = {"node_id": name, "root_id": root or name, "parent": parent, "task_id": task,
         "tmux_session_id": sid, "tmux_pane_id": pane, "tmux_socket": sock,
         "workdir": d, "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "process_state": "running", "task_outcome": "unknown"}
# Lock a stable sidecar file: agents.json itself is replaced on every write, so
# two writers can otherwise hold locks on different generations of that inode.
fd = os.open(reg + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
try:
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        with open(reg) as f: txt = f.read().strip()
    except FileNotFoundError:
        txt = ""
    data = json.loads(txt) if txt else {}
    data[name] = entry
    # Unique temp file in the registry's own directory: a fixed .tmp path lets
    # concurrent launches clobber each other, and rename is atomic only within
    # one directory. mkstemp creates it 0600.
    tfd, tmp = tempfile.mkstemp(dir=os.path.dirname(reg) or ".",
                                prefix=".agents.", suffix=".tmp")
    try:
        with os.fdopen(tfd, "w") as g:
            json.dump(data, g, indent=1); g.write("\n")
        os.replace(tmp, reg)
    except BaseException:
        os.unlink(tmp); raise
finally:
    os.close(fd)
PY
then
  echo "$name $sid $pane"
else
  echo "registration failed: session $name ($sid $pane) is running and was left open; register it by hand or close it" >&2
  echo "$name $sid $pane"
  exit 3
fi
