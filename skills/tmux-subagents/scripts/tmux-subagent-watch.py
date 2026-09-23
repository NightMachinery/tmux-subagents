#!/usr/bin/env python3
"""Registry-driven watcher for tmux children: plain polling, no LLM tokens.

Selects children from the shared registry, re-reading it every cycle, and
prints one line per event, `EVENT <node> <kind> <detail>`:

  pane-dead    the child's process exited (remain-on-exit keeps the pane)
  pane-gone    the pane or its whole tmux server no longer exists
  menu         a permission, trust or choice menu is waiting on screen
  result       a result*.md file in the task directory was created or changed
  needs-input  a *.needs-input.md file there was created or changed
  log          a new line in the task directory's events.log (debounced)
  turn-end     a turn_end line in status.jsonl (only with --turn-end)
  NO-CHILDREN  the selection is empty (node `-`)
  timeout      --timeout elapsed with nothing to report (node `-`)

One-shot by default: it exits after the first batch, so a parent runs it as a
harness-tracked background task and re-runs the same command after acting.
What it has reported is recorded under <state>/watch/, keyed by the selection,
so a re-run never replays it; a child seen for the first time has its existing
files baselined unless it was registered after that record was started.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time

STAMP = '%Y-%m-%dT%H:%M:%S'  # the launch helper's `created` format

# Menus seen on screen (2026-09): Claude Code `❯ 1. Yes` (permissions) and
# `❯ No, exit` (trust), Codex `› 1. Yes, continue`, agy `> Yes, I trust this
# folder`. Numbers are optional, so what makes a menu is a cursor line beside
# an unselected option, with a key hint below it: every one of those menus has
# such a footer, while typed text or a transcript line quoting a menu does not.
BORDER_LEFT = re.compile(r'^\s*[│┃║]')
BORDER_RIGHT = re.compile(r'[│┃║]\s*$')
CURSOR = re.compile(r'^\s*[❯›>]\s+(\S.*)$')
FOOTER = re.compile(r'(?i)enter to (confirm|select|continue)|esc to (cancel|exit)'
                    r'|press enter|enter confirm|↑/↓')
NUMBERED = re.compile(r'^\d+\.\s')


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, self.prog + ': error: ' + message + '\n')


def state_root():
    return Path(os.environ.get('TMUX_SUBAGENTS_STATE', str(
        Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'tmux-subagents')))


def write_json(path, data):
    fd, tmp = tempfile.mkstemp(prefix='.watch-', dir=path.parent)
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def tmux(entry, *args):
    sock = entry.get('tmux_socket')
    cmd = ['tmux', *(['-S', sock] if sock else []), *args]
    return subprocess.run(cmd, capture_output=True, text=True, errors='replace')


def pane_state(entry):
    """('alive'|'dead'|'gone', detail); ('', '') when no pane is recorded."""
    pane = entry.get('tmux_pane_id')
    if not pane:
        return '', ''
    out = tmux(entry, 'display-message', '-p', '-t', pane,
               '#{pane_id} #{pane_dead} #{pane_dead_status}')
    words = out.stdout.split()
    if out.returncode or not words or words[0] != pane:
        return 'gone', pane
    if len(words) > 1 and words[1] == '1':
        return 'dead', pane + (' exit ' + words[2] if len(words) > 2 else '')
    return 'alive', pane


def find_menu(screen):
    """(signature, detail) for the bottom-most menu on screen, or None."""
    lines = [BORDER_RIGHT.sub('', BORDER_LEFT.sub('', l.rstrip())) for l in screen.splitlines()]
    found = None
    for i, line in enumerate(lines):
        m = CURSOR.match(line)
        if not m:
            continue
        numbered = bool(NUMBERED.match(m.group(1)))
        def option(j):
            if not 0 <= j < len(lines):
                return False
            s = lines[j]
            return (s[:1].isspace() and s.strip() != '' and not CURSOR.match(s)
                    and (not numbered or bool(NUMBERED.match(s.strip()))))
        if not (option(i - 1) or option(i + 1)):
            continue
        end = next((j for j in range(i + 1, min(len(lines), i + 16)) if FOOTER.search(lines[j])), None)
        if end is None:
            continue
        start = next((j for j in range(i - 1, max(-1, i - 16), -1) if '?' in lines[j]), None)
        question = lines[start].strip() if start is not None else ''
        block = lines[start if start is not None else i:end + 1]
        body = '\n'.join(re.sub(r'^\s*[❯›>]\s+', '', s).strip() for s in block)
        detail = (question + ' | ' if question else '') + line.strip()
        found = (hashlib.sha1(body.encode()).hexdigest()[:16], detail[:200])
    return found


def main():
    p = Parser(prog='tmux-subagent-watch.sh', description=__doc__.split('\n\n')[0])
    p.add_argument('--parent', action='append', default=[], metavar='ID',
                   help='children whose parent is ID (default: $TMUX_SUBAGENT_NODE)')
    p.add_argument('--root', action='append', default=[], metavar='ID', help='every node under root ID')
    p.add_argument('--node', action='append', default=[], metavar='ID', help='this node')
    p.add_argument('--interval', type=float, default=15, help='seconds between polls (15)')
    p.add_argument('--debounce', type=float, default=60,
                   help='hold events.log lines this long after the first, then print them all (60)')
    p.add_argument('--timeout', type=float, default=0, help='exit 1 after this many quiet seconds')
    p.add_argument('--turn-end', action='store_true', help='also report turn ends from status.jsonl')
    p.add_argument('--follow', action='store_true', help='keep printing instead of exiting')
    args = p.parse_args()

    # A detached copy writing to /dev/null can never notify anyone.
    try:
        out = os.fstat(1)
    except OSError:
        print('tmux-subagent-watch: stdout is closed; nothing would ever see an event', file=sys.stderr)
        return 2
    null = os.stat(os.devnull)
    if stat.S_ISCHR(out.st_mode) and out.st_rdev == null.st_rdev:
        print('tmux-subagent-watch: stdout is /dev/null, so no event could notify anyone; '
              'run it as a tracked background task instead', file=sys.stderr)
        return 2

    if not (args.parent or args.root or args.node):
        own = os.environ.get('TMUX_SUBAGENT_NODE', '')
        if not own:
            p.error('no selection: pass --parent, --root or --node (TMUX_SUBAGENT_NODE is unset)')
        args.parent = [own]
    selectors = sorted({('parent', v) for v in args.parent} | {('root', v) for v in args.root}
                       | {('node', v) for v in args.node})
    key = ','.join(k + '=' + v for k, v in selectors)
    slug = re.sub(r'[^A-Za-z0-9_.-]+', '-', key)[:60] + '-' + hashlib.sha1(key.encode()).hexdigest()[:10]

    root = state_root()
    watch_dir = root / 'watch'
    watch_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = open(watch_dir / (slug + '.lock'), 'a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print('tmux-subagent-watch: another watcher is running for ' + key, file=sys.stderr)
        return 3
    base_path = watch_dir / (slug + '.json')
    try:
        base = json.loads(base_path.read_text())
    except (OSError, ValueError):
        base = {}
    base.setdefault('selection', key)
    base.setdefault('created', time.strftime(STAMP))
    base.setdefault('nodes', {})
    status_path = root / 'status.jsonl'
    if base.get('status_offset') is None:
        base['status_offset'] = status_path.stat().st_size if status_path.exists() else 0

    read_pos = {}        # events.log offsets read but not yet printed
    pending = []         # (node, line) held for the debounce window
    pending_since = None
    started = time.monotonic()
    was_empty = False

    def selected(node, entry):
        return any((k == 'parent' and entry.get('parent') == v) or (k == 'root' and entry.get('root_id') == v)
                   or (k == 'node' and node == v) for k, v in selectors)

    def emit(lines):
        for line in lines:
            print(line, flush=True)

    while True:
        try:
            registry = json.loads((root / 'agents.json').read_text() or '{}')
        except (OSError, ValueError):
            registry = {}
        children = {n: e for n, e in registry.items() if isinstance(e, dict) and selected(n, e)}
        events, dirty = [], False
        now = time.monotonic()

        if not children:
            if not args.follow:
                emit(['EVENT - NO-CHILDREN ' + key])
                return 1
            if not was_empty:
                emit(['EVENT - NO-CHILDREN ' + key])
            was_empty = True
        else:
            was_empty = False
        for gone in set(base['nodes']) - set(children):
            del base['nodes'][gone]
            dirty = True

        for node, entry in sorted(children.items()):
            task = entry.get('task_id', '')
            task_dir = Path(entry['task_dir']) if entry.get('task_dir') else (
                root / 'tasks' / task if task else None)
            results = sorted(task_dir.glob('result*.md')) if task_dir and task_dir.is_dir() else []
            log = task_dir / 'events.log' if task_dir else None
            log_size = log.stat().st_size if log and log.exists() else 0
            node_state = base['nodes'].get(node)
            if node_state is None:
                # First sight: history is not news, unless the child was registered
                # after this record began, in which case nothing of it was reported.
                late = entry.get('created', '') > base['created']
                node_state = base['nodes'][node] = {'files': {}, 'log_offset': 0, 'pane': '', 'menu': ''}
                if not late:
                    node_state['files'] = {f.name: [f.stat().st_mtime_ns, f.stat().st_size] for f in results}
                    node_state['log_offset'] = log_size
                dirty = True

            seen = {}
            for f in results:
                try:
                    st = f.stat()
                except OSError:
                    continue
                sig = seen[f.name] = [st.st_mtime_ns, st.st_size]
                if node_state['files'].get(f.name) != sig:
                    kind = 'needs-input' if f.name.endswith('.needs-input.md') else 'result'
                    events.append(f'EVENT {node} {kind} {f}')
            if seen != node_state['files']:
                node_state['files'] = seen
                dirty = True

            pos = read_pos.get(node, node_state['log_offset'])
            if log_size < pos:  # truncated or replaced: start over
                pos = node_state['log_offset'] = 0
                dirty = True
            if log_size > pos:
                with open(log, 'rb') as f:
                    f.seek(pos)
                    chunk = f.read(log_size - pos)
                whole = chunk[:chunk.rfind(b'\n') + 1]  # leave a partial last line for later
                for raw in whole.splitlines():
                    text = raw.decode('utf-8', 'replace').strip()
                    if text:
                        pending.append((node, text))
                        pending_since = pending_since or now
                pos += len(whole)
            read_pos[node] = pos

            state, detail = pane_state(entry)
            if state and state != node_state['pane']:
                if state == 'dead' or (state == 'gone' and node_state['pane'] != 'dead'):
                    events.append(f'EVENT {node} pane-{state} {detail}')
                node_state['pane'] = state
                dirty = True
            menu = ''
            if state == 'alive':
                shot = tmux(entry, 'capture-pane', '-p', '-t', entry['tmux_pane_id'])
                found = find_menu(shot.stdout) if shot.returncode == 0 else None
                if found:
                    menu = found[0]
                    if menu != node_state['menu']:
                        events.append(f'EVENT {node} menu {found[1]}')
            if menu != node_state['menu']:
                node_state['menu'] = menu
                dirty = True

        size = status_path.stat().st_size if status_path.exists() else 0
        if size < base['status_offset']:
            base['status_offset'] = 0
        if size > base['status_offset']:
            with open(status_path, 'rb') as f:
                f.seek(base['status_offset'])
                chunk = f.read(size - base['status_offset'])
            whole = chunk[:chunk.rfind(b'\n') + 1]
            for raw in whole.splitlines():
                try:
                    rec = json.loads(raw)
                except ValueError:
                    continue
                if args.turn_end and rec.get('state') == 'turn_end' and rec.get('node_id') in children:
                    events.append(f"EVENT {rec['node_id']} turn-end {rec.get('task_id', '')} {rec.get('ts', '')}")
            base['status_offset'] += len(whole)
            dirty = True

        timed_out = args.timeout and now - started >= args.timeout
        if pending and (events or timed_out or now - pending_since >= args.debounce):
            events += [f'EVENT {node} log {text}' for node, text in pending]
            pending, pending_since = [], None
            for node, pos in read_pos.items():
                if node in base['nodes']:
                    base['nodes'][node]['log_offset'] = pos
        if events:
            emit(events)
        if events or dirty:
            write_json(base_path, base)
        if events and not args.follow:
            return 0
        if timed_out and not args.follow:
            emit([f'EVENT - timeout {args.timeout:g}s without events'])
            return 1
        time.sleep(args.interval)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
