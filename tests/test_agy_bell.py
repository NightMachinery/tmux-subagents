"""agy operator helpers: the bell's detection with fake screens, the Stop hook,
the throwaway profile and a scratch tmux server; no agy and no API calls."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/tmux-subagents/scripts'


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bell_mod = load('tmux-subagent-agy-bell')
watch_mod = load('tmux-subagent-watch')

BUSY = '''\
  Reading web/src/lib/tips.ts
  Editing web/src/lib/tips.ts
  ⠋ Working (12s · esc to cancel)
'''
IDLE = '''\
  Edited web/src/lib/tips.ts
  Done: the button now hides tips.
 > Type a message
'''
AGY_PERMISSION = '''\
  Read file outside workspace: ~/notes/learnings.md
  Reason: outside workspace
  1. Yes, allow access
  2. Yes, and always allow non-workspace access
  3. No, deny access
'''
AGY_TRUST = '''\
Do you trust the contents of this project?
> Yes, I trust this folder
  No, exit
  ↑/↓ Navigate · enter Confirm
'''
# A transcript line far above the bottom that quotes a dialog does not count.
QUOTED_HIGH = 'Allow once is what the old CLI said.\n' + '\n'.join(f'line {i}' for i in range(20)) + '\n'


class BellDetection(unittest.TestCase):
    def bell(self, **kw):
        kw.setdefault('now', 0.0)
        return bell_mod.Bell(**kw)

    def test_turn_end_after_two_polls_without_busy_marker(self):
        b = self.bell()
        self.assertEqual(b.observe(BUSY, 5, 0), [])
        self.assertEqual(b.observe(IDLE, 10, 0), [])   # one poll can be a redraw
        events = b.observe(IDLE, 15, 0)
        self.assertEqual([k for k, _ in events], ['turn-end'])
        self.assertIn('Done: the button now hides tips.', events[0][1])
        self.assertEqual(b.observe(IDLE, 20, 0), [])    # reported once

    def test_flicker_is_not_a_turn_end(self):
        b = self.bell()
        b.observe(BUSY, 5, 0)
        b.observe(IDLE, 10, 0)
        b.observe(BUSY, 15, 0)
        self.assertEqual(b.observe(IDLE, 20, 0), [])

    def test_no_turn_end_before_the_worker_was_busy(self):
        b = self.bell()
        self.assertEqual(b.observe(IDLE, 5, 0) + b.observe(IDLE, 10, 0), [])

    def test_stop_hook_report_suppresses_duplicate_turn_end(self):
        b = self.bell()
        b.observe(BUSY, 100, 0)
        b.observe(IDLE, 105, 0)
        self.assertEqual(b.observe(IDLE, 110, 104), [])  # the hook touched the mark at 104

    def test_dialogs_reported_once_each(self):
        b = self.bell()
        events = b.observe(AGY_PERMISSION, 5, 0)
        self.assertEqual([k for k, _ in events], ['dialog'])
        self.assertIn('1. Yes, allow access', events[0][1])
        self.assertIn('3. No, deny access', events[0][1])
        self.assertEqual(b.observe(AGY_PERMISSION, 10, 0), [])
        self.assertEqual(b.observe(IDLE, 15, 0), [])
        self.assertEqual([k for k, _ in b.observe(AGY_PERMISSION, 20, 0)], ['dialog'])  # a new one

    def test_same_wording_other_path_is_a_new_dialog(self):
        def file_access(path):
            return ('  Reading the project files\n File access\n Allow access to this file?\n'
                    f'   Read: {path}\n > 1. Yes, allow access\n   2. No, deny access\n')
        b = self.bell()
        first = b.observe(file_access('~/repo/SKILL.md'), 5, 0)
        self.assertEqual([k for k, _ in first], ['dialog'])
        self.assertIn('Read: ~/repo/SKILL.md', first[0][1])
        second = b.observe(file_access('~/state/agents.json'), 10, 0)  # answered; the next one is up
        self.assertEqual([k for k, _ in second], ['dialog'])
        self.assertIn('Read: ~/state/agents.json', second[0][1])
        self.assertEqual(b.observe(file_access('~/state/agents.json'), 15, 0), [])

    def test_open_dialog_reminders_until_it_closes(self):
        b = self.bell(remind=300, warm=0, stall=10**9)
        self.assertEqual([k for k, _ in b.observe(AGY_PERMISSION, 0, 0)], ['dialog'])
        self.assertEqual(b.observe(AGY_PERMISSION, 299, 0), [])
        events = b.observe(AGY_PERMISSION, 300, 0)
        self.assertEqual([k for k, _ in events], ['dialog-open'])
        text = bell_mod.message(*events[0], 'w')
        self.assertIn('still open after 5 minutes', text)
        self.assertIn('3. No, deny access', text)
        self.assertEqual(b.observe(AGY_PERMISSION, 450, 0), [])
        events = b.observe(AGY_PERMISSION, 600, 0)
        self.assertIn('after 10 minutes', bell_mod.message(*events[0], 'w'))
        self.assertEqual(b.observe(IDLE, 700, 0), [])     # closed
        self.assertEqual(b.observe(IDLE, 1300, 0), [])    # no reminders after it closed
        off = self.bell(remind=0)
        off.observe(AGY_PERMISSION, 0, 0)
        self.assertEqual(off.observe(AGY_PERMISSION, 10**5, 0), [])

    def test_spinner_does_not_make_a_dialog_new(self):
        b = self.bell()
        b.observe(AGY_PERMISSION + '⠋ Working (3s · esc to cancel)\n', 5, 0)
        self.assertEqual(b.observe(AGY_PERMISSION + '⠙ Working (8s · esc to cancel)\n', 10, 0), [])

    def test_trust_and_yes_no_prompts(self):
        for screen in (AGY_TRUST, 'Overwrite review.md? (y/n)\n', 'Do you want to run this command?\n'):
            self.assertEqual([k for k, _ in self.bell().observe(screen, 5, 0)], ['dialog'], screen)

    def test_lookalikes_are_not_dialogs(self):
        for screen in (BUSY, IDLE, QUOTED_HIGH, 'The allowance logic is fine.\n'):
            self.assertEqual(self.bell().observe(screen, 5, 0), [], screen)

    def test_log_target_leaves_watcher_menus_to_the_watcher(self):
        b = self.bell(find_menu=watch_mod.find_menu)
        self.assertEqual(b.observe(AGY_TRUST, 5, 0), [])  # the watcher reports it as `menu`
        events = b.observe(AGY_PERMISSION, 10, 0)          # no footer: only the bell sees it
        self.assertEqual([k for k, _ in events], ['dialog'])

    def test_stall_only_while_busy_and_once(self):
        b = self.bell(stall=60, warm=0)
        b.observe(BUSY, 0, 0)
        self.assertEqual(b.observe(BUSY, 59, 0), [])
        events = b.observe(BUSY, 61, 0)
        self.assertEqual(events, [('stall', '1')])
        self.assertEqual(b.observe(BUSY, 200, 0), [])
        b.observe(BUSY + 'more\n', 210, 0)                 # a change re-arms it
        self.assertEqual(b.observe(BUSY + 'more\n', 271, 0), [('stall', '1')])
        idle = self.bell(stall=60, warm=0)
        idle.observe(IDLE, 0, 0)
        self.assertEqual(idle.observe(IDLE, 500, 0), [])  # idle and waiting is not stuck

    def test_keep_warm_gating(self):
        def busy_bell(**kw):
            b = self.bell(stall=10**9, **kw)
            b.observe(BUSY, 0, 0)
            return b
        b = busy_bell(warm=100, warm_max=1000)
        self.assertEqual(b.observe(BUSY, 99, 0), [])
        self.assertEqual(b.observe(BUSY, 100, 0), [('keep-warm', '')])
        self.assertEqual(b.observe(BUSY, 150, 100), [])    # the ping reset the quiet time
        self.assertEqual(b.observe(BUSY, 200, 100), [('keep-warm', '')])
        asked = []
        b = busy_bell(warm=100)
        self.assertEqual(b.observe(BUSY, 100, 0, lambda: asked.append(1) or False), [])
        self.assertEqual(asked, [1])                       # a busy operator is not pinged
        b = busy_bell(warm=0)
        self.assertEqual(b.observe(BUSY, 10**6, 0), [])     # 0 turns it off
        b = busy_bell(warm=100, warm_max=250)
        self.assertEqual(b.observe(BUSY, 200, 0), [('keep-warm', '')])
        self.assertEqual(b.observe(BUSY, 300, 200), [])    # past WARM_MAX since a real event
        self.assertEqual(b.observe(BUSY, 400, 350), [])    # the hook spoke at 350: real again
        self.assertEqual(b.observe(BUSY, 450, 350), [('keep-warm', '')])
        b = self.bell(warm=100)
        b.observe(IDLE, 0, 0)
        self.assertEqual(b.observe(IDLE, 500, 0), [])      # an idle worker needs no warm operator


@unittest.skipUnless(shutil.which('tmux'), 'tmux required')
class BellEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='agy-bell-')
        self.root = Path(self.tmp.name)
        self.state = self.root / 'state'
        self.state.mkdir()
        self.label = 'agybell-' + os.urandom(4).hex()
        self.env = dict(os.environ, TMUX_SUBAGENTS_STATE=str(self.state), LC_ALL='C.UTF-8')
        for key in ('TMUX', 'TMUX_PANE', 'TMUX_SUBAGENT_AGY_NOTIFY', 'TMUX_SUBAGENT_TASK',
                    'TMUX_SUBAGENT_NODE'):
            self.env.pop(key, None)
        self.tmux('new-session', '-d', '-s', 'holder', 'sleep 600')
        self.tmux('set-option', '-g', 'remain-on-exit', 'on')
        self.socket = self.tmux('display-message', '-p', '-t', 'holder', '#{socket_path}').stdout.strip()

    def tearDown(self):
        self.tmux('kill-server', check=False)
        self.tmp.cleanup()

    def tmux(self, *args, check=True):
        return subprocess.run(['tmux', '-L', self.label, '-f', '/dev/null', *args],
                              env=self.env, text=True, capture_output=True, check=check)

    def test_turn_end_then_exit_reach_the_events_log(self):
        script = self.root / 'worker.sh'
        script.write_text("printf 'Working (esc to cancel)\\n'; sleep 2; clear; printf 'All done.\\n'; "
                          "sleep 3; exit 4\n")
        pane = self.tmux('new-session', '-d', '-P', '-F', '#{pane_id}', '-s', 'worker',
                         f"sh '{script}'").stdout.strip()
        log = self.root / 'events.log'
        bell = subprocess.run([str(SCRIPTS / 'tmux-subagent-agy-bell.sh'), '--pane', pane,
                               '--socket', self.socket, '--notify', f'log:{log}', '--poll', '0.3'],
                              env=self.env, text=True, capture_output=True, timeout=60)
        self.assertEqual(bell.returncode, 0, bell.stderr)
        lines = log.read_text().splitlines()
        self.assertEqual(len(lines), 2, lines)
        self.assertIn("worker: the worker's turn ended", lines[0])
        self.assertIn('All done.', lines[0])
        self.assertIn('the worker exited (status 4)', lines[1])

    def test_stop_hook_reports_and_marks(self):
        pane = self.tmux('new-session', '-d', '-P', '-F', '#{pane_id}', '-s', 'agyw',
                         "printf 'Finished the step.\\n'; sleep 600").stdout.strip()
        (self.state / 'agy-bell').mkdir()
        log = self.root / 'events.log'
        env = dict(self.env, TMUX=f'{self.socket},1,0', TMUX_PANE=pane,
                   TMUX_SUBAGENT_AGY_NOTIFY=f'log:{log}', TMUX_SUBAGENT_TASK='t1', TMUX_SUBAGENT_NODE='n1')
        time.sleep(0.3)
        began = time.monotonic()
        hook = subprocess.run(['sh', str(SCRIPTS / 'tmux-subagent-agy-stop-hook.sh')], env=env,
                              input='{"hook":"Stop"}', text=True, capture_output=True, timeout=10)
        self.assertLess(time.monotonic() - began, 3)
        self.assertEqual(hook.stdout, '{}\n')
        self.assertRegex(log.read_text(), r'^\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d UTC\] \[agy-bell\] agyw: turn ended\n$')
        mark = self.state / 'agy-bell' / (bell_mod.mark_key(self.socket, pane) + '.mark')
        self.assertTrue(mark.exists(), list((self.state / 'agy-bell').iterdir()))
        status = self.state / 'status.jsonl'
        for _ in range(50):
            if status.exists() and status.read_text():
                break
            time.sleep(0.1)
        row = json.loads(status.read_text().splitlines()[-1])
        self.assertEqual((row['task_id'], row['node_id'], row['state']), ('t1', 'n1', 'turn_end'))

    def test_stop_hook_without_target_still_answers(self):
        hook = subprocess.run(['sh', str(SCRIPTS / 'tmux-subagent-agy-stop-hook.sh')], env=self.env,
                              input='{}', text=True, capture_output=True, timeout=10)
        self.assertEqual((hook.returncode, hook.stdout), (0, '{}\n'))


class PaseoTarget(unittest.TestCase):
    def test_send_and_idle_use_paseo(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            calls = tmp / 'calls'
            fake = tmp / 'paseo'
            fake.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "' + str(calls) + '"\n'
                            '[ "$1" = inspect ] && printf \'{"Status":"idle"}\'\nexit 0\n')
            fake.chmod(0o700)
            old = os.environ['PATH']
            os.environ['PATH'] = f'{tmp}:{old}'
            try:
                target = bell_mod.Target('paseo:agent-1', tmp / 'bell.log')
                self.assertTrue(target.send('[agy-bell] w: hello\nsecond line'))
                self.assertTrue(target.idle())
            finally:
                os.environ['PATH'] = old
            text = calls.read_text()
            self.assertIn('send agent-1 [agy-bell] w: hello', text)
            self.assertIn('--no-wait', text)
            self.assertIn('inspect agent-1 --json', text)
            with self.assertRaises(ValueError):
                bell_mod.Target('mail:someone', tmp / 'bell.log')


class Profile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='agy-profile-')
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        (self.source / 'antigravity-cli').mkdir(parents=True)
        (self.source / 'antigravity-cli/antigravity-oauth-token').write_text('not a real token\n')
        (self.source / 'antigravity-cli/jetski_state.pbtxt').write_text('onboarded: true\n')
        (self.source / 'antigravity-cli/cache').mkdir()
        (self.source / 'antigravity-cli/cache/onboarding.json').write_text('{"onboardingComplete": true}\n')
        (self.source / 'antigravity-cli/settings.json').write_text('{"statusLine": "user"}\n')
        self.ws = self.root / 'work space'
        self.ws.mkdir()
        self.profile = self.root / 'profile'

    def tearDown(self):
        self.tmp.cleanup()

    def run_helper(self, *args):
        return subprocess.run([str(SCRIPTS / 'tmux-subagent-agy-profile.sh'), *map(str, args)],
                              text=True, capture_output=True)

    def test_create_rerun_and_destroy(self):
        made = self.run_helper('create', self.profile, '--source', self.source, '--workspace', self.ws)
        self.assertEqual(made.returncode, 0, made.stderr)
        app = self.profile / 'antigravity-cli'
        self.assertEqual((app / 'antigravity-oauth-token').stat().st_mode & 0o777, 0o600)
        self.assertTrue((app / 'jetski_state.pbtxt').exists())
        self.assertTrue((app / 'cache/onboarding.json').exists())
        settings = json.loads((app / 'settings.json').read_text())
        self.assertNotIn('statusLine', settings)            # the user's settings are not copied
        self.assertEqual(settings['toolPermission'], 'proceed-in-sandbox')
        self.assertEqual(settings['artifactReviewPolicy'], 'agent-decides')
        self.assertTrue(settings['enableTerminalSandbox'])
        ws = str(self.ws.resolve())
        self.assertEqual(settings['permissions']['allow'], [f'write_file({ws}/)'])
        self.assertEqual(settings['trustedWorkspaces'], [ws])
        hooks = json.loads((self.profile / 'config/hooks.json').read_text())
        self.assertIn('tmux-subagent-agy-stop-hook.sh', hooks['tmux-subagents']['Stop'][0]['command'])

        settings['trustedWorkspaces'] = ['/elsewhere', ws]  # agy adds to it too
        settings['permissions']['allow'].append('read_file(/elsewhere/)')
        (app / 'settings.json').write_text(json.dumps(settings))
        other = self.root / 'cache'
        other.mkdir()
        again = self.run_helper('create', self.profile, '--source', self.source, '--workspace', self.ws,
                                '--write', other)
        self.assertEqual(again.returncode, 0, again.stderr)
        settings = json.loads((app / 'settings.json').read_text())
        self.assertEqual(settings['trustedWorkspaces'], ['/elsewhere', ws])
        self.assertEqual(settings['permissions']['allow'],
                         ['read_file(/elsewhere/)', f'write_file({ws}/)', f'write_file({other.resolve()}/)'])

        flags = self.run_helper('flags', self.profile).stdout.split()
        self.assertEqual(flags, [f'--gemini_dir={self.profile.resolve()}', '--app_data_dir=antigravity-cli'])
        self.assertEqual(self.run_helper('destroy', self.profile).returncode, 0)
        self.assertFalse((app / 'antigravity-oauth-token').exists())
        self.assertTrue((app / 'settings.json').exists())
        self.assertEqual(self.run_helper('destroy', self.profile, '--all').returncode, 0)
        self.assertFalse(self.profile.exists())
        self.assertTrue((self.source / 'antigravity-cli/antigravity-oauth-token').exists())

    def test_refusals(self):
        def refused(*args):
            out = self.run_helper(*args)
            self.assertEqual(out.returncode, 64, out.stdout + out.stderr)
            return out.stderr
        refused('create', self.profile, '--source', self.source)                     # no workspace
        refused('create', self.profile, '--source', self.root / 'none', '--workspace', self.ws)
        self.assertIn('not made by this script',
                      refused('create', self.source, '--source', self.source, '--workspace', self.ws))
        refused('create', self.profile, '--source', self.source, '--workspace', '/')
        refused('destroy', self.source, '--all')                                      # not ours
        self.assertTrue(self.source.exists())

    def test_no_hook(self):
        out = self.run_helper('create', self.profile, '--source', self.source, '--workspace', self.ws, '--no-hook')
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads((self.profile / 'config/hooks.json').read_text()), {})


class LaunchRecordsHookedProfile(unittest.TestCase):
    def test_agy_profile_hooked(self):
        launch = load('tmux-subagent-launch')
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'config').mkdir()
            command = f"zsh -c 'command agy --gemini_dir={tmp} --app_data_dir=antigravity-cli --sandbox'"
            self.assertFalse(launch.agy_profile_hooked(command))
            (Path(tmp) / 'config/hooks.json').write_text(
                '{"tmux-subagents": {"Stop": [{"command": "sh /x/tmux-subagent-agy-stop-hook.sh"}]}}')
            self.assertTrue(launch.agy_profile_hooked(command))
            self.assertFalse(launch.agy_profile_hooked("zsh -c 'agy --sandbox'"))


if __name__ == '__main__':
    unittest.main()
