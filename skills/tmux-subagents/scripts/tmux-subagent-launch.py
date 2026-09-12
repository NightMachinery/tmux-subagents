#!/usr/bin/env python3
"""Launch an inspectable agent with a persistent exact-conversation resume path."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent


class LaunchParser(argparse.ArgumentParser):
    def error(self, message):
        # Exit 2 is reserved for a tmux name collision: callers retry it.
        self.print_usage(sys.stderr)
        self.exit(64, self.prog + ': error: ' + message + '\n')


def tmux(*args, check=True):
    return subprocess.run(['tmux', *args], text=True, capture_output=True, check=check)


def write_json(path, data):
    fd, tmp = tempfile.mkstemp(prefix='.agents-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(data, out, indent=1)
            out.write('\n')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def launcher_token(command, requested=None):
    # Preserve shell source verbatim; identify one whole launcher token, never
    # a matching substring in a path, prompt or environment assignment.
    tokens = re.finditer(r"(?:[^\s\"']+|'[^']*'|\"(?:\\.|[^\"])*\")+", command)
    for token in tokens:
        try:
            words = shlex.split(token.group())
        except ValueError:
            continue
        if len(words) != 1:
            continue
        word = words[0]
        if requested:
            if word == requested:
                return word, token.end()
        elif word != 'env' and not re.match(r'[A-Za-z_][A-Za-z0-9_]*=', word):
            return word, token.end()
    return '', 0


def main():
    os.umask(0o077)
    p = LaunchParser(description=__doc__)
    p.add_argument('--task', default=os.environ.get('TMUX_SUBAGENT_TASK', ''))
    p.add_argument('--notify-chain', action='append', default=[])
    p.add_argument('--resume-command', required=True,
                   help='shell code calling agent-session-resume-exact with $AGENT_SESSION_ID and $AGENT_SESSION_CWD')
    p.add_argument('--provider', choices=['claude', 'codex', 'agy'])
    p.add_argument('--hook-launcher', help='exact launcher token in COMMAND for hook insertion')
    p.add_argument('--plugin', default=os.environ.get('AGENT_SESSION_PLUGIN', str(
        Path(os.environ.get('NIGHTDIR', str(Path.home() / 'scripts'))) /
        'zshlang/plugins/agent-session/agent-session.plugin.zsh')))
    p.add_argument('--lineage', default=os.environ.get('TMUX_SUBAGENT_LINEAGE', ''))
    p.add_argument('--run', default=os.environ.get('TMUX_SUBAGENT_RUN', ''))
    p.add_argument('name')
    p.add_argument('workdir')
    p.add_argument('command')
    args = p.parse_args()
    if not args.resume_command.strip():
        p.error("--resume-command must not be empty")
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', args.name):
        p.error('NAME must contain only letters, digits, underscores and hyphens')
    plugin = Path(args.plugin).expanduser().resolve()
    runtime = plugin.with_name('pane.py')
    if not plugin.is_file() or not runtime.is_file():
        p.error('agent-session plugin is missing; install it or set AGENT_SESSION_PLUGIN')
    cwd = str(Path(args.workdir).resolve())
    if not Path(cwd).is_dir():
        p.error('WORKDIR must be an existing directory')
    word, launcher_end = launcher_token(args.command, args.hook_launcher)
    providers = dict(claude='claude', **{'claude-m': 'claude', 'claude-work': 'claude',
        'codex': 'codex', 'codex-m': 'codex', 'agy': 'agy', 'antigravity': 'agy', 'antigravity-m': 'agy'})
    provider = args.provider or providers.get(Path(word).name)
    if not provider:
        p.error('unrecognized provider; pass --provider')
    if tmux('has-session', '-t', '=' + args.name, check=False).returncode == 0:
        print('collision: session ' + args.name + ' exists', file=sys.stderr)
        return 2
    state_root = Path(os.environ.get('TMUX_SUBAGENTS_STATE', str(
        Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'tmux-subagents'))).resolve()
    state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_root.chmod(0o700)
    runs = state_root / 'panes'
    runs.mkdir(mode=0o700, exist_ok=True)
    state = Path(tempfile.mkdtemp(prefix='pane-', dir=runs))
    hooks = []
    if provider == 'claude':
        capture = shlex.join(['python3', str(runtime), 'hook', str(state), provider])
        settings = {'hooks': {'SessionStart': [{'hooks': [{'type': 'command', 'command': capture}]}]}}
        if args.task:
            stop = shlex.join([str(HERE / 'tmux-subagent-status.sh'), args.task, args.name, 'turn_end', '-'])
            settings['hooks']['Stop'] = [{'hooks': [{'type': 'command', 'command': stop}]}]
        hooks = ['--settings', json.dumps(settings, separators=(',', ':'))]
    elif provider == 'codex':
        notify = [str(HERE / 'tmux-subagent-codex-notify.sh'), args.task, args.name, *args.notify_chain]
        hooks = ['-c', 'notify=' + json.dumps(notify, separators=(',', ':'))]
    initial = args.command
    if hooks:
        if not word or not launcher_end:
            p.error('cannot locate launcher for hook wiring; pass --hook-launcher')
        at = launcher_end
        initial = initial[:at] + ' ' + shlex.join(hooks) + initial[at:]
    environment = {key: os.environ.get(key) for key in (
        'CLAUDE_CONFIG_DIR', 'CODEX_HOME', 'TMUX_SUBAGENT_PARENT', 'TMUX_SUBAGENT_ROOT',
        'TMUX_SUBAGENT_LINEAGE', 'TMUX_SUBAGENT_RUN')}
    environment.update(TMUX_SUBAGENTS_STATE=str(state_root), AGENT_SESSION_PLUGIN=str(plugin),
                       TMUX_SUBAGENT_TASK=args.task, TMUX_SUBAGENT_NODE=args.name,
                       TMUX_SUBAGENT_LINEAGE=args.lineage, TMUX_SUBAGENT_RUN=args.run)
    write_json(state / 'launch.json', dict(provider=provider, cwd=cwd, initial=initial,
                                         resume=args.resume_command, environment=environment))
    write_json(state / 'hooks.json', hooks)
    made = tmux('new-session', '-d', '-P', '-F', '#{session_id} #{pane_id}', '-s', args.name,
                '-c', cwd, 'sh', '-c', 'exec sleep 2147483647', check=False)
    if made.returncode:
        if tmux('has-session', '-t', '=' + args.name, check=False).returncode == 0:
            print('collision: session ' + args.name + ' exists', file=sys.stderr)
            return 2
        raise RuntimeError(made.stderr.strip())
    sid, pane = made.stdout.strip().split()
    tmux('set-option', '-t', sid, 'remain-on-exit', 'on')
    tmux('set-option', '-t', sid, 'allow-rename', 'off')
    tmux('set-option', '-p', '-t', pane, '@agent_session_state', str(state))
    sock = tmux('display-message', '-p', '-t', pane, '#{socket_path}').stdout.strip()
    entry = dict(node_id=args.name, root_id=os.environ.get('TMUX_SUBAGENT_ROOT') or args.name,
                 parent=os.environ.get('TMUX_SUBAGENT_PARENT', ''), task_id=args.task,
                 lineage=args.lineage, run=args.run, provider=provider,
                 tmux_session_id=sid, tmux_pane_id=pane, tmux_socket=sock, workdir=cwd,
                 resume_state=str(state), created=time.strftime('%Y-%m-%dT%H:%M:%S'),
                 process_state='running', task_outcome='unknown')
    registered = True
    try:
        with open(state_root / 'agents.json.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            reg = state_root / 'agents.json'
            txt = reg.read_text().strip() if reg.exists() else ''
            data = json.loads(txt) if txt else {}
            data[args.name] = entry
            write_json(reg, data)
    except (OSError, ValueError) as error:
        registered = False
        print('registration failed: ' + str(error), file=sys.stderr)
    tmux('respawn-pane', '-k', '-t', pane, '-c', cwd,
         'python3', str(runtime), 'run', str(state), str(plugin))
    print(args.name, sid, pane)
    if not registered:
        print('session is running and was left open; register it or close it explicitly', file=sys.stderr)
        return 3
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print('launch failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
