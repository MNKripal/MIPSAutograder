#!/usr/bin/env python3
"""
Gradescope Autograder for MIPS Assignment (Question 7)
Prefix sums via a single procedure call (nSum).
Uses the instructor's MIPS code as the oracle solution.
"""

import json
import os
import subprocess
import re

# ----------------------------------------------------------------------
# Professor's MIPS solution
# ----------------------------------------------------------------------
PROF_SOLUTION = """\
# A - $s0, B - $s1, n - $s2

Main:    addi $t1, $zero, 0   # j = 0
Loop1:   bge $t0, $s2, Exit   # j >= n exit
         sll $t1, $t0, 2      # j * 4
         add $t1, $t1, $s1    # Address of B[j]
         addi $a0, $s0, 0     # 1st argument to function
         addi $a1, $t0, 0     # 2nd argument to function
         jal nSum             # Call function
         sw $v0, 0($t1)       # Write to B[j]
         addi $t0, $t0, 1     # j ++
         j Loop1

nSum:    lw $v0, 0($a0)       # sum = A[0]
         addi $t2, $zero, 1   # j = 1
Loop2:   bgt $t2, $a1, End    # j > k end
         sll $t3, $t2, 2      # j * 4
         add $t3, $t3, $a0    # address of A[j]
         lw $t3, 0($t3)       # value of A[j]
         add $v0, $v0, $t3    # sum += A[j]
         addi $t2, $t2, 1     # j ++
         j Loop2
End:     jr $ra

Exit:
"""

# ----------------------------------------------------------------------
# Hidden Test Cases
#   $s0 = nominal base address of input array A
#   $s1 = nominal base address of output array B
#   $s2 = n (length of A and B)
#   array = initial contents of A
# ----------------------------------------------------------------------
TEST_CASES = [
    {
        "name": "Test Case 1",
        "s0": 4000,
        "s1": 8000,
        "s2": 5,
        "array": [10, 5, -5, -2, 0]
    },
    {
        "name": "Test Case 2",
        "s0": 13800,
        "s1": 13804,
        "s2": 1,
        "array": [-8]
    },
    {
        "name": "Test Case 3",
        "s0": 8040,
        "s1": 8000,
        "s2": 10,
        "array": [-5, 8, 4, -6, 6, 0, -3, -2, 2, -2]
    },
    {
        # In-place: B shares A's address, so A elements are overwritten as
        # B is built. nSum must re-read the updated values from memory.
        "name": "Test Case 4",
        "s0": 2648,
        "s1": 2648,
        "s2": 8,
        "array": [-80, -40, 25, 20, -15, 10, -8, -4]
    }
]


def find_student_submission(submission_dir="/autograder/submission"):
    """
    Recursively searches the submission directory for a valid MIPS file
    (.asm or .asm.txt), ignoring macOS metadata files starting with '._'.
    """
    if not os.path.exists(submission_dir):
        # Fallback to local directory for debugging/local testing
        submission_dir = "./submission"
        if not os.path.exists(submission_dir):
            return None

    for root, dirs, files in os.walk(submission_dir):
        for f in files:
            # Skip macOS metadata files
            if f.startswith("._"):
                continue
            if f.endswith(".asm") or f.endswith(".asm.txt"):
                return os.path.join(root, f)
    return None


def sanitize_student_code(code):
    """
    Removes boilerplate that the harness already provides, so students who
    submit a full runnable program are not penalized for it:
      - .data sections (everything from .data up to the next .text)
      - .text and .globl main directives
      - the lowercase main: label (an instruction on the same line is kept)

    SPIM labels are case-sensitive, so only the exact label 'main' collides
    with the harness. Labels such as 'Main:' are left untouched so that any
    jumps to them in the student's code still resolve.
    """
    cleaned = []
    in_data = False
    for line in code.splitlines():
        head = line.split("#", 1)[0].strip()
        head_lower = head.lower()
        if head_lower.startswith(".data"):
            in_data = True
            continue
        if head_lower.startswith(".text"):
            in_data = False
            continue
        if in_data:
            continue
        if re.match(r"^\.globl\s+main\b", head):
            continue
        m = re.match(r"^\s*main\s*:\s*(.*)$", line)
        if m:
            rest = m.group(1)
            if rest.strip() and not rest.strip().startswith("#"):
                cleaned.append(rest)
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def check_assignment_rules(code):
    """
    Enforces the assignment's grading rules and returns (score_factor, notes).
      - No procedure calls (no jal) => score_factor 0.0 (total score of zero).
    The notes are shown only to instructors, in red.
    """
    notes = []
    factor = 1.0
    code_no_comments = "\n".join(l.split("#", 1)[0] for l in code.splitlines())
    if not re.search(r"\bjal\b", code_no_comments):
        notes.append("No 'jal' found: procedure execution not used. "
                     "Assignment rule: total score of zero even if tests pass.")
        factor = 0.0
    elif not re.search(r"\bjr\b", code_no_comments):
        notes.append("No 'jr' found: procedure return may not be used (manual review).")
    return factor, notes

