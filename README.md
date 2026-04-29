Migration of CSE 230 MIPS Lab Autograding to Gradescope

Objective: To replace the restrictive ZyLabs environment with a flexible, Docker-based autograder using the SPIM simulator. This allows for complex memory-level verification and provides students with a grading environment consistent with the QtSpim GUI used in class.

Technical Architecture: The autograder operates on a Wrapper-Simulate-Verify model:

- Environment: A Linux-based Docker container running spim (the command-line equivalent of QtSpim).
- Injection Logic: The student’s code is appended to a "Test Harness" (test_harness.s). This harness initializes the base address register ($s0) and populates A[0] and A[1] with specific test case values.
- Output Parsing: The Python driver executes the code, captures the memory dump, and uses regular expressions (regex) to verify the contents of memory addresses 12($s0) through 28($s0).

Verification Criteria (Test Cases): The logic ensures the following ALU and Memory operations are performed correctly:

- 64-bit Multiplication: High and low order bits must be correctly split into A[2] and A[4].
- Division/Modulo: Quotient and remainder logic for A[5] and variable a.
- Bitwise Manipulation: Correct execution of right shifts (srl), masks (andi), and logical ORs.
- Concatenation & Alignment: Validation of the manual memory placement of b, c, and d into the word at A[6].

Files in this Repository:

- setup.sh: Shell script to provision the Docker container with spim and python3.
- autograder.py: The main Python driver that handles the execution, parsing, and results.json generation.
- test_harness.s: The assembly template used to wrap student submissions.
- solution_reference.s: The verified reference implementation for internal testing.

How to Run Locally:

- Ensure spim is installed on your system.
- Place the student submission as submission.s.
- Run the driver:

Bash
python3 autograder.py
View the output in results.json.
