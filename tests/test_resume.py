"""Behavior tests using fake CLIs and a private tmux socket; no API calls."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/tmux-subagents/scripts'
PLUGIN = Path(os.environ.get('AGENT_SESSION_PLUGIN', str(
    Path.home() / 'scripts/zshlang/plugins/agent-session/agent-session.plugin.zsh')))
IDENT = '12345678-1234-1234-1234-123456789abc'


@unittest.skipUnless(shutil.which('tmux') and PLUGIN.exists(), 'tmux and agent-session plugin required')
class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='agent-resume-')
        self.root = Path(self.tmp.name)
        self.cwd = self.root / 'project with quotes \' and $dollars'
        self.cwd.mkdir()
        self.home = self.root / 'home'
        self.home.mkdir()
        (self.home / ".zshrc").write_text("# Deliberately empty standalone setup.\n")
        self.socket = self.root / 'tmux.sock'
        self.env = dict(os.environ, HOME=str(self.home), ZDOTDIR=str(self.home),
                        TMUX=f'{self.socket},0,0', TMUX_SUBAGENTS_STATE=str(self.root / 'state'),
                        AGENT_SESSION_PLUGIN=str(PLUGIN), TEST_LOG=str(self.root / 'calls.jsonl'),
                        CLAUDE_CONFIG_DIR=str(self.root / 'profile with spaces'),
                        CODEX_HOME=str(self.root / 'codex profile'))
        for key in ('TMUX_PANE', 'TMUX_SUBAGENT_TASK', 'NIGHTDIR', 'AGENT_SESSION_STATE'):
            self.env.pop(key, None)
        self.tmux('new-session', '-d', '-s', 'holder')
        self.fake = self.root / 'fake-agent'
        self.fake.write_text('''#!/usr/bin/env python3
import json, os, subprocess, sys, time
from pathlib import Path
provider = os.environ['TEST_PROVIDER']
ident = os.environ.get('TEST_ID', '12345678-1234-1234-1234-123456789abc')
key = dict(claude='CLAUDE_CODE_SESSION_ID', codex='CODEX_THREAD_ID', agy='ANTIGRAVITY_CONVERSATION_ID')[provider]
env = dict(os.environ, **{key: ident})
if not os.environ.get('TEST_NO_ID'):
    subprocess.run([os.environ['TEST_REGISTER'], provider], env=env, check=True)
with open(os.environ['TEST_LOG'], 'a') as log:
    log.write(json.dumps(dict(argv=sys.argv[1:], cwd=os.getcwd(), profile=os.environ.get('CLAUDE_CONFIG_DIR'), codex_home=os.environ.get('CODEX_HOME'))) + '\\n')
if os.environ.get('TEST_BUSY'):
    time.sleep(60)
''')
        self.fake.chmod(0o700)
        self.env['TEST_REGISTER'] = str(SCRIPTS / 'tmux-subagent-register.sh')

    def tearDown(self):
        self.tmux('kill-server', check=False)
        self.tmp.cleanup()

    def tmux(self, *args, check=True):
        return subprocess.run(['tmux', '-S', str(self.socket), '-f', '/dev/null', *args],
                              env=self.env, text=True, capture_output=True, check=check)

    def wait(self, fn):
        for _ in range(100):
            value = fn()
            if value:
                return value
            time.sleep(.1)
        self.fail('timed out waiting for pane state')

    def rows(self):
        p = Path(self.env['TEST_LOG'])
        return [json.loads(row) for row in p.read_text().splitlines()] if p.exists() else []

    def launch(self, provider='claude', busy=False, no_id=False):
        self.env.update(TEST_PROVIDER=provider)
        if busy:
            self.env['TEST_BUSY'] = '1'
        if no_id:
            self.env['TEST_NO_ID'] = '1'
        # TEST_* is inherited by the private server only if explicitly passed to the pane.
        prefix = ' '.join(k + '=' + shlex.quote(v) for k, v in self.env.items() if k.startswith('TEST_'))
        initial = prefix + ' ' + shlex.quote(str(self.fake)) + ' --model demo initial-prompt'
        resume = prefix + ' agent-session-resume-exact ' + provider + ' "$AGENT_SESSION_ID" "$AGENT_SESSION_CWD" ' + shlex.quote(str(self.fake)) + ' --model demo'
        cmd = [str(SCRIPTS / 'tmux-subagent-launch.sh'), '--provider', provider,
               '--hook-launcher', str(self.fake), '--resume-command', resume,
               '--task', 'test-task', '--lineage', 'root-child', '--run', 'test-run',
               'ag--demo--review-parser--' + provider + '--abcdef', str(self.cwd), initial]
        result = subprocess.run(cmd, env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        name, sid, pane = result.stdout.strip().split()
        self.wait(lambda: len(self.rows()) == 1)
        return cmd, name, sid, pane

    def dead(self, pane):
        return self.tmux('display-message', '-p', '-t', pane, '#{pane_dead}').stdout.strip() == '1'

    def test_provider_resume_and_repeated_restart(self):
        for provider, verb in [('claude', '--resume'), ('codex', 'resume'), ('agy', '--conversation')]:
            with self.subTest(provider=provider):
                # Separate files/session names keep each provider's assertions independent.
                self.env['TEST_LOG'] = str(self.root / (provider + '.jsonl'))
                _, name, sid, pane = self.launch(provider)
                self.wait(lambda: self.dead(pane))
                for count in (2, 3):
                    self.tmux('respawn-pane', '-k', '-t', pane)
                    self.wait(lambda: len(self.rows()) == count)
                    self.wait(lambda: self.dead(pane))
                    row = self.rows()[-1]
                    self.assertEqual(row['argv'][:2], [verb, IDENT])
                    self.assertNotIn('initial-prompt', row['argv'])
                    self.assertEqual(row['cwd'], str(self.cwd.resolve()))
                    self.assertEqual(row['profile'], self.env['CLAUDE_CONFIG_DIR'])
                    self.assertEqual(row['codex_home'], self.env['CODEX_HOME'])
                    if provider == 'claude':
                        self.assertIn('--settings', row['argv'])
                    if provider == 'codex':
                        self.assertTrue(any(x.startswith('notify=') for x in row['argv']))
                registry = json.loads((self.root / 'state/agents.json').read_text())
                self.assertEqual(registry[name]['lineage'], 'root-child')
                self.assertEqual(registry[name]['tmux_pane_id'], pane)
                state = Path(registry[name]['resume_state'])
                self.assertEqual((state / 'launch.json').stat().st_mode & 0o777, 0o600)
                self.assertEqual(json.loads((state / 'identity.json').read_text())['id'], IDENT)

    def test_running_restart(self):
        _, _, _, pane = self.launch('codex', busy=True)
        self.assertFalse(self.dead(pane))
        self.tmux('respawn-pane', '-k', '-t', pane)
        self.wait(lambda: len(self.rows()) == 2)
        self.assertEqual(self.rows()[-1]['argv'][:2], ['resume', IDENT])

    def test_missing_identity_does_not_relaunch(self):
        _, _, _, pane = self.launch(no_id=True)
        self.wait(lambda: self.dead(pane))
        self.tmux('respawn-pane', '-k', '-t', pane)
        self.wait(lambda: self.dead(pane))
        self.assertEqual(len(self.rows()), 1)
        output = self.tmux('capture-pane', '-p', '-t', pane).stdout
        self.assertIn('identity not recorded', output)

    def test_collision_leaves_existing_session(self):
        cmd, _, sid, pane = self.launch()
        result = subprocess.run(cmd, env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(self.tmux('display-message', '-p', '-t', pane, '#{session_id}').stdout.strip(), sid)
        self.assertEqual(len(self.rows()), 1)

    def test_hook_identity_and_notify_chain(self):
        _, name, _, pane = self.launch('codex', no_id=True)
        self.wait(lambda: self.dead(pane))
        state = json.loads((self.root / 'state/agents.json').read_text())[name]['resume_state']
        payload = json.dumps({'last-assistant-message': 'x' * 3000, 'thread-id': IDENT})
        chain_file = self.root / 'notify-payload.json'
        code = 'import pathlib,sys; pathlib.Path(' + repr(str(chain_file)) + ').write_text(sys.argv[1])'
        import sys
        result = subprocess.run([str(SCRIPTS / 'tmux-subagent-codex-notify.sh'), 'test-task', name,
                                 sys.executable, '-c', code, payload],
                                env=dict(self.env, AGENT_SESSION_STATE=state), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(chain_file.read_text(), payload)
        self.assertEqual(json.loads((Path(state) / 'identity.json').read_text())['id'], IDENT)
        self.tmux('respawn-pane', '-k', '-t', pane)
        self.wait(lambda: len(self.rows()) == 2)
        self.assertEqual(self.rows()[-1]['argv'][:2], ['resume', IDENT])

    def test_done_report_resumes_managed_settings(self):
        scripts_root = PLUGIN.parents[3]
        done_module = scripts_root / 'zshlang/auto-load/others/agent-done.zsh'
        session_module = scripts_root / 'zshlang/auto-load/others/agent-session.zsh'
        basic = scripts_root / 'zshlang/basic/basic.plugin.zsh'
        if not done_module.exists():
            self.skipTest('local /done integration is not installed')
        _, _, _, pane = self.launch('codex')
        self.wait(lambda: self.dead(pane))
        report = self.root / 'finished report.txt'
        report.write_text('Completed fake task.\n')
        transcript = self.root / (IDENT + '.jsonl')
        transcript.write_text('{}\n')
        pane_script = self.root / 'finished report.pane.sh'
        command = 'source "$1"; function aliasfn { return 0; }; function assert-args { local v; for v in "$@"; do [[ -n ${(P)v} ]] || return 1; done; }; source "$2"; h-agent-done-pane-script "$3" "$4" "$5" "$6"'
        result = subprocess.run(['zsh', '-f', '-c', command, 'test', str(basic), str(done_module),
                                 str(report), str(transcript), str(self.cwd), str(pane_script)],
                                env=dict(self.env, TMUX_PANE=pane), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('export AGENT_SESSION_REUSE_PANE=', pane_script.read_text())
        # Use the actual local resume wrapper, with metadata discovery stubbed
        # for the fake transcript. No personal providers or accounts are loaded.
        source = session_module.read_text()
        wrapper = source[source.index('function h-agent-session-resume-run {'):source.index('function agent-session-resume {')]
        startup = ('source ' + shlex.quote(str(basic)) + '\nsource ' + shlex.quote(str(PLUGIN)) + '\n' + wrapper +
                   '\nfunction assert-args { local v; for v in "$@"; do [[ -n ${(P)v} ]] || return 1; done; }\n' +
                   'function h-agent-session-live-list { return 0; }\n' +
                   'function h-agent-session-agent-of { print -r -- codex; }\n' +
                   'function h-agent-session-call { print -r -- ' + IDENT + '; }\n' +
                   'function agent-session-resume { h-agent-session-resume-run "$1" false; }\n')
        (self.home / '.zshrc').write_text(startup)
        self.tmux('respawn-pane', '-k', '-t', pane, 'sh', str(pane_script))
        self.wait(lambda: self.dead(pane))
        self.assertIn('Completed fake task', self.tmux('capture-pane', '-p', '-t', pane).stdout)
        self.assertEqual(len(self.rows()), 1)
        self.tmux('respawn-pane', '-k', '-t', pane)
        self.wait(lambda: len(self.rows()) == 2)
        self.assertEqual(self.rows()[-1]['argv'][:2], ['resume', IDENT])
        self.assertIn('--model', self.rows()[-1]['argv'])
        self.assertTrue(any(x.startswith('notify=') for x in self.rows()[-1]['argv']))

    def test_process_lock_prevents_duplicate(self):
        import fcntl
        _, name, _, pane = self.launch()
        self.wait(lambda: self.dead(pane))
        registry = json.loads((self.root / 'state/agents.json').read_text())
        state = Path(registry[name]['resume_state'])
        with open(state / 'process.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self.tmux('respawn-pane', '-k', '-t', pane)
            self.wait(lambda: self.dead(pane))
            self.assertEqual(len(self.rows()), 1)
            self.assertIn('refusing a duplicate', self.tmux('capture-pane', '-p', '-t', pane).stdout)
        self.tmux('respawn-pane', '-k', '-t', pane)
        self.wait(lambda: len(self.rows()) == 2)

    def test_identity_cannot_change(self):
        _, name, _, _ = self.launch()
        registry = json.loads((self.root / 'state/agents.json').read_text())
        result = subprocess.run(['python3', str(PLUGIN.with_name('pane.py')), 'identity',
                                 registry[name]['resume_state'], 'claude', '87654321-4321-4321-4321-cba987654321', ''],
                                text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('another ID', result.stderr)


@unittest.skipUnless(PLUGIN.exists(), 'agent-session plugin required')
class PluginTests(unittest.TestCase):
    def test_clean_shell_repeat_source_and_exact_id(self):
        command = ('source "$1" && source "$1" || exit; '
                   'function fake-launcher { print -r -- "$PWD"; print -rl -- "$@"; }; '
                   'agent-session-resume-exact codex "$2" /tmp fake-launcher --model "demo model"')
        result = subprocess.run(['zsh', '-f', '-c', command, 'test', str(PLUGIN), IDENT],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = result.stdout.splitlines()
        self.assertEqual(Path(rows[0]).resolve(), Path('/tmp').resolve())
        self.assertEqual(rows[1:], ['resume', IDENT, '--model', 'demo model'])
        result = subprocess.run(['zsh', '-f', '-c', command, 'test', str(PLUGIN), 'most-recent'],
                                text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')


class NameTests(unittest.TestCase):
    def test_readable_unique_names(self):
        cmd = [str(SCRIPTS / 'tmux-subagent-name.sh'), 'Demo', 'Review parser!', 'Claude.Opus']
        names = [subprocess.check_output(cmd, text=True).strip() for _ in range(2)]
        self.assertRegex(names[0], r'^ag--demo--review-parser--claude-opus--[0-9a-f]{6}$')
        self.assertNotEqual(*names)


if __name__ == '__main__':
    unittest.main()