def build_harness(mips_code, s0_val, s1_val, s2_val, array_vals):
    """
    Generates a complete MIPS test harness assembly program.
    Maps the nominal addresses in $s0 (A) and $s1 (B) into a safe memory
    buffer, initializes array A, resets temporaries so the code starts from
    a clean register state, executes the MIPS code, and then prints the n
    elements of array B from B's original base address.
    """
    # Relative mapping of both arrays into __Memory to avoid SPIM crashes
    min_val = min(s0_val, s1_val)

    # Mapped offsets from __Memory (1000 byte safety margin)
    offset_s0 = s0_val - min_val + 1000
    offset_s1 = s1_val - min_val + 1000

    # Store word instructions to initialize array A at $s0
    sw_instructions = []
    for idx, val in enumerate(array_vals):
        sw_instructions.append(f"    li $t0, {val}")
        sw_instructions.append(f"    sw $t0, {idx * 4}($s0)")
    sw_initialization = "\n".join(sw_instructions)

    # Reset temporaries, arguments and return registers to zero so the graded
    # code sees the same clean state it would in a freshly started simulator.
    reset_regs = "\n".join(
        f"    li ${r}, 0" for r in
        ["t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9",
         "a0", "a1", "a2", "a3", "v0", "v1"]
    )

    harness = f"""\
.data
.align 2
__Memory:
.space 20000

__b_msg: .asciiz "B:\\n"
__newline_msg: .asciiz "\\n"

.text
.globl main
main:
    # Set up register inputs using relative mapped addresses
    la $s0, __Memory
    addi $s0, $s0, {offset_s0}

    la $s1, __Memory
    addi $s1, $s1, {offset_s1}

    li $s2, {s2_val}

    # Initialize array A in memory
{sw_initialization}

    # Clean register state before graded code runs
{reset_regs}

    # Execute student/instructor MIPS code
{mips_code}

    # Print "B:\\n"
    li $v0, 4
    la $a0, __b_msg
    syscall

    # Load original B base address (independent of any changes to $s1)
    la $t1, __Memory
    addi $t1, $t1, {offset_s1}

    # Print exactly n elements of B
    li $t2, {s2_val}
    li $t3, 0
__print_b_loop:
    bge $t3, $t2, __print_b_done

    lw $a0, 0($t1)
    li $v0, 1
    syscall

    li $v0, 4
    la $a0, __newline_msg
    syscall

    addi $t1, $t1, 4
    addi $t3, $t3, 1
    j __print_b_loop

__print_b_done:
    # Clean exit
    li $v0, 10
    syscall
"""
    return harness


def run_spim(asm_path, timeout_seconds=5):
    """
    Executes the specified assembly file in SPIM and returns stdout combined with stderr.
    Throws TimeoutError or RuntimeError on failure.
    """
    try:
        run = subprocess.run(
            ["spim", "-file", asm_path],
            capture_output=True,
            text=True,
            timeout=timeout_seconds
        )
        return run.stdout + run.stderr
    except subprocess.TimeoutExpired as e:
        raise TimeoutError(f"SPIM execution timed out after {timeout_seconds} seconds.") from e
    except Exception as e:
        raise RuntimeError(f"Failed to execute SPIM: {str(e)}") from e


def check_spim_errors(spim_output):
    """
    Checks SPIM output for compiler or execution errors.
    Returns a string containing the error lines if found, or None if clean.
    """
    error_lines = []
    for line in spim_output.splitlines():
        # Skip standard exception file loading logs
        if "exceptions.s" in line or "Loaded:" in line:
            continue

        lower_line = line.lower()
        if (
            "error" in lower_line or
            "exception" in lower_line or
            "attempt to" in lower_line or
            "undefined symbol" in lower_line or
            "spim:" in lower_line
        ):
            error_lines.append(line.strip())

    if error_lines:
        return "\n".join(error_lines)
    return None


