DSTT Reasoning Benchmark Challenge

Objective: Evaluate how far a 3B model with structured reasoning
(DSTT/ReAct loop) can match a 120B model.

Levels: L1: Linear reasoning L2: State tracking L3: Multi-step
dependency L4: Constraint satisfaction L5: Logical consistency L6:
Algorithmic reasoning

Sample Tasks: 1. Start with 5 → multiply by 3 → add 7 → subtract 2
(Expected: 20) 2. Numbers 1--6 → keep even → sum (Expected: 12) 3. x=2,
y=x+3, z=y\*x (Expected: 10) 4. Schedule tasks with constraints 5.
Logical truth puzzle 6. Binary transformation chain

Evaluation Criteria: - Correctness - Step consistency - Constraint
adherence - No hallucination

Goal: Demonstrate boundary between structured execution reasoning vs
global search reasoning.

Conclusion: 3B + system ≈ structured reasoning engine 120B ≈ full
reasoning + search engine
