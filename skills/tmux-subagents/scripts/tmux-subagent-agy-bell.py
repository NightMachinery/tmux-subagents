#!/usr/bin/env python3
"""Zero-token bell for an agy worker in tmux: wakes its operator on events.

agy's hooks report turn ends (tmux-subagent-agy-stop-hook.sh) but nothing
else: there is no permission-dialog or notification hook. This watches the
worker's pane instead and tells the operator when

  turn-end   the busy marker (`esc to cancel`) is gone for two polls, unless
             the Stop hook already reported this turn end;
  dialog     a permission or review dialog appears near the bottom of the pane,
             keyed by that whole bottom block, so a second dialog with the
             same wording but another path is a new one; while one stays
             open, a reminder every REMIND s says for how long;
  stall      the pane shows the busy marker but has not changed for STALL s
             (once per stall);
  keep-warm  the worker is busy, the operator has heard nothing for WARM s and
             (for a Paseo operator) is idle, within WARM_MAX s of the last
             real event; the ping keeps the operator's prompt cache warm;
  end        the pane exits or disappears; the bell then exits too.

Targets: `paseo:<agent-id>` sends with `paseo send ... --no-wait`, and
`log:<path>` appends one line to a task's events.log, which wakes a parent
running tmux-subagent-watch.sh. With a log target, menus the watcher already
reports as `menu` events are left to it.
"""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
BUSY = 'esc to cancel'
# Dialog wording seen in agy and generic CLI prompts. Matched only in the last
# few non-blank lines, so a transcript quoting one higher up does not count.
DIALOG = re.compile(r'(?i)allow once|always allow|allow this|allow access|deny access'
                    r'|^\s*(>\s*)?(\d+\.\s*)?(allow|deny|reject|approve)\b|do you want to'
                    r'|do you trust|\(y/n\)|\[y/n\]')
TAIL_DIALOG = 14
TAIL_REPORT = 15
TAIL_DIALOG_REPORT = 8
SPINNER = re.compile('[\u2800-\u28ff]')


