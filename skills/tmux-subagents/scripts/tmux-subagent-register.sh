#!/bin/sh
# Run inside the child before its first task action. No personal shell required.
set -eu
plugin=${AGENT_SESSION_PLUGIN:-${NIGHTDIR:-$HOME/scripts}/zshlang/plugins/agent-session/agent-session.plugin.zsh}
exec zsh -f -c 'source "$1" && agent-session-register-current "$2"' tmux-subagent "$plugin" "$1"
