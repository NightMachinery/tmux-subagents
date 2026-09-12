#!/bin/sh
# PROJECT TASK PROVIDER-MODEL -> readable name with a collision-resistant suffix.
set -eu
exec python3 - "$@" <<'PY'
import re, secrets, sys, unicodedata
if len(sys.argv) != 4:
    sys.exit('usage: tmux-subagent-name.sh PROJECT TASK PROVIDER-MODEL')
def slug(value, limit):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()
    value = re.sub(r'[^a-z0-9]+', '-', value).strip('-')[:limit].rstrip('-')
    if not value:
        sys.exit('name fields must contain at least one ASCII letter or digit')
    return value
print('ag--' + '--'.join(slug(v, n) for v, n in zip(sys.argv[1:], (20, 32, 28))) + '--' + secrets.token_hex(3))
PY