def load_watch():
    spec = importlib.util.spec_from_file_location('tmux_subagent_watch', HERE / 'tmux-subagent-watch.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def state_root():
    return Path(os.environ.get('TMUX_SUBAGENTS_STATE', str(
        Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'tmux-subagents')))


def mark_key(socket_path, pane_id):
    """Shared with the Stop hook: <socket basename>-<pane number>."""
    raw = os.path.basename(socket_path) + '-' + pane_id.lstrip('%')
    return re.sub(r'[^A-Za-z0-9_.-]', '-', raw)


def nonblank(screen):
    return [l.rstrip() for l in screen.splitlines() if l.strip()]


def dialog_lines(screen):
    hits = [l for l in nonblank(screen)[-TAIL_DIALOG:] if DIALOG.search(l)]
    return '\n'.join(hits[-6:])


def dialog_key(lines):
    """The bottom block that identifies one dialog: two agy file-access dialogs
    share their wording and differ only in the path line. Spinner frames and
    the busy footer are left out, so an animation does not make it new."""
    return '\n'.join(SPINNER.sub('', l) for l in lines[-TAIL_DIALOG:] if BUSY not in l.lower())


def same(mtime, stamp):
    """A file mtime set from STAMP; filesystems round it."""
    return stamp is not None and abs(mtime - stamp) < 0.5


class Bell:
    """The detection state machine; pure, so tests feed it fake screens."""

    def __init__(self, stall=1200, warm=1500, warm_max=12600, remind=300, find_menu=None, now=0.0):
        self.stall, self.warm, self.warm_max, self.remind = stall, warm, warm_max, remind
        self.find_menu = find_menu      # set for a log target: the watcher reports these
        self.last_screen = None
        self.changed = now
        self.stall_sent = False
        self.busy = False
        self.idle_polls = 0
        self.dialog = ''                # key of the dialog on screen, '' when none
        self.dialog_first = self.dialog_sent = now
        self.last_real = now            # last event other than a keep-warm ping
        self.warm_at = None
        self.started = now              # the mark's mtime when the bell started
        self.busy_at = now

    def observe(self, screen, now, heard, operator_idle=lambda: True):
        """Events for one poll: a list of (kind, text).

        heard: when the operator last heard from the bell or the Stop hook (the
        mark file's mtime). operator_idle is only called when a ping is due.
        """
        events = []
        quiet_for = now - heard
        if heard > self.last_real + 0.5 and not same(heard, self.warm_at):
            self.last_real = heard  # the Stop hook spoke
        if screen != self.last_screen:
            self.last_screen = screen
            self.changed = now
            self.stall_sent = False
        lines = nonblank(screen)
        tail = '\n'.join(l[:220] for l in lines[-TAIL_REPORT:])
        if BUSY in screen.lower():
            self.busy = True
            self.busy_at = now
            self.idle_polls = 0
        elif self.busy:
            self.idle_polls += 1
            if self.idle_polls >= 2:  # one poll can catch a redraw between frames
                self.busy = False
                # The Stop hook touches the mark as the turn ends, around the
                # last busy frame; then it has already told the operator.
                if same(heard, self.started) or heard < self.busy_at - 5:
                    events.append(('turn-end', tail))
        found = dialog_lines(screen)
        if found and self.find_menu and self.find_menu(screen):
            found = ''
        bottom = '\n'.join(l[:220] for l in lines[-TAIL_DIALOG_REPORT:])
        if not found:
            self.dialog = ''
        elif dialog_key(lines) != self.dialog:
            self.dialog = dialog_key(lines)
            self.dialog_first = self.dialog_sent = now
            events.append(('dialog', bottom))
        elif self.remind and now - self.dialog_sent >= self.remind:
            self.dialog_sent = now
            events.append(('dialog-open', f'{int((now - self.dialog_first) // 60)}\n{bottom}'))
        if self.busy and not self.stall_sent and now - self.changed >= self.stall:
            self.stall_sent = True
            events.append(('stall', str(int((now - self.changed) // 60))))
        if events:
            self.last_real = now
        elif (self.warm and self.busy and quiet_for >= self.warm
                and now - self.last_real < self.warm_max and operator_idle()):
            self.warm_at = now
            events.append(('keep-warm', ''))
        return events


def message(kind, text, label):
    head = f'[agy-bell] {label}: '
    if kind == 'turn-end':
        return head + "the worker's turn ended. Last lines of its pane:\n" + text
    if kind == 'dialog':
        return head + 'a dialog seems to be waiting for you:\n' + text
    if kind == 'dialog-open':
        minutes, _, bottom = text.partition('\n')
        return head + f'the dialog is still open after {minutes} minutes:\n' + bottom
    if kind == 'stall':
        return head + f'busy, but the pane has not changed for {text} minutes; check whether it is stuck.'
    if kind == 'keep-warm':
        return head + 'keep-warm ping; the worker is still busy. Reply with one word and end your turn.'
    return head + text


class Target:
    def __init__(self, spec, log):
        kind, _, value = spec.partition(':')
        if kind not in ('paseo', 'log') or not value:
            raise ValueError('target must be paseo:<agent-id> or log:<path>')
        self.kind, self.value, self.log = kind, value, log

    def send(self, text):
        ok = False
        if self.kind == 'paseo':
            with open(self.log, 'a') as out:
                try:
                    ok = subprocess.run(['paseo', 'send', self.value, text, '--no-wait'],
                                        stdout=out, stderr=out).returncode == 0
                except OSError as error:  # paseo missing: log it and keep watching
                    out.write(f'paseo send failed: {error}\n')
        else:
            line = ' | '.join(nonblank(text))[:300]
            stamp = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())
            try:
                with open(self.value, 'a') as f:
                    f.write(f'[{stamp}] {line}\n')
                ok = True
            except OSError:
                pass
        with open(self.log, 'a') as out:
            out.write(f"{time.strftime('%H:%M:%S')} {'sent' if ok else 'FAILED'}: {text.splitlines()[0]}\n")
        return ok

    def idle(self):
        if self.kind != 'paseo':
            return True
        try:
            out = subprocess.run(['paseo', 'inspect', self.value, '--json'], capture_output=True, text=True)
            return json.loads(out.stdout).get('Status', '') == 'idle'
        except (OSError, ValueError, AttributeError):
            return False


def main():
    p = argparse.ArgumentParser(prog='tmux-subagent-agy-bell.sh', description=__doc__.split('\n\n')[0])
    p.add_argument('--node', help='registry node: supplies the pane, socket and default log target')
    p.add_argument('--pane', help='tmux target of the worker pane, such as %%12')
    p.add_argument('--socket', help='tmux socket path (default: the server tmux finds)')
    p.add_argument('--notify', default=os.environ.get('TMUX_SUBAGENT_AGY_NOTIFY', ''),
                   help='paseo:<agent-id> or log:<path> (default $TMUX_SUBAGENT_AGY_NOTIFY, '
                        "else the node's events.log)")
    p.add_argument('--label', help='name used in messages (default: the tmux session name)')
    env = os.environ.get
    p.add_argument('--poll', type=float, default=float(env('AGY_BELL_POLL', 5)))
    p.add_argument('--stall', type=float, default=float(env('AGY_BELL_STALL', 1200)))
    p.add_argument('--warm', type=float, default=float(env('AGY_BELL_WARM', 1500)), help='0 turns it off')
    p.add_argument('--warm-max', type=float, default=float(env('AGY_BELL_WARM_MAX', 12600)))
    p.add_argument('--remind', type=float, default=float(env('AGY_BELL_REMIND', 300)),
                   help='seconds between reminders of an open dialog; 0 turns them off')
    args = p.parse_args()

    root = state_root()
    pane, socket, task_dir = args.pane, args.socket, None
    if args.node:
        try:
            entry = json.loads((root / 'agents.json').read_text())[args.node]
        except (OSError, ValueError, KeyError):
            p.error('node not found in the registry: ' + args.node)
        pane = pane or entry.get('tmux_pane_id')
        socket = socket or entry.get('tmux_socket')
        if entry.get('task_dir'):
            task_dir = Path(entry['task_dir'])
        elif entry.get('task_id'):
            task_dir = root / 'tasks' / entry['task_id']
    if not pane:
        p.error('pass --pane or --node')
    notify = args.notify or (f'log:{task_dir}/events.log' if task_dir else '')
    if not notify:
        p.error('no target: pass --notify paseo:<id>|log:<path>, or a --node with a task')

    def tmux(*words):
        cmd = ['tmux', *(['-S', socket] if socket else []), *words]
        return subprocess.run(cmd, capture_output=True, text=True, errors='replace')

    info = tmux('display-message', '-p', '-t', pane, '#{pane_id}\t#{socket_path}\t#{session_name}').stdout
    parts = info.rstrip('\n').split('\t')
    if len(parts) != 3 or not parts[0].startswith('%'):
        p.error('pane not found: ' + pane)
    pane_id, socket_path, session = parts
    label = args.label or session
    bells = root / 'agy-bell'
    bells.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = mark_key(socket_path, pane_id)
    lock = open(bells / (key + '.lock'), 'a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print('tmux-subagent-agy-bell: another bell watches ' + pane_id, file=sys.stderr)
        return 3
    mark = bells / (key + '.mark')
    started = time.time()
    mark.touch()
    os.utime(mark, (started, started))
    try:
        target = Target(notify, bells / (key + '.log'))
    except ValueError as error:
        p.error(str(error))

    watch = load_watch() if target.kind == 'log' else None
    bell = Bell(args.stall, args.warm, args.warm_max, args.remind,
                find_menu=watch.find_menu if watch else None, now=started)
    while True:
        state = tmux('display-message', '-p', '-t', pane_id, '#{pane_id} #{pane_dead} #{pane_dead_status}')
        words = state.stdout.split()
        if state.returncode or not words or words[0] != pane_id:
            target.send(f'[agy-bell] {label}: the worker pane is gone.')
            return 0
        if words[1:2] == ['1']:
            target.send(f'[agy-bell] {label}: the worker exited (status {" ".join(words[2:]) or "?"}).')
            return 0
        shot = tmux('capture-pane', '-p', '-t', pane_id)
        now = time.time()
        for kind, text in bell.observe(shot.stdout, now, mark.stat().st_mtime, target.idle):
            if target.send(message(kind, text, label)):
                os.utime(mark, (now, now))
        time.sleep(args.poll)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
