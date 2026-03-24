# OS2I — Mission & Roadmap

## Mission

Explore how far a structured agent architecture can go on small LLMs.

Not general-purpose reasoning. Not a framework. A tight, observable, evidentiary
system that runs on models anyone can deploy — and pushes them as far as they
can go.

The bet: most agent complexity comes from poor architecture, not small models.
OS2I tests that bet, generation by generation.

---

## The Journey

### Generation 1 — Structured Execution  `← we are here`

> A small LLM as a compiler, not a controller.

The model does one thing: map one abstract tool to one grounded tool call.
The kernel executes mechanically. State is explicit. Failures are hard and
immediate. Every decision is observable.

**What it can do:**
- O(1) to O(n) linear task execution on a tight tool domain
- Deterministic, reproducible execution
- Full evidentiary record — what the model knew, what it was asked, what it decided

**Confidence target:** 90–95% on tight domain, O(1)–O(n) tasks

**Milestone:** end-to-end execution with observable transition records
across the seed task suite.

---

### Generation 2 — Adaptive Execution  `[ not started ]`

> The plan bends when reality diverges.

Milestone boundaries become decision points. The system can branch to a
different segment based on what a milestone revealed. Milestone outputs are
validated — not just present, but semantically correct.

Genuine replanning (amending the DSTT mid-execution given committed segments)
is the full second-gen capability. It requires the model to reason about what
was already sealed and what remains — the hardest thing a small LLM can be
asked to do coherently.

**What it adds:**
- Conditional segment routing at milestone boundaries (DSTT as DAG, not list)
- Milestone validation — rule-based and LLM binary check
- Partial replanning at segment boundaries (ambitious on small LLMs)

**Confidence target:** 85–90% on branching tasks in tight domain

**Milestone:** a task that takes two different execution paths based on
tool output, correctly validated at the milestone boundary.

---

### Generation 3 — Self-Aware Execution  `[ research ]`

> The system knows what it doesn't know.

The agent distinguishes between the task it was given and the goal behind it.
It recognises when it's at the edge of its competence boundary — before failing,
not after. It can negotiate scope rather than execute blindly.

Cross-run learning closes the loop: the evidentiary records from Gen 1 and Gen 2
become training signal. The model learns from its own failure modes.

**What it adds:**
- Goal-task alignment check before committing a plan
- Capability boundary detection — rule system + narrow LLM call
- Scope negotiation as a first-class output (not just completed/failed)
- Fine-tuning on own execution records (failure stage, state at failure, correct path)

**Milestone:** the system surfaces a scope conflict before executing and
negotiates a corrected task with the caller, then executes successfully.

---

### Generation 4 — World Model  `[ frontier ]`

> The agent develops its own understanding of the domain it operates in.

Not task-driven. Model-driven. The agent maintains beliefs about the environment
that persist across runs, update from observations, and inform planning. It
reasons causally — not "this happened after that" but "this happened because
of that."

Autonomous goal formation. Calibrated uncertainty. The task is sometimes
self-generated.

This is where "generation" stops being the right word. It's a different class
of system — one we don't yet know how to build reliably, even with large models.

**What it requires:**
- Persistent belief state across runs
- Causal reasoning at runtime
- Calibrated uncertainty quantification
- Training objectives beyond next-token prediction

**Milestone:** the agent identifies a recurring failure pattern across runs,
updates its world model, and avoids the failure class proactively on the next run.

---

## Principles That Hold Across All Generations

- **One LLM call per decision.** Each call is narrow, focused, and bounded.
- **Hard failures.** Nothing is swallowed silently. The caller always knows exactly what happened.
- **Observable by design.** Every decision is recorded as it occurs — not reconstructed.
- **Small models first.** If it requires a large model, the architecture isn't tight enough yet.
- **The record is the product.** Execution produces evidence. The evidence is what you ship.
