#!/bin/sh
# tmux-subagent-agy-profile.sh create PROFILE --workspace DIR [--write DIR]...
#                                     [--source ROOT] [--no-hook]
# tmux-subagent-agy-profile.sh flags PROFILE
# tmux-subagent-agy-profile.sh usage PROFILE
# tmux-subagent-agy-profile.sh destroy PROFILE [--all]
#
# A throwaway agy profile for a sandboxed worker, so the user's own agy
# settings and hooks are never edited. `create` copies three files from the
# account's root (default ~/.gemini) with cp, never reading them: the auth
# token and the onboarding state (cache/onboarding.json, without which agy
# 1.4.2 shows its colour and terms screens, the latter with the data-collection
# box ticked; jetski_state.pbtxt as well). It writes
# antigravity-cli/settings.json with the verified sandbox keys, one write_file
# rule per workspace or --write root, and the workspace as trusted (which skips
# the trust question), and installs the Stop hook in config/hooks.json.
# Re-running it repoints the write rules and keeps other settings agy added.
#
# `flags` prints the arguments that select the profile, for
#   SSH_CONNECTION=${SSH_CONNECTION:-agy-file-auth} command agy $(... flags P) ...
# `usage` runs agy's /usage for the profile's account (no quota is spent).
# `destroy` deletes the token copy; --all removes the whole profile, which it
# only does for a directory this script created.
set -eu
umask 077
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
app=antigravity-cli
token=antigravity-oauth-token
onboarding='jetski_state.pbtxt
cache/onboarding.json'  # one per line: create splits on newlines
marker=.tmux-subagent-agy-profile

die() { printf 'tmux-subagent-agy-profile: %s\n' "$1" >&2; exit 64; }
absdir() { [ -d "$1" ] || die "not a directory: $1"; (CDPATH= cd -- "$1" && pwd -P); }

[ $# -ge 2 ] || die 'usage: create|flags|usage|destroy PROFILE [options]'
cmd=$1 profile=$2
shift 2

case $cmd in
create)
  source=$HOME/.gemini hook=1 workspace= writes=
  while [ $# -gt 0 ]; do
    case $1 in
      --workspace) [ $# -ge 2 ] || die '--workspace needs a directory'; workspace=$(absdir "$2"); shift 2 ;;
      --write) [ $# -ge 2 ] || die '--write needs a directory'
        writes="$writes$(absdir "$2")
"; shift 2 ;;
      --source) [ $# -ge 2 ] || die '--source needs a directory'; source=$2; shift 2 ;;
      --no-hook) hook=0; shift ;;
      *) die "unknown option: $1" ;;
    esac
  done
  [ -n "$workspace" ] || die 'create needs --workspace DIR'
  IFS='
'  # $writes holds one root per line; paths may contain spaces
  source=$(absdir "$source")
  [ -f "$source/$app/$token" ] || die "no $app/$token under the source root; sign in there first"
  if [ -d "$profile" ] && [ ! -f "$profile/$marker" ] && [ -n "$(command ls -A "$profile")" ]; then
    die 'PROFILE exists and was not made by this script; pick a new directory'
  fi
  command mkdir -p "$profile/$app" "$profile/config"
  profile=$(absdir "$profile")
  case "$profile/" in "$source/"*) die 'the profile must not be inside the source root' ;; esac
  case "$source/" in "$profile/"*) die 'the source root must not be inside the profile' ;; esac
  for root in "$workspace" $writes; do
    case $root in /|"$HOME") die "refusing a write rule for $root: name the workspace itself" ;; esac
  done
  : > "$profile/$marker"
  command chmod 700 "$profile" "$profile/$app" "$profile/config"
  command cp "$source/$app/$token" "$profile/$app/$token"
  command chmod 600 "$profile/$app/$token"
  for f in $onboarding; do
    if [ -f "$source/$app/$f" ]; then
      command mkdir -p "$(dirname -- "$profile/$app/$f")"
      command cp "$source/$app/$f" "$profile/$app/$f"
    else
      echo "tmux-subagent-agy-profile: no $f in the source; agy may show its first-run screens" >&2
    fi
  done
  python3 - "$profile" "$hook" "$here" "$workspace" $writes <<'PY'
import json, os, shlex, sys, tempfile
profile, hook, here, roots = sys.argv[1], sys.argv[2] == '1', sys.argv[3], sys.argv[4:]

def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}

def save(path, data):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix='.profile-')
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write('\n')
    os.replace(tmp, path)

path = os.path.join(profile, 'antigravity-cli', 'settings.json')
settings = load(path)
settings.update(enableTerminalSandbox=True, toolPermission='proceed-in-sandbox',
                artifactReviewPolicy='agent-decides')
perms = settings.setdefault('permissions', {})
allow = [r for r in perms.get('allow', []) if not r.startswith('write_file(')]
allow += ['write_file(%s/)' % r.rstrip('/') for r in dict.fromkeys(roots)]
perms['allow'] = allow
trusted = settings.setdefault('trustedWorkspaces', [])
if roots[0] not in trusted:
    trusted.append(roots[0])
save(path, settings)

path = os.path.join(profile, 'config', 'hooks.json')
hooks = load(path)
if hook:
    # agy waits for the hook's {}; print it even if the script cannot run.
    command = 'sh %s 2>/dev/null || printf \'{}\\n\'' % shlex.quote(here + '/tmux-subagent-agy-stop-hook.sh')
    hooks['tmux-subagents'] = {'Stop': [{'type': 'command', 'command': command, 'timeout': 5}]}
else:
    hooks.pop('tmux-subagents', None)
save(path, hooks)
PY
  printf '%s\n' "$profile"
  ;;
flags)
  profile=$(absdir "$profile")
  printf -- '--gemini_dir=%s --app_data_dir=%s\n' "$profile" "$app"
  ;;
usage)
  profile=$(absdir "$profile")
  [ -f "$profile/$app/$token" ] || die 'the profile has no token copy'
  SSH_CONNECTION=${SSH_CONNECTION:-agy-file-auth} \
    exec agy "--gemini_dir=$profile" "--app_data_dir=$app" -p /usage
  ;;
destroy)
  all=0
  [ "${1:-}" = --all ] && all=1
  profile=$(absdir "$profile")
  [ -f "$profile/$marker" ] || die 'not a profile made by this script; delete it by hand'
  command rm -f "$profile/$app/$token"
  [ "$all" = 1 ] && command rm -rf "$profile"
  printf 'removed %s\n' "$([ "$all" = 1 ] && echo "$profile" || echo "the token copy in $profile")"
  ;;
*) die "unknown command: $cmd" ;;
esac
