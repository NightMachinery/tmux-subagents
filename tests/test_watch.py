"""Watcher tests: a scratch tmux server, a fake registry, inert panes; no API calls."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / 'skills/tmux-subagents/scripts/tmux-subagent-watch.sh'
FAST = ['--interval', '0.2']

CLAUDE_PERMISSION = '''\
 Bash command
   ls -la
 Do you want to proceed?
 ❯ 1. Yes
   2. Yes, and don't ask again for ls commands in this folder
   3. No, and tell Claude what to do differently (esc)

 Esc to cancel
'''
CLAUDE_TRUST = '''\
 Quick safety check: Is this a project you created or one you trust?
 ❯ No, exit
   Yes, I trust this folder
 Enter to confirm · Esc to cancel
'''
CODEX_TRUST = '''\
> You are in /scratch
  Do you trust the contents of this directory? Working with untrusted contents
› 1. Yes, continue
  2. No, quit
  Press enter to continue
'''
AGY_TRUST = '''\
Do you trust the contents of this project?
> Yes, I trust this folder
  No, exit
  ↑/↓ Navigate · enter Confirm
'''
# Not menus: a transcript quoting one, typed text in an input box, a busy footer.
NOT_MENUS = '''\
  ⎿ The menu cursor line looks like `❯ 1. Yes`, followed by `2. No`.
 Would you like me to go on?
────────────────────────────────────────
❯ 1. first item I am typing
  2. second item
────────────────────────────────────────
  ✻ Working… (esc to interrupt)
'''


@unittest.skipUnless(shutil.which('tmux'), 'tmux required')
class WatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='agent-watch-')
        self.root = Path(self.tmp.name)
        self.state = self.root / 'state'
        (self.state / 'tasks').mkdir(parents=True)
        self.label = 'agwatch-' + os.urandom(4).hex()
        self.env = dict(os.environ, TMUX_SUBAGENTS_STATE=str(self.state), LC_ALL='C.UTF-8')
        for key in ('TMUX', 'TMUX_PANE', 'TMUX_SUBAGENT_NODE'):
            self.env.pop(key, None)
        self.tmux('new-session', '-d', '-s', 'holder', 'sleep 600')
        self.tmux('set-option', '-g', 'remain-on-exit', 'on')  # before any pane can exit
        self.socket = self.tmux('display-message', '-p', '-t', 'holder', '#{socket_path}').stdout.strip()
        self.registry = {}
        self.fixtures = 0

    def tearDown(self):
        self.tmux('kill-server', check=False)
        self.tmp.cleanup()

    def tmux(self, *args, check=True):
        return subprocess.run(['tmux', '-L', self.label, '-f', '/dev/null', *args],
                              env=self.env, text=True, capture_output=True, check=check)

    def pane(self, screen=None, command=None):
        """A pane showing SCREEN (or running COMMAND) and then idling."""
        if screen is not None:
            self.fixtures += 1
            path = self.root / f'screen{self.fixtures}.txt'
            path.write_text(screen)
            command = f"cat '{path}'; sleep 600"
        return self.tmux('new-session', '-d', '-P', '-F', '#{pane_id}', '-x', '120', '-y', '40',
                         command or 'sleep 600').stdout.strip()

    def child(self, node, pane=None, parent='parent-a', created='2000-01-01T00:00:00'):
        task = 'task-' + node
        (self.state / 'tasks' / task).mkdir(exist_ok=True)
        self.registry[node] = dict(node_id=node, root_id='root-a', parent=parent, task_id=task,
                                   tmux_pane_id=pane or self.pane(), tmux_socket=self.socket, created=created)
        self.save()
        return self.state / 'tasks' / task

    def save(self):
        tmp = self.state / 'agents.json.tmp'
        tmp.write_text(json.dumps(self.registry))
        os.replace(tmp, self.state / 'agents.json')

    def watch(self, *args, timeout=None, stdout=subprocess.PIPE):
        extra = ['--timeout', str(timeout)] if timeout else []
        return subprocess.run([str(WATCH), *FAST, *extra, *args], env=self.env, text=True,
                              stdout=stdout, stderr=subprocess.PIPE, timeout=60)

    def start(self, *args):
        return subprocess.Popen([str(WATCH), *FAST, *args], env=self.env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def events(self, result):
        return [line.split(' ', 3)[1:] for line in result.stdout.splitlines()]

    def quiet(self, *args):
        """Asserts nothing new is reported within a short timeout."""
        result = self.watch(*args, timeout=1.5)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.events(result), [['-', 'timeout', '1.5s without events']])

    def test_pane_dead_and_gone_reported_once(self):
        self.child('dead', self.pane(command='exit 3'))
        self.child('gone', '%999')
        time.sleep(0.5)
        result = self.watch('--parent', 'parent-a')
        self.assertEqual(result.returncode, 0, result.stderr)
        kinds = sorted(tuple(e[:2]) for e in self.events(result))
        self.assertEqual(kinds, [('dead', 'pane-dead'), ('gone', 'pane-gone')])
        self.assertIn('exit 3', result.stdout)
        self.quiet('--parent', 'parent-a')

    def test_menus_detected_and_lookalikes_ignored(self):
        cases = dict(claude_perm=CLAUDE_PERMISSION, claude_trust=CLAUDE_TRUST, codex=CODEX_TRUST, agy=AGY_TRUST)
        for node, screen in cases.items():
            self.child(node, self.pane(screen), parent='menus')
        self.child('lookalike', self.pane(NOT_MENUS), parent='menus')
        time.sleep(0.5)
        result = self.watch('--parent', 'menus')
        self.assertEqual(result.returncode, 0, result.stderr)
        got = {e[0]: e[2] for e in self.events(result)}
        self.assertEqual(set(got), set(cases), result.stdout)
        self.assertTrue(all(e[1] == 'menu' for e in self.events(result)))
        self.assertIn('Do you want to proceed? | ❯ 1. Yes', got['claude_perm'])
        self.assertIn('› 1. Yes, continue', got['codex'])
        self.assertIn('> Yes, I trust this folder', got['agy'])
        self.quiet('--parent', 'menus')  # a menu still on screen is not reported twice

    def test_result_and_needs_input_without_replay(self):
        task = self.child('c1')
        self.quiet('--parent', 'parent-a')
        watcher = self.start('--parent', 'parent-a')
        time.sleep(0.6)
        (task / 'result.needs-input.md').write_text('question\n')
        out, err = watcher.communicate(timeout=30)
        self.assertEqual(watcher.returncode, 0, err)
        self.assertEqual(out.split()[1:3], ['c1', 'needs-input'])
        (task / 'result.needs-input.md').unlink()
        (task / 'result.md').write_text('done\n')
        result = self.watch('--parent', 'parent-a')
        self.assertEqual([e[:2] for e in self.events(result)], [['c1', 'result']])
        self.quiet('--parent', 'parent-a')
        (task / 'result.md').write_text('done, corrected\n')  # modified is an event too
        result = self.watch('--parent', 'parent-a')
        self.assertEqual([e[:2] for e in self.events(result)], [['c1', 'result']])

    def test_existing_history_is_baselined(self):
        task = self.child('old')
        (task / 'result.md').write_text('old result\n')
        (task / 'events.log').write_text('[t] old line\n')
        self.quiet('--parent', 'parent-a')

    def test_events_log_debounced_then_printed_together(self):
        task = self.child('c1')
        log = task / 'events.log'
        log.write_text('[t0] before the watcher\n')
        self.quiet('--parent', 'parent-a')
        watcher = self.start('--parent', 'parent-a', '--debounce', '3')
        time.sleep(0.6)
        began = time.monotonic()
        with open(log, 'a') as f:
            f.write('[t1] first\n')
        time.sleep(1)
        with open(log, 'a') as f:
            f.write('[t2] second\n[t3] partial')  # no newline yet: held back
        out, err = watcher.communicate(timeout=30)
        waited = time.monotonic() - began
        self.assertEqual(watcher.returncode, 0, err)
        self.assertGreater(waited, 2.5)
        self.assertEqual([l.split(' ', 3)[3] for l in out.splitlines()], ['[t1] first', '[t2] second'])
        with open(log, 'a') as f:
            f.write(' now whole\n')
        result = self.watch('--parent', 'parent-a', '--debounce', '0')
        self.assertEqual(self.events(result), [['c1', 'log', '[t3] partial now whole']])
        self.quiet('--parent', 'parent-a')

    def test_child_added_after_start(self):
        self.child('first')
        watcher = self.start('--parent', 'parent-a')
        time.sleep(1.2)  # the first cycle records its baseline
        created = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(time.time() + 1))
        task = self.child('second', created=created)
        (task / 'result.md').write_text('already done\n')
        out, err = watcher.communicate(timeout=30)
        self.assertEqual(watcher.returncode, 0, err)
        self.assertEqual(out.split()[1:3], ['second', 'result'])

    def test_turn_end_only_when_asked(self):
        self.child('c1')
        def turn_end(node):
            with open(self.state / 'status.jsonl', 'a') as f:
                f.write(json.dumps(dict(ts='t', task_id='task-' + node, node_id=node, state='turn_end')) + '\n')
        turn_end('c1')  # history, baselined on the first run
        self.quiet('--node', 'c1', '--turn-end')
        turn_end('c1')
        self.quiet('--node', 'c1')  # off by default
        turn_end('c1')
        turn_end('elsewhere')
        result = self.watch('--node', 'c1', '--turn-end')
        self.assertEqual([e[:2] for e in self.events(result)], [['c1', 'turn-end']])
        self.quiet('--node', 'c1', '--turn-end')

    def test_default_selection_is_own_children(self):
        self.child('mine', self.pane(command='exit 0'), parent='me')
        self.child('theirs', self.pane(command='exit 0'), parent='someone-else')
        time.sleep(0.5)
        self.env['TMUX_SUBAGENT_NODE'] = 'me'
        result = self.watch()
        self.assertEqual([e[:2] for e in self.events(result)], [['mine', 'pane-dead']])
        del self.env['TMUX_SUBAGENT_NODE']
        self.assertEqual(self.watch().returncode, 2)

    def test_empty_selection(self):
        self.child('c1')
        result = self.watch('--parent', 'nobody')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.events(result), [['-', 'NO-CHILDREN', 'parent=nobody']])

    def test_refuses_dev_null(self):
        self.child('c1')
        result = self.watch('--parent', 'parent-a', stdout=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 2)
        self.assertIn('/dev/null', result.stderr)

    def test_one_watcher_per_selection(self):
        self.child('c1')
        first = self.start('--parent', 'parent-a')
        time.sleep(0.6)
        second = self.watch('--parent', 'parent-a')
        first.kill()
        first.communicate()
        self.assertEqual(second.returncode, 3)
        self.assertIn('another watcher', second.stderr)


if __name__ == '__main__':
    unittest.main()
