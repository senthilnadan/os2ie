DSTT Reasoning Benchmark Challenge (Full Task Suite)

Objective: Evaluate how far a 3B model with DSTT can match a 120B model
using identical tools.

LEVEL 1 --- Linear Reasoning 1. Start with 5 → multiply by 3 → add 7 →
subtract 2 (Expected: 20) 2. Numbers 1--6 → keep even → sum (Expected:
12) 3. "abcde" → reverse → uppercase → append "\_X" (Expected: EDCBA_X)

LEVEL 2 --- State & Dependency 4. x=2, y=x+3, z=y*x (Expected: 10) 5.
\[1,2,3\] → double → remove \>4 (Expected: \[2,4\]) 6. For 1--5:
even→*2, odd→+1 (Expected: \[2,4,4,8,6\])

LEVEL 3 --- Multi-step Chains 7. 3 → square → add previous → multiply by
2 (Expected: 24) 8. 1--10 → multiples of 3 → square → sum (Expected:
126) 9. x=4, y=2x, z=y+x, w=z−y (Expected: 4)

LEVEL 4 --- Constraints 10. Schedule A(2h), B(3h), C(1h), B after A 11.
Assign 3 workers to 3 tasks, B requires worker 1

LEVEL 5 --- Logical Consistency 12. Truth puzzle (A,B,C statements) 13.
5 box puzzle (single true statement)

LEVEL 6 --- Algorithmic Reasoning 14. 6 → binary → reverse → decimal
(Expected: 3) 15. 5 → square → binary → count 1s → \*3 (Expected: 9)

Evaluation Metrics: - Correctness - Step accuracy - Tool usage
correctness - Constraint satisfaction - Failure reason tracking

Conclusion: 3B + DSTT approximates structured reasoning. 120B dominates
in global search and deep logic.
