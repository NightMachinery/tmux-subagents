# Print-mode workers in tmux

Read only before intentionally launching a headless Claude Code worker with
`-p`/`--print`. These lessons were observed with Claude Code 2.1 in September
2026. Re-verify them on the installed version before relying on the behavior;
this is separate from the main skill's interactive permission guidance.

- A print-mode child could not read outside its working directory unless each
  referenced directory was passed with `--add-dir`. Include the private run
  directory, required skill directories and any other repository named in the
  brief, within the task's existing authorization.
- `--permission-mode acceptEdits` approved edits but refused shell commands in
  the observed print-mode launches. A child that must build, render or commit
  needs a mode and rules that approve those commands, or an explicit plan for
  the coordinator to build, verify and commit the child's edits. Do not infer
  shell approval from successful file edits.

Check both outside-directory reading and an inert shell command before a long
unattended launch. If blocked, publish the edits and a PARTIAL result with the
remaining coordinator steps. Do not silently loosen permissions to make it run.
