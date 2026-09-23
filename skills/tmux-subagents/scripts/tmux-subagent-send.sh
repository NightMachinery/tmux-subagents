#!/bin/sh
# tmux-subagent-send.sh PANE_ID (--file PATH | -- TEXT)
#
# Parent side: types one follow-up into a Claude Code child's input box and
# submits it, then checks mechanically that it left the box. Prints exactly one
# line on stdout and exits with its code:
#   SENT <pane>           0  the input line is empty after the submit
#   NOT-SUBMITTED <pane>  1  text still sits in the input line after two C-m
#   REFUSED <pane>        2  no idle input box: a permission or trust modal, text
#                            someone is already typing, or a dead/unknown pane
# The one-line status is the check. Do not also read the pane for every message.
#
# Why each step:
# - The text goes with `send-keys -l`, so words like Enter or C-c are typed,
#   not read as key names, in chunks, since tmux refuses one oversized command.
# - The submit is a separate `C-m` about 1.5 s later, then verified. A typed
#   follow-up has been seen to sit unsubmitted in a child's input box (once,
#   while a user was attached to that pane); the cause is unconfirmed. Checking
#   the input line and retrying `C-m` once makes the cause irrelevant to callers.
# - The check reads `capture-pane -e`: the input line is the last line starting
#   with `❯` that is not a menu item (`❯ 1. Yes`), plus its continuation lines
#   up to the box's bottom rule. Dim text (ESC[2m) there is Claude Code's prompt
#   suggestion, not typed input, so it is removed before testing for emptiness.
#   A busy child still shows its input box and queues what was typed.
# - Under `editorMode: vim` an empty box in NORMAL state (no `-- INSERT --` in
#   the footer) gets one `i` first; if INSERT still does not show, REFUSED.
set -eu
[ $# -ge 2 ] || { echo "usage: $0 PANE_ID (--file PATH | -- TEXT)" >&2; exit 64; }
exec python3 - "$@" <<'PY'
import re, subprocess, sys, time

pane, mode = sys.argv[1], sys.argv[2]
if mode == "--file" and len(sys.argv) == 4:
    with open(sys.argv[3], encoding="utf-8") as f:
        text = f.read()
elif mode == "--":
    text = " ".join(sys.argv[3:])
else:
    print(f"usage: tmux-subagent-send.sh PANE_ID (--file PATH | -- TEXT)", file=sys.stderr)
    sys.exit(64)
# A trailing newline would be typed as a newline in the box; the submit is ours.
text = text.rstrip("\n")
if not text:
    print("empty message", file=sys.stderr)
    sys.exit(64)

def tmux(*args, check=True):
    return subprocess.run(["tmux", *args], check=check, capture_output=True, text=True).stdout

def say(word, code):
    print(f"{word} {pane}")
    sys.exit(code)

ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[()][0-9A-Za-z]|\x1b[=>]")
DIM = re.compile(r"\x1b\[2m.*?(?=\x1b\[(?:0|22)?m|$)")
RULE = re.compile(r"^\s*─{8,}")
MENU = re.compile(r"^❯\s*\d+\.")
MODAL = re.compile(r"Do you want to|Do you trust|Yes, I trust|Esc to cancel|Enter to confirm")

def input_state():
    """'empty', 'typed' or 'none' (no input box on screen)."""
    try:
        raw = tmux("capture-pane", "-p", "-e", "-J", "-t", pane).splitlines()
    except subprocess.CalledProcessError:
        return "none"
    plain = [ANSI.sub("", l) for l in raw]
    start = None
    for i in range(len(plain) - 1, -1, -1):
        s = plain[i].lstrip()
        if s.startswith("❯"):
            if MENU.match(s):
                return "none"
            start = i
            break
    if start is None or MODAL.search("\n".join(plain[start:])):
        return "none"
    body = []
    for i in range(start, len(raw)):
        if i > start and RULE.match(plain[i]):
            break
        body.append(ANSI.sub("", DIM.sub("", raw[i])))
    body[0] = body[0].lstrip().removeprefix("❯")
    residue = "".join(body).replace("\xa0", " ").strip()
    return "typed" if residue else "empty"

try:
    dead = tmux("display-message", "-p", "-t", pane, "#{pane_dead}").strip()
except subprocess.CalledProcessError:
    dead = ""
if dead != "0":
    say("REFUSED", 2)
if input_state() != "empty":
    say("REFUSED", 2)

# With `editorMode: vim`, a box in NORMAL state would read the text as editing
# commands. NORMAL shows no marker; INSERT shows `-- INSERT --` in the footer.
# An empty box in NORMAL state is harmless to leave with `i`, so do that once.
def vim_configured():
    import glob, json, os
    homes = [os.environ.get("CLAUDE_CONFIG_DIR", "")] + glob.glob(os.path.expanduser("~/.claude*"))
    for home in homes:
        try:
            with open(os.path.join(home, "settings.json")) as f:
                if json.load(f).get("editorMode") == "vim":
                    return True
        except (OSError, ValueError, AttributeError):
            pass
    return False

def insert_shown():
    return "-- INSERT --" in tmux("capture-pane", "-p", "-t", pane)

if vim_configured() and not insert_shown():
    tmux("send-keys", "-t", pane, "i")
    time.sleep(0.7)
    if not insert_shown() or input_state() != "empty":
        say("REFUSED", 2)

# Chunk on characters, well under tmux's per-command message limit.
for i in range(0, len(text), 1000):
    tmux("send-keys", "-t", pane, "-l", "--", text[i:i + 1000])
time.sleep(1.5)
for attempt in range(2):
    tmux("send-keys", "-t", pane, "C-m")
    time.sleep(1.5)
    state = input_state()
    if state == "empty":
        say("SENT", 0)
    if state == "none":
        # The box gave way to a modal, which only a running turn raises, so the
        # message went in. Never press C-m again here: it would pick option 1.
        alive = tmux("display-message", "-p", "-t", pane, "#{pane_dead}", check=False).strip()
        say("SENT", 0) if alive == "0" else say("NOT-SUBMITTED", 1)
say("NOT-SUBMITTED", 1)
PY