def parse_output(spim_output, n):
    """
    Parses the SPIM output to extract the n elements of array B.
    """
    b_index = spim_output.find("B:")
    if b_index == -1:
        raise ValueError("Could not find 'B:' in SPIM output.")

    b_part = spim_output[b_index + 2:]
    b_elements = [int(x) for x in re.findall(r"-?\d+", b_part)]

    if len(b_elements) < n:
        raise ValueError(f"Expected {n} elements in B, but only parsed {len(b_elements)}.")

    return b_elements[:n]


def grade_testcase(test_case, student_code):
    """
    Runs a single test case. Builds and executes harnesses for both the
    professor's solution and the student's solution, then compares the output.
    """
    s0 = test_case["s0"]
    s1 = test_case["s1"]
    s2 = test_case["s2"]
    array = test_case["array"]
    name = test_case["name"]

    # 1. Instructor Oracle Execution
    prof_harness = build_harness(PROF_SOLUTION, s0, s1, s2, array)
    prof_asm_path = f"/tmp/prof_harness_{s0}_{s1}_{s2}.asm"
    prof_output = ""
    try:
        with open(prof_asm_path, "w") as f:
            f.write(prof_harness)
        prof_output = run_spim(prof_asm_path)

        prof_error = check_spim_errors(prof_output)
        if prof_error:
            raise RuntimeError(f"Oracle solution run produced error:\n{prof_error}")

        prof_b = parse_output(prof_output, s2)
    except Exception as e:
        cleaned_output = prof_output.strip() if prof_output else ""
        student_res = {
            "name": name,
            "score": 0.0,
            "max_score": 1.0,
            "status": "failed",
            "output": "Fail"
        }
        instructor_detail = f"Internal Error executing instructor solution: {str(e)}\n\nSPIM Output:\n{cleaned_output}"
        return student_res, instructor_detail
    finally:
        if os.path.exists(prof_asm_path):
            try:
                os.remove(prof_asm_path)
            except:
                pass

    # 2. Student Submission Execution
    student_harness = build_harness(sanitize_student_code(student_code), s0, s1, s2, array)
    student_asm_path = f"/tmp/student_harness_{s0}_{s1}_{s2}.asm"
    student_output = ""
    try:
        with open(student_asm_path, "w") as f:
            f.write(student_harness)
        student_output = run_spim(student_asm_path)

        student_error = check_spim_errors(student_output)
        if student_error:
            raise RuntimeError(f"SPIM error during execution:\n{student_error}")

        student_b = parse_output(student_output, s2)
    except Exception as e:
        cleaned_output = student_output.strip() if student_output else ""
        student_res = {
            "name": name,
            "score": 0.0,
            "max_score": 1.0,
            "status": "failed",
            "output": "Fail"
        }
        instructor_detail = f"Execution/Parsing failed.\nError: {str(e)}\n\nSPIM Output:\n{cleaned_output}"
        return student_res, instructor_detail
    finally:
        if os.path.exists(student_asm_path):
            try:
                os.remove(student_asm_path)
            except:
                pass

    # 3. Compare Results
    if student_b == prof_b:
        student_res = {
            "name": name,
            "score": 1.0,
            "max_score": 1.0,
            "status": "passed",
            "output": "Pass"
        }
        instructor_detail = (
            f"Pass.\n"
            f"Correct output B: {student_b}"
        )
    else:
        details = []
        for idx, (exp, got) in enumerate(zip(prof_b, student_b)):
            if exp != got:
                details.append(f"B[{idx}] (address {s1 + 4 * idx}): Expected {exp}, Got {got}")
        output_details = "\n".join(details)
        student_res = {
            "name": name,
            "score": 0.0,
            "max_score": 1.0,
            "status": "failed",
            "output": "Fail"
        }
        instructor_detail = (
            f"Mismatch in results:\n"
            f"Expected B: {prof_b}\n"
            f"Got B:      {student_b}\n\n"
            f"Details:\n{output_details}"
        )

    return student_res, instructor_detail


