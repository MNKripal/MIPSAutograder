#!/usr/bin/env python3
"""
Gradescope Autograder for MIPS Assignment (Question 5)
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
Main:
    add $t0,$s0,$s1
    bge $t0,$zero,Sub
    sub $t0,$zero,$t0

Sub:
    sub $t1,$s0,$s1
    bge $t1,$zero,Args
    sub $t1,$zero,$t1

Args:
    addi $a0,$t0,0
    addi $a1,$t1,0
    jal Recursion

    mult $v0,$s0
    mflo $t2

Second:
    addi $a0,$t1,0
    addi $a1,$t0,0
    jal Recursion

    mult $v0,$s1
    mflo $t3

Result:
    sub $s2,$t2,$t3
    j Exit

Recursion:
    bgt $a0,$zero,XPos
    bgt $a1,$zero,YPos

BothLess:
    addi $v0,$zero,0
    jr $ra

YPos:
    addi $v0,$a1,0
    jr $ra

XPos:
    bgt $a1,$zero,BothPos
    addi $v0,$a0,0
    jr $ra

BothPos:
    addi $sp,$sp,-16

    sw $ra,12($sp)
    sw $a1,8($sp)
    sw $a0,4($sp)

    addi $a0,$a0,-1
    jal Recursion

    sw $v0,0($sp)

    lw $a0,4($sp)
    lw $a1,8($sp)

    addi $a1,$a1,-1
    jal Recursion

    lw $t8,0($sp)
    add $v0,$v0,$t8

    lw $ra,12($sp)

    addi $sp,$sp,16

    jr $ra

Exit:
"""

# ----------------------------------------------------------------------
# Hidden Test Cases
# ----------------------------------------------------------------------
TEST_CASES = [
    {
        "name": "Test Case 1",
        "s0": 1,
        "s1": 2,
        "s2": 0
    },
    {
        "name": "Test Case 2",
        "s0": 4,
        "s1": 2,
        "s2": 0
    },
    {
        "name": "Test Case 3",
        "s0": 230,
        "s1": 230,
        "s2": 0
    },
    {
        "name": "Test Case 4",
        "s0": 4,
        "s1": 0,
        "s2": 0
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
    prof_asm_path = f"/tmp/prof_harness_{s0}_{s1}.asm"
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
    student_harness = build_harness(student_code, s0, s1, s2)
    student_asm_path = f"/tmp/student_harness_{s0}_{s1}.asm"
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
