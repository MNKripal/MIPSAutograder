#!/usr/bin/env python3
"""
Gradescope Autograder for MIPS Assignment (Question 1)
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
lw $t0, 0($s0)
lw $t1, 4($s0)

multu $t0, $t1
mflo $t2
mfhi $t3

sw $t2, 16($s0)
sw $t3, 8($s0)

addi $t5, $zero, 230
div $t2, $t5
mflo $t4
mfhi $t5

sw $t4, 20($s0)

srl $t6, $t5, 16
andi $t7, $t5, 8
ori $t8, $t6, 3
or $t7, $t7, $t8
sll $t9, $t5, 2

sh $t9, 24($s0)
sb $t7, 26($s0)
sb $t6, 27($s0)

add $t5, $t0, $t1
addi $t5, $t5, -100
add $t6, $t3, $t2
sub $t6, $t6, $t4
sub $t6, $t5, $t6

sw $t6, 12($s0)
"""

# ----------------------------------------------------------------------
# Hidden Test Cases
# ----------------------------------------------------------------------
TEST_CASES = [
    {"name": "Test Case 1", "a0": 4, "a1": 5},
    {"name": "Test Case 2", "a0": -8, "a1": -4},
    {"name": "Test Case 3", "a0": -5, "a1": 8},
    {"name": "Test Case 4", "a0": 5, "a1": -8}
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


def build_harness(mips_code, a0, a1):
    """
    Generates a complete MIPS test harness assembly program.
    The harness initializes array A with test case values, executes
    the given MIPS code, and then prints A[0] through A[6] separated by spaces.
    """
    harness = f"""\
.data
A:
.word {a0}
.word {a1}
.space 20

.text
.globl main
main:
    la $s0, A

{mips_code}

    # Print A[0]
    lw $a0, 0($s0)
    li $v0, 1
    syscall

    # Print space
    li $a0, 32
    li $v0, 11
    syscall

    # Print A[1]
    lw $a0, 4($s0)
    li $v0, 1
    syscall

    # Print space
    li $a0, 32
    li $v0, 11
    syscall

    # Print A[2]
    lw $a0, 8($s0)
    li $v0, 1
    syscall

    # Print space
    li $a0, 32
    li $v0, 11
    syscall

    # Print A[3]
    lw $a0, 12($s0)
    li $v0, 1
    syscall

    # Print space
    li $a0, 32
    li $v0, 11
    syscall

    # Print A[4]
    lw $a0, 16($s0)
    li $v0, 1
    syscall

    # Print space
    li $a0, 32
    li $v0, 11
    syscall

    # Print A[5]
    lw $a0, 20($s0)
    li $v0, 1
    syscall

    # Print space
    li $a0, 32
    li $v0, 11
    syscall

    # Print A[6]
    lw $a0, 24($s0)
    li $v0, 1
    syscall

    # Clean exit
    li $v0, 10
    syscall
"""
    return harness


def run_spim(asm_path, timeout_seconds=5):
    """
    Executes the specified assembly file in SPIM and returns stdout combined with stderr.
    Throws TimeoutExpired or RuntimeError on failure.
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


def parse_memory_dump(spim_output):
    """
    Parses the SPIM stdout/stderr output and extracts the last 7 integers.
    """
    # Extract all integer patterns (positive and negative)
    nums = [int(x) for x in re.findall(r"-?\d+", spim_output)]
    if len(nums) < 7:
        raise ValueError(f"Could not parse 7 printed values from SPIM output. Total integers found: {len(nums)}")
    return nums[-7:]


def grade_testcase(test_case, student_code):
    """
    Runs a single test case. Builds and executes harnesses for both the
    professor's solution and the student's solution, then compares the output.
    """
    a0 = test_case["a0"]
    a1 = test_case["a1"]
    name = test_case["name"]

    # 1. Instructor Oracle Execution
    prof_harness = build_harness(PROF_SOLUTION, a0, a1)
    prof_asm_path = f"/tmp/prof_harness_{a0}_{a1}.asm"
    prof_output = ""
    try:
        with open(prof_asm_path, "w") as f:
            f.write(prof_harness)
        prof_output = run_spim(prof_asm_path)
        
        prof_error = check_spim_errors(prof_output)
        if prof_error:
            raise RuntimeError(f"Oracle solution run produced error:\n{prof_error}")
            
        prof_values = parse_memory_dump(prof_output)
    except Exception as e:
        cleaned_output = prof_output.strip() if prof_output else ""
        student_res = {
            "name": name,
            "score": 0,
            "max_score": 1,
            "status": "failed",
            "output": "Internal Error."
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
    student_harness = build_harness(student_code, a0, a1)
    student_asm_path = f"/tmp/student_harness_{a0}_{a1}.asm"
    student_output = ""
    try:
        with open(student_asm_path, "w") as f:
            f.write(student_harness)
        student_output = run_spim(student_asm_path)
        
        student_error = check_spim_errors(student_output)
        if student_error:
            raise RuntimeError(f"SPIM error during execution:\n{student_error}")
            
        student_values = parse_memory_dump(student_output)
    except Exception as e:
        cleaned_output = student_output.strip() if student_output else ""
        student_res = {
            "name": name,
            "score": 0,
            "max_score": 1,
            "status": "failed",
            "output": "Execution failed."
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
    # The 5 register memory values to check are at offsets 8, 12, 16, 20, 24.
    # These correspond to indices 2, 3, 4, 5, 6 in student_values and prof_values.
    correct_count = sum(1 for i in range(2, 7) if student_values[i] == prof_values[i])
    score = round(correct_count * 0.2, 2)
    status = "passed" if score == 1.0 else "failed"

    details = []
    offsets = [8, 12, 16, 20, 24]
    for idx, offset in enumerate(offsets, start=2):
        student_val = student_values[idx]
        prof_val = prof_values[idx]
        element_idx = idx
        if student_val == prof_val:
            details.append(f"A[{element_idx}] (offset {offset}): Correct ({student_val})")
        else:
            details.append(f"A[{element_idx}] (offset {offset}): Incorrect. Expected {prof_val}, Got {student_val}")
            
    output_details = "\n".join(details)
    
    if score == 1.0:
        student_res = {
            "name": name,
            "score": 1.0,
            "max_score": 1,
            "status": "passed",
            "output": "Pass."
        }
        instructor_detail = f"Pass.\nCorrect memory output: {student_values}\n\nMemory Details:\n{output_details}"
    else:
        student_res = {
            "name": name,
            "score": score,
            "max_score": 1,
            "status": "failed",
            "output": "Fail."
        }
        instructor_detail = (
            f"Mismatch in memory values.\n"
            f"Expected: {prof_values}\n"
            f"Got:      {student_values}\n\n"
            f"Memory Details:\n{output_details}"
        )
    return student_res, instructor_detail


def main():
    # Identify student submission file
    student_file = find_student_submission()
    
    test_results = []
    instructor_logs = []
    
    if student_file is None:
        # Build failing results for all test cases if no file was found
        for tc in TEST_CASES:
            msg = "No student MIPS submission file (.asm or .asm.txt) was found in /autograder/submission/."
            test_results.append({
                "name": tc["name"],
                "score": 0,
                "max_score": 1,
                "status": "failed",
                "output": msg
            })
            instructor_logs.append((tc["name"], msg))
    else:
        try:
            with open(student_file, "r", encoding="utf-8", errors="ignore") as f:
                student_code = f.read()
            
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
                    "score": 0,
                    "max_score": 1,
                    "status": "failed",
                    "output": "Failed to read submission file."
                })
                instructor_logs.append((tc["name"], f"Failed to read submission file: {str(e)}"))

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
    for name, detail in instructor_logs:
        print(f"--- {name} ---")
        print(detail)
        print()
    print("==========================================================")
    
    print(f"Grading complete. Results written to {results_path}")
    print(f"Total Score: {total_score}/{len(TEST_CASES)}")


if __name__ == "__main__":
    main()
