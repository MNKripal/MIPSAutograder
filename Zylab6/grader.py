#!/usr/bin/env python3
"""
Gradescope Autograder for MIPS Assignment (Question 6)
Shift-and-add recursive multiplication.
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
# Assign Arguments
Main: addi $a0, $s0, 0
      addi $a1, $s1, 0
      addi $a2, $s2, 0
      slt $s3, $a1, $zero  # $s3 = 1, if md < 0
      beq $s3, $zero, m    # if md >= 0 skip sub1
sub1: sub $a1, $zero, $a1
m:    slt $s4, $a2, $zero  # $s4 = 1, if m < 0
      beq $s4, $zero, Call # if m >= 0 skip sub2
sub2: sub $a2, $zero, $a2
Call: addi $a3, $zero, 16  # assign n = 16
      jal Pdt              # First Recursive Call
      beq $s3, $s4, same   # if operands have same sign skip neg
      sub $s0, $zero, $v0
      j Exit
same: addi $s0, $v0, 0     # Product = return value
      j Exit

Pdt:  bne $a3, $zero, Next # if n = 0, return
      addi $v0, $a0, 0     # return p
      jr $ra
Next: addi $sp, $sp, -4    # Use stack
      sw $ra, 0($sp)       # Store $ra
      andi $t0, $a2, 1     # m_0
      beq $t0, $zero, task # if LSb == 0, skip p+=md
      add $a0, $a0, $a1    # p = p + md
task: sll $a1, $a1, 1      # md << 1
      srl $a2, $a2, 1      # m >> 1
      addi $a3, $a3, -1    # n--
      jal Pdt
Ret:  lw $ra, 0($sp)       # retrieve $ra
      addi $sp, $sp, 4     # update $sp
      jr $ra

Exit:
"""

# ----------------------------------------------------------------------
# Hidden Test Cases
#   $s0 = product (initialized to 0)
#   $s1 = multiplicand
#   $s2 = multiplier
# ----------------------------------------------------------------------
TEST_CASES = [
    {
        "name": "Test Case 1",
        "s0": 0,
        "s1": 8000,
        "s2": 15000
    },
    {
        "name": "Test Case 2",
        "s0": 0,
        "s1": -230,
        "s2": 11012
    },
    {
        "name": "Test Case 3",
        "s0": 0,
        "s1": -23011,
        "s2": -23012
    },
    {
        "name": "Test Case 4",
        "s0": 0,
        "s1": 23012,
        "s2": -11023
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
      - Use of mult/multu/mul/mulu anywhere => score_factor 0.0 (score of zero).
      - No procedure calls (no jal)         => score_factor 0.5 (half credit).
    The notes are shown only to instructors, in red.
    """
    notes = []
    factor = 1.0
    code_no_comments = "\n".join(l.split("#", 1)[0] for l in code.splitlines())
    if re.search(r"\b(mult|multu|mul|mulu|mulo|mulou)\b", code_no_comments):
        notes.append("Submission uses a multiply instruction (mult/mul). "
                     "Assignment rule: score of zero even if tests pass.")
        factor = 0.0
    if not re.search(r"\bjal\b", code_no_comments):
        notes.append("No 'jal' found: recursive procedure calls not used. "
                     "Assignment rule: only half credit.")
        factor = min(factor, 0.5)
    elif not re.search(r"\bjr\b", code_no_comments):
        notes.append("No 'jr' found: procedure return may not be used (manual review).")
    return factor, notes

def build_harness(mips_code, s0_val, s1_val, s2_val):
    """
    Generates a complete MIPS test harness assembly program.
    Initializes register inputs, executes the student/instructor MIPS code,
    and prints final registers $s0, $s1, $s2.
    """
    harness = f"""\
.data
__s0_prefix: .asciiz "s0: "
__s1_prefix: .asciiz "s1: "
__s2_prefix: .asciiz "s2: "
__newline_msg: .asciiz "\\n"

.text
.globl main
main:
    # Setup initial registers
    li $s0, {s0_val}
    li $s1, {s1_val}
    li $s2, {s2_val}

    # Execute student/instructor code
{mips_code}

    # Save final results before syscalls (which modify $a0, $v0)
    move $s6, $s0
    move $s7, $s1
    move $t4, $s2

    # Print s0
    li $v0, 4
    la $a0, __s0_prefix
    syscall
    move $a0, $s6
    li $v0, 1
    syscall
    li $v0, 4
    la $a0, __newline_msg
    syscall

    # Print s1
    li $v0, 4
    la $a0, __s1_prefix
    syscall
    move $a0, $s7
    li $v0, 1
    syscall
    li $v0, 4
    la $a0, __newline_msg
    syscall

    # Print s2
    li $v0, 4
    la $a0, __s2_prefix
    syscall
    move $a0, $t4
    li $v0, 1
    syscall
    li $v0, 4
    la $a0, __newline_msg
    syscall

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


def parse_registers(spim_output):
    """
    Parses the SPIM output to extract s0, s1, s2 final values.
    """
    registers = {}
    for line in spim_output.splitlines():
        match = re.match(r"^(s0|s1|s2):\s*(-?\d+)", line.strip())
        if match:
            registers[match.group(1)] = int(match.group(2))
    for reg in ["s0", "s1", "s2"]:
        if reg not in registers:
            raise ValueError(f"Could not find register {reg} in SPIM output.")
    return registers


def grade_testcase(test_case, student_code):
    """
    Runs a single test case. Builds and executes harnesses for both the
    professor's solution and the student's solution, then compares the output.
    """
    s0 = test_case["s0"]
    s1 = test_case["s1"]
    s2 = test_case["s2"]
    name = test_case["name"]

    # 1. Instructor Oracle Execution
    prof_harness = build_harness(PROF_SOLUTION, s0, s1, s2)
    prof_asm_path = f"/tmp/prof_harness_{s1}_{s2}.asm"
    prof_output = ""
    try:
        with open(prof_asm_path, "w") as f:
            f.write(prof_harness)
        prof_output = run_spim(prof_asm_path)

        prof_error = check_spim_errors(prof_output)
        if prof_error:
            raise RuntimeError(f"Oracle solution run produced error:\n{prof_error}")

        prof_regs = parse_registers(prof_output)
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
    student_harness = build_harness(sanitize_student_code(student_code), s0, s1, s2)
    student_asm_path = f"/tmp/student_harness_{s1}_{s2}.asm"
    student_output = ""
    try:
        with open(student_asm_path, "w") as f:
            f.write(student_harness)
        student_output = run_spim(student_asm_path)

        student_error = check_spim_errors(student_output)
        if student_error:
            raise RuntimeError(f"SPIM error during execution:\n{student_error}")

        student_regs = parse_registers(student_output)
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
    reg_mismatches = []
    for reg in ["s0", "s1", "s2"]:
        if student_regs[reg] != prof_regs[reg]:
            reg_mismatches.append(f"${reg} mismatch: Expected {prof_regs[reg]}, Got {student_regs[reg]}")

    if not reg_mismatches:
        student_res = {
            "name": name,
            "score": 1.0,
            "max_score": 1.0,
            "status": "passed",
            "output": "Pass"
        }
        instructor_detail = (
            f"Pass.\n"
            f"Correct registers: {student_regs}"
        )
    else:
        output_details = "Register Mismatches:\n" + "\n".join(reg_mismatches)
        student_res = {
            "name": name,
            "score": 0.0,
            "max_score": 1.0,
            "status": "failed",
            "output": "Fail"
        }
        instructor_detail = (
            f"Mismatch in results:\n\n{output_details}"
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