def build_instructor_notes_entry(code_notes, score_factor):
    """
    Builds a hidden Gradescope test entry that only instructors can see.
    Violations are rendered in red on a highlighted background.
    """
    if code_notes:
        items = "".join(f"<li>{n}</li>" for n in code_notes)
        if score_factor == 0.0:
            action = "ALL AUTOMATED TEST SCORES SET TO 0."
        elif score_factor != 1.0:
            action = f"ALL AUTOMATED TEST SCORES MULTIPLIED BY {score_factor}."
        else:
            action = "No score change applied."
        html = (
            '<div style="color:#b00020;background:#ffe5e5;border:3px solid #b00020;'
            'padding:10px;font-weight:bold;font-size:1.1em;">'
            '&#9888; ASSIGNMENT RULE VIOLATION &#9888;<br>'
            f'{action}<ul style="margin-top:6px;">{items}</ul></div>'
        )
    else:
        html = (
            '<div style="color:#1b5e20;background:#e8f5e9;border:2px solid #1b5e20;'
            'padding:8px;font-weight:bold;">'
            'Assignment rule check passed: no forbidden instructions, procedure calls present.</div>'
        )
    return {
        "name": "Instructor Notes (hidden from students)",
        "score": 0.0,
        "max_score": 0.0,
        "visibility": "hidden",
        "output_format": "html",
        "output": html
    }


def main():
    # Identify student submission file
    student_file = find_student_submission()

    test_results = []
    instructor_logs = []
    code_notes = []
    score_factor = 1.0

    if student_file is None:
        # Build failing results for all test cases if no file was found
        for tc in TEST_CASES:
            msg = "No student MIPS submission file (.asm or .asm.txt) was found in /autograder/submission/."
            test_results.append({
                "name": tc["name"],
                "score": 0.0,
                "max_score": 1.0,
                "status": "failed",
                "output": "Fail"
            })
            instructor_logs.append((tc["name"], msg))
    else:
        try:
            with open(student_file, "r", encoding="utf-8", errors="ignore") as f:
                student_code = f.read()

            score_factor, code_notes = check_assignment_rules(student_code)

            # Grade each test case
            for tc in TEST_CASES:
                res, detail = grade_testcase(tc, student_code)
                test_results.append(res)
                instructor_logs.append((tc["name"], detail))

        except Exception as e:
            # General file read or processing error
            for tc in TEST_CASES:
                test_results.append({
                    "name": tc["name"],
                    "score": 0.0,
                    "max_score": 1.0,
                    "status": "failed",
                    "output": "Fail"
                })
                instructor_logs.append((tc["name"], f"Failed to read submission file: {str(e)}"))

    # Apply assignment-rule penalty to every automated test
    if score_factor != 1.0:
        for res in test_results:
            res["score"] = round(res["score"] * score_factor, 2)
            if res["score"] < res["max_score"]:
                res["status"] = "failed"
                if score_factor == 0.0:
                    res["output"] = "Fail. Score set to 0: assignment rule violated (see instructor notes)."
                else:
                    res["output"] = f"Score reduced to {int(score_factor * 100)}%: assignment rule violated (see instructor notes)."

    # Instructor-only entry (visibility hidden => never shown to students).
    # Rendered as HTML so violations appear as a red highlighted banner.
    test_results.append(build_instructor_notes_entry(code_notes, score_factor))

    # Calculate final cumulative score
    total_score = round(sum(res["score"] for res in test_results), 2)

    results = {
        "score": total_score,
        "stdout_visibility": "hidden",
        "tests": test_results
    }

    # Write Gradescope JSON results
    results_dir = "/autograder/results"
    if not os.path.exists(results_dir):
        try:
            os.makedirs(results_dir, exist_ok=True)
        except Exception:
            # Fallback to local directory for debugging/local testing
            results_dir = "./results"
            os.makedirs(results_dir, exist_ok=True)

    results_path = os.path.join(results_dir, "results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

    print("=================== INSTRUCTOR DETAILS ===================")
    if code_notes:
        print("!" * 70)
        print("!!!  ASSIGNMENT RULE VIOLATION  !!!")
        for note in code_notes:
            print(f"!!!  {note}")
        if score_factor == 0.0:
            print("!!!  ALL AUTOMATED TEST SCORES SET TO 0.")
        elif score_factor != 1.0:
            print(f"!!!  ALL AUTOMATED TEST SCORES MULTIPLIED BY {score_factor}.")
        print("!" * 70)
        print()
    else:
        print("Assignment rule check passed: no violations detected.")
        print()
    for name, detail in instructor_logs:
        print(f"--- {name} ---")
        print(detail)
        print()
    print("==========================================================")

    print(f"Grading complete. Results written to {results_path}")
    print(f"Total Score: {total_score}/{len(TEST_CASES)}")


if __name__ == "__main__":
    main()
