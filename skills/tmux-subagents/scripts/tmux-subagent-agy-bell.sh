#!/bin/sh
# Public entrypoint; the bell itself lives beside it (usage: --help).
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$here/tmux-subagent-agy-bell.py" "$@"
