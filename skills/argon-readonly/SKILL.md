---
name: argon-readonly
description: Use Gemini 4 Argon through the Antigravity CLI (agy) for work that needs no writes, such as code review, design or plan critique, second opinions and research over local files. Covers checking which account offers Argon, the read-only headless invocation, sizing jobs so a long answer is not cut off, prompt shapes that keep the result, capturing output, budgeting its separate weekly quota, and verifying what it reports.
---

# Argon for read-only work

Gemini 4 Argon is a strong reasoning model offered in the Antigravity CLI (`agy`) to some accounts. It is a good second opinion for review and planning, but it has two traps: on large inputs a long answer can be cut off and lost while the quota is still charged, and at medium effort it may spend its whole answer on visible working notes. This skill is about getting a usable result from it for work that needs no writes.

When the shared `delegate` skill is installed, read it first for worker choice, account boundaries, briefs and result review; this skill only covers Argon itself. Use `tmux-subagents` instead when the job needs an interactive, attachable session, and its section "Operating an agy worker" when Argon must write: a sandboxed throwaway profile, a bell that wakes the operator, quota readings before and after, and the operator verifying and committing.

## When to use it

- Good fits: reviewing a diff or a module for real defects, critiquing a design or plan, checking a proof or an argument, comparing approaches, summarizing what a body of local files says, producing a list of risks or test cases.
- Poor fits: anything that must edit files or run commands with effects (see "Operating an agy worker" in `tmux-subagents` for that), quick lookups (a cheaper model is enough), and jobs whose input is much larger than a few thousand lines (split them first).
- Never use it to reach a verdict nobody checks. Treat every finding as a claim to verify (see Verify).

## 1. Check access

Argon is rolled out per account, not per plan: two accounts on the same plan can differ. List the models of the account you mean to use and pick the exact slug:

```sh
agy models | grep -i argon
# gemini-4-argon-low, gemini-4-argon-medium, gemini-4-argon-high
```

If the account does not list Argon, asking for it fails at once with "not recognized as a known model", before any quota is spent. If you have several agy accounts behind local launchers, check each and pick one that lists the model; a quota-aware picker should skip accounts without it. Never invent a profile flag.

## 2. Pick the effort

- **Medium is the default for real work.** In the measurements below it finished a review of about 3,700 lines in under nine minutes.
- **High only for small inputs** (well under a thousand lines, or one focused question). On the 3,700-line review, High thought for about nine and a half minutes per attempt, the stream was then cut ("The stream was interrupted. Please continue the task you were working on."), agy retried once with the same result, and the run ended with no answer. The quota was charged anyway.
- **Low** for quick checks and triage.

The slugs carry the effort. `agy --help` also lists a separate `--effort` flag; do not combine it with an effort-bearing slug unless you have checked what it does for that model.

## 3. Prepare a workspace

agy treats its working directory as the workspace and reads files there.

- Make a scratch directory and copy in exactly the inputs the job needs (the diff, the files after the change, the tests, the design note). Keep it small and focused; every extra file is input it may read.
- Put the task in a brief file in that directory when it holds anything private, and keep the command line short ("Read brief.md and do what it says"). Command lines are visible to other processes.
- Do not point it at a live repository checkout when a copy will do.

## 4. Run it read-only and headless

```sh
cd /abs/path/to/scratch
agy --model gemini-4-argon-medium --mode plan \
    --print-timeout 25m --output-format json \
    --print "Read brief.md in this folder and do what it says." \
    > argon.json 2> argon.stderr
```

- `--mode plan` keeps the session read-only. Read-only work never needs `--dangerously-skip-permissions`, and it should not be used for it.
- `--print-timeout` bounds the run; pick something above the expected time (Medium: about ten minutes for a large review).
- `--output-format json` gives one object with `status`, `response`, `error`, `duration_seconds`, `conversation_id` and `usage` (`input_tokens`, `output_tokens`, `thinking_tokens`, `cache_read_tokens`, `total_tokens`).
- Untested idea for long jobs: `--output-format stream-json` writes events as they arrive, so a run that is cut off may still leave partial text on disk.

## 5. Shape the prompt so the result survives

- **Answer first.** Ask for the final findings first and any reasoning after, or ask for each finding to be written as soon as it is found. Medium has stopped after pages of working notes with "I am ready to write the review", before the write-up; an answer-first prompt keeps the substance at the top.
- **Name the output format exactly:** for a review, "for each finding: severity P0 to P3, file and line, a concrete failure scenario, the fix; most severe first; say plainly if you find nothing serious; no style issues; end with a one-paragraph verdict".
- **One question per run.** Split a big review by file, by concern (concurrency, error paths, documentation) or by commit, so each answer needs well under about 20,000 tokens of reasoning.
- **Give the context it cannot infer:** what the code is for, what was intended, known non-issues, and what "done" looks like.

## 6. Check the result

- `status` must be `SUCCESS` and `response` non-empty. `ERROR` with "stream was interrupted" means the job was too big for one answer: split it instead of rerunning it unchanged.
- If `response` is mostly working notes, the findings are usually near the end; extract them rather than paying for a rerun. A follow-up turn on the same conversation (`--conversation <id>` with "write the final review now, findings only") is possible but untested here.
- Keep `argon.json` with the job's inputs, so the token use and the exact output can be checked later.

## 7. Budget the quota

- Argon has its **own weekly bucket** per account ("Gemini 4 Argon Weekly Limit"), separate from the general Gemini five-hour and weekly buckets and from the Claude and GPT buckets. Argon jobs did not move any of the others. No five-hour Argon bucket was shown.
- The cost follows **output tokens** (thinking included) much better than total tokens: about one point of the weekly bucket per 8,000 to 10,000 output tokens, from two measurements with whole-percent readings (so each figure is uncertain by about a point). A large review costs five or six points, so fewer than twenty such jobs fit in a week per account.
- Read the buckets before and after a job when it matters: `agy -p /usage` asks the backend (whole percents); a TUI statusline cache, where you have one, carries a decimal.

## 8. Verify before acting

Argon's findings read well whether or not they are right. Before anyone changes code because of them:

- Hand each finding to whoever owns the code (or an independent agent) to reproduce or refute, with a test where possible, and record a verdict per finding: CONFIRMED, PARTLY, REFUTED or BY DESIGN.
- Expect some findings to describe intended behaviour as a bug, and some scenarios to rest on a misread line. Fix only what is confirmed.
- Say in any report that the findings came from Argon and were verified (or not), and by whom.

## Measurements behind this skill

The trials, their token counts and quota readings are kept in the public note [Antigravity limits: Argon](https://github.com/NightMachinery/notes-public/blob/master/subjects/Google/Gemini/Antigravity/limits/Argon.org). Update the numbers here when new measurements change them.
