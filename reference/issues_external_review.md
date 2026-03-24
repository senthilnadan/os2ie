# Review Comments — issues_external.md
# Filed to: task2plan team (abstract_dstt owners)
# Date: 2026-03-23

These comments review the field operations issues report against the known
architecture before routing to the task2plan team. Several issues require
clarification or reassignment before action is taken.

---

## ISS-AT-001 — Wrong tool selected for read task

**Review verdict: MISATTRIBUTED — reassign to transition2exec**

`as_task2plan` produces abstract tool names. Abstract tool names are by design
not grounded — two programmers describing "read a file" may produce different
abstract names and both are correct. The responsibility for selecting the right
concrete tool (`read_file` vs `exists`) belongs entirely to `transition2exec`,
which holds the grounded tool catalog.

The field ops report attributes this to `as_task2plan` because the wrong
concrete tool was executed. That is a grounding decision — it happens in
`transition2exec`, not in the planner.

**Action for task2plan team:** None. This issue does not belong to you.

**Action for transition2exec team:** When an abstract tool signals a read
operation (by name, output key, or output type), ground it to `read_file`,
not `exists`. These are semantically distinct tools. `exists` never fails;
`read_file` fails on missing files. The distinction is critical for callers
who depend on `status=failed` as a signal.

---

## Architectural clarification — Split/Join responsibility

Before reviewing individual issues, an architectural decision has been made
that affects how multi-step failures are owned:

**transition2exec owns split/join decisions.**

The action splitter and task2plan have no tool awareness and are not expected
to get decomposition size correct. transition2exec is the only component with
access to the tool catalog. It decides whether an abstract transition maps to
one tool, needs splitting into multiple tool calls, or can be joined with an
adjacent transition.

This means:
- Multi-step collapse failures are **not task2plan issues** — the planner
  describes abstract intent, not tool count.
- Split/join correctness failures are **transition2exec issues** — it must
  detect when an abstract action has no direct tool mapping and split or join
  accordingly.
- The action splitter's decomposition only needs to be roughly bounded, not
  correct. transition2exec corrects it.

Issues AT-002, AT-003, AT-004 below are reclassified under this principle.

---

## ISS-AT-002 — Wrong sequence for create-then-append task

**Review verdict: RECLASSIFIED — transition2exec split/join responsibility**

The action splitter's decomposition size is not required to be correct.
transition2exec must detect that the abstract transitions for this task form
a create → append → append sequence and produce the correct executable
transitions in order, with state threading between them.

**Action for task2plan team:** None.
**Action for transition2exec team:** When adjacent abstract transitions share
a file artifact as both output and input, preserve sequencing and state
threading across the join. Do not collapse or repeat transitions.

---

## ISS-AT-003 — Multi-step task incomplete: shell output not written to file

**Review verdict: RECLASSIFIED — transition2exec split/join responsibility**

The action splitter's decomposition is not required to be correct. transition2exec
must recognise that running a shell command and writing its stdout to a file
are two dependent tool calls — `run_shell_command` followed by `create_file`
with `stdout` as content — and produce both executable transitions with correct
state threading.

**Action for task2plan team:** None.
**Action for transition2exec team:** When an abstract transition implies
capturing shell output into a file, produce two grounded transitions:
`run_shell_command` → `create_file(content=stdout)`. State must thread
`stdout` from the first to the second.

---

## ISS-AT-004 — Multi-step task incomplete: make_directory then create_file

**Review verdict: RECLASSIFIED — transition2exec split/join responsibility**

The action splitter's decomposition is not required to be correct. transition2exec
must recognise that creating a directory and then creating a file inside it are
two dependent tool calls — `make_directory` followed by `create_file` — and
produce both with correct state threading between them.

**Action for task2plan team:** None.
**Action for transition2exec team:** When abstract transitions have a
directory-then-file dependency, sequence `make_directory` before `create_file`
and thread the directory path through state.

---

## ISS-AT-005 — Count python files: wrong tool selected

**Review verdict: VALID — task2plan issue, but abstract tool naming is the lever**

This is a single atomic task — no splitting concern. The task:
```
"Count all Python files in /tmp/.../test_dir"
```

The abstract DSTT produced should signal a shell execution operation, not a
directory listing. The abstract tool name and output type matter here.

If the abstract tool is named something like `list_directory_contents` or
`enumerate_files`, transition2exec may reasonably ground it to `list_directory`
— a non-shell tool. If the abstract tool is named something like
`count_files_by_shell` or `run_file_count_command`, transition2exec is guided
toward `run_shell_command`.

**Action for task2plan team:** For tasks that imply shell execution (counting,
filtering, searching by content), the abstract tool name and output type should
signal shell execution intent. The abstract DSTT does not reference concrete
tools — but it can carry semantic signal through naming and `resource_required`.

Specifically: ensure that `resource_required` includes `"shell"` or
`"run_shell_command"` for tasks that require shell execution. This gives
transition2exec the signal it needs to ground correctly without the planner
having to know about concrete tools.

---

## Summary for task2plan team

| Issue | Verdict | Action |
|-------|---------|--------|
| ISS-AT-001 | Misattributed — belongs to transition2exec | No action |
| ISS-AT-002 | Reclassified → transition2exec (split/join) | No action |
| ISS-AT-003 | Reclassified → transition2exec (split/join) | No action |
| ISS-AT-004 | Reclassified → transition2exec (split/join) | No action |
| ISS-AT-005 | Valid — use `resource_required` to signal shell intent | Update abstract tool generation |

**Key ask:** For issues AT-002, AT-003, AT-004 — provide the Action Splitter
output for each failing task before accepting the issues. The boundary between
the splitter and the planner must be established to avoid misrouting fixes.
