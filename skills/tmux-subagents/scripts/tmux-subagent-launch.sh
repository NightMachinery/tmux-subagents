#!/bin/sh
# Public entrypoint; argument parsing and atomic registry writes live beside it.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$here/tmux-subagent-launch.py" "$@"
