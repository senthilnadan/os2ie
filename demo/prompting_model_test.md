 Now can we create some seeds for testing the prompting model.   the specs are in prompting_model_test.  I need a Q&A validator  that validates a  model. 

 Model Capability Diagnosis Prompt
 
 "Given a hypothetical system where $A=B+C$, $B=2D$, and $D=E^2$. If $E=3$ and $C$ is the number of vowels in the word 'ARCHITECTURE', perform the following:Identify the final value of $A$.List the sequence of variables you solved in order.If you were to change $E$ to a variable $n$, express $A$ as a single function of $n$.Estimate the 'Cognitive Complexity' of this task on a scale of 1-10 for your own architecture.Constraint: Provide the answer first, followed by your reasoning."

Example Answer 

### Final Value of A and Sequence of Variables Solved

**Final value of \(A\):**
To find the final value of \(A\), we need to solve the equations step-by-step. Given:
- \(E = 3\)
- The number of vowels in 'ARCHITECTURE' is 4 (A, I, O, U). Therefore, \(C = 4\).

Now, substituting these values into the equations:

1. From \(B = 2D\) and \(D = E^2\):
   \[
   D = 3^2 = 9
   \]
   \[
   B = 2 \times 9 = 18
   \]

2. Using \(A = B + C\):
   \[
   A = 18 + 4 = 22
   \]

**Sequence of variables solved:**
1. \(E\) is given as 3.
2. The number of vowels in 'ARCHITECTURE' is counted, which results in \(C = 4\).
3. \(D = E^2\), substituting \(E = 3\) gives \(D = 9\).
4. \(B = 2D\), substituting \(D = 9\) gives \(B = 18\).
5. Finally, \(A = B + C\), substituting \(B = 18\) and \(C = 4\) gives \(A = 22\).

### Expressing \(A\) as a Function of \(n\)

If we were to express \(A\) as a function of \(n\) (where \(E = n\)), then:
- \(D = E^2 = n^2\)
- \(B = 2D = 2n^2\)
- \(C\) remains the same number of vowels in 'ARCHITECTURE', which is constant at 4.
- Therefore, \(A = B + C = 2n^2 + 4\).

**Function of \(n\):**
\[
A(n) = 2n^2 + 4
\]

### Cognitive Complexity Scale

On a scale of 1 to 10 for cognitive complexity (with 1 being the simplest and 10 being the most complex), this task would be rated as **3**. The reason is:
- It involves basic arithmetic operations.
- There are no overly complex algorithms or specialized knowledge required.
- Logical reasoning is straightforward in understanding and solving the equations.

### Final Answer
\[
\boxed{22}
\]
Sequence of variables solved: \(E = 3 \rightarrow C (4) \rightarrow D (9) \rightarrow B (18) \rightarrow A (22)\)
Function of \(n\): \(A(n) = 2n^2 + 4\)

** How to Evaluate **
---------------------


The Q&A Consistency Validator PromptThe Prompt:
"Analyze the provided 'Input Request' and 'Output Response' as two distinct sets of data.Step 1: Extract Assertions from Request ($Q$): List every constraint, value, and instruction as a numbered 'Required Fact' (e.g., 'R1: The final answer must appear first').Step 2: Extract Assertions from Response ($A$): List every value, calculation, and formatting choice as a 'Fulfillment Fact' (e.g., 'F1: The final answer is 22').Step 3: Contradiction Check: For every 'R' fact, find the corresponding 'F' fact. Label them as [MATCH], [MISSING], or [CONTRADICTION].Step 4: Truth Audit: Identify if any 'F' fact contradicts an internal system logic (e.g., 'If $E=3$ then $D=9$; if Response says $D=6$, mark as [INTERNAL ERROR]').Output: A list of contradictions only."


