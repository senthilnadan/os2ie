# Two-Transition DSTT — Implementation Plan

**Branch:** `feature/two-transition-dstt`
**Seeds:** `training/two_transition_dstt/seed.json` (8 scenarios)

---

## What already works

The kernel loop already handles two-transition DSTTs correctly:

```
for segment in abstract_dstt.segments:
    for abstract_transition in segment.transitions:
        # COMPILE — state passed in includes everything accumulated so far
        exec_dstt = t2e.compile(task, state, abstract_transition, available_tools)

        # DISPATCH
        state.update(grounded.inputs)   # PATCH
        outputs = tool_fn(state)        # DISPATCH
        state.update(outputs)           # MERGE — T1 outputs now in state

        # Loop continues → T2 compile receives updated state
```

After T1 dispatches, `state` contains T1's output keys. T2's `t2e.compile()` call
receives this updated state — transition2exec sees T1's outputs as available context
when resolving T2's inputs. **No kernel changes required.**

---

## What needs to be built

### 1. Extend StubTransition2ExecClient — capture compile-time state

The stub currently pops queued responses without recording arguments.
For two-transition tests, we must assert that T2's compile received T1's outputs
in the `state` argument.

**Change:** add `captured_states: list[dict]` — records the `state` passed to each
`compile()` call in order.

```python
# tests/stub_t2e.py addition
class StubTransition2ExecClient:
    def __init__(self, responses):
        self._queue = list(responses)
        self.captured_states: list[dict] = []   # NEW
        # ... existing validation ...

    def compile(self, task, state, abstract_transition, available_tools=None):
        self.captured_states.append(dict(state))   # NEW — snapshot before compile
        if not self._queue:
            raise RuntimeError("no more responses queued")
        return self._queue.pop(0), {}
```

**Assert pattern in tests:**
```python
# T2's compile saw T1's output in state
assert "text" in stub.captured_states[1]
assert stub.captured_states[1]["text"] == "hello world"
```

---

### 2. Test-scoped tool stubs — deterministic dispatch

Tools (read_file, create_file, etc.) touch the real filesystem. Tests must not depend
on real files. Introduce a test-scoped tool registry override:

```python
# tests/stub_tools.py
from src import tools

def patch_tool_registry(monkeypatch, overrides: dict[str, callable]):
    """Replace named tools in TOOL_REGISTRY for the duration of a test."""
    for name, fn in overrides.items():
        monkeypatch.setitem(tools.TOOL_REGISTRY, name, fn)
```

Each test provides deterministic tool stubs:
```python
def stub_read_file(state):
    return {"text": "hello world"}

def stub_create_file(state):
    return {"success": True}
```

---

### 3. Test structure — per seed

Each of the 8 seeds becomes one test. Common pattern:

```
test_tt<N>_<scenario_name>:
  1. Build AbstractDSTT from seed (two transitions, one segment)
  2. Build initial_context from seed
  3. Queue two stub t2e responses (T1 compiled tool, T2 compiled tool)
  4. Patch tool registry with deterministic stubs
  5. Run kernel.execute()
  6. Assert A — T2 compile received T1 outputs in state
  7. Assert B — final state contains all expected keys
  8. Assert C — milestone_reached matches seed milestone
  9. Assert D — execution_log has 2 entries, both ok
  10. Assert E — result.status == "completed"
```

---

### 4. Assertions per seed

| Assert | What it proves |
|--------|----------------|
| `stub.captured_states[1]` contains T1 output keys | State threaded correctly — T2 compile sees T1 output |
| `stub.captured_states[0]` does NOT contain T1 output keys | State was empty of T1 outputs before T1 ran |
| `result.state` contains initial_context + T1 outputs + T2 outputs | Cumulative merge — nothing dropped |
| `result.milestone_reached` ⊇ seed milestone | Milestone validates correctly after both transitions |
| `len(result.execution_log) == 2` | Both transitions executed |
| All log entries `status == "ok"` | No dispatch errors |
| `result.status == "completed"` | Full segment completed |

---

### 5. Key state threading cases to cover

| Seed | Thread | What assert A checks |
|------|--------|----------------------|
| tt01 | `text → content` | `captured_states[1]["text"] == <T1 output>` |
| tt02 | `created` in state | `captured_states[1]["created"] == True` |
| tt03 | `copied` in state | `captured_states[1]["copied"] == True` |
| tt04 | `is_present` in state | `captured_states[1]["is_present"] == True` |
| tt05 | `entries` in state | `captured_states[1]["entries"] == [...]` |
| tt06 | `text → content` | `captured_states[1]["text"] == <T1 output>` |
| tt07 | `created` in state | `captured_states[1]["created"] == True` |
| tt08 | `deleted` in state | `captured_states[1]["deleted"] == True` |

---

### 6. File layout

```
tests/
  stub_tools.py                       NEW — tool registry patch helper
  test_two_transition_dstt.py         NEW — 8 tests (one per seed)

tests/stub_t2e.py                     MODIFIED — add captured_states
```

---

## Execution order

1. Extend `stub_t2e.py` — add `captured_states`
2. Create `tests/stub_tools.py` — tool registry patch helper
3. Write `tests/test_two_transition_dstt.py` — 8 tests
4. Run `pytest tests/test_two_transition_dstt.py -v`
5. All 8 pass → commit + push

---

## Pass criteria

- 8/8 tests passing
- Assert A confirmed for all 8: T2's compile received T1's outputs in state
- No test touches the real filesystem
- No kernel changes required — the loop already threads state correctly
