#!/usr/bin/env python3
"""
Gradescope Autograder for MIPS Assignment (Question 3)
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
# A - $s0, B - $s2, n1 - $s1, n2 - $s3

Main: addi $t1, $zero, 1
      sw $t1, 0($s2)

Init: addi $s0, $s0, 4

For:  bge $t1, $s1, End
      addi $s3, $t1, 0

C_exp:
      lw $a0, 0($s0)
      addi $a1, $t1, 0
      jal F_exp

C_App:
      addi $a2, $v0, 0
      addi $a1, $s3, 0
      addi $a0, $s2, 0
      jal F_app

j_up:
      addi $t1, $t1, 1
      addi $s0, $s0, 4
      j For

End:
      addi $s3, $s3, 1
      j Exit

F_exp:
      addi $v0, $a0, 0
      addi $t8, $zero, 1

loop:
      bge $t8, $a1, Ret1
      mult $v0, $a0
      mflo $v0
      addi $t8, $t8, 1
      j loop

Ret1:
      jr $ra

F_app:
      sll $t9, $a1, 2
      add $t9, $t9, $a0
      sw $a2, 0($t9)

Ret2:
      jr $ra

Exit:
"""

# ----------------------------------------------------------------------
# Hidden Test Cases
# ----------------------------------------------------------------------
TEST_CASES = [
    {
        "name": "Test Case 1",
        "s0": 4000,
        "s1": 5,
        "s2": 8000,
        "s3": 0,
        "array": [10, 5, -5, -2, 0]
    },
    {
        "name": "Test Case 2",
        "s0": 13800,
        "s1": 1,
        "s2": 13804,
        "s3": 0,
        "array": [-8]
    },
    {
        "name": "Test Case 3",
        "s0": 8016,
        "s1": 10,
        "s2": 8000,
        "s3": 0,
        "array": [-5, 8, 4, -6, 6, 0, -3, -2, 2, -2]
    },
    {
        "name": "Test Case 4",
        "s0": 2648,
        "s1": 8,
        "s2": 2648,
        "s3": 0,
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


def build_harness(mips_code, s0_val, s1_val, s2_val, s3_val, array_vals):
    """
    Generates a complete MIPS test harness assembly program.
    Initializes input register values, builds input array A in memory relative to $s0,
    executes the provided MIPS instruction sequence, and then prints the final $s2,
    $s3, and the generated elements of array P.
    """
    # Calculate min_val for relative mapping of both arrays to avoid crashes in SPIM
    min_val = min(s0_val, s2_val)
    
    # Mapped offsets from __Memory (1000 byte safety margin)
    offset_s0 = s0_val - min_val + 1000
    offset_s2 = s2_val - min_val + 1000
    
    # Generate the store word instructions to initialize Array A at $s0
    sw_instructions = []
    for idx, val in enumerate(array_vals):
        sw_instructions.append(f"    li $t0, {val}")
        sw_instructions.append(f"    sw $t0, {idx * 4}($s0)")
    sw_initialization = "\n".join(sw_instructions)
    
    harness = f"""\
.data
.align 2
__Memory:
.space 20000

__s2_msg: .asciiz "S2: "
__s3_msg: .asciiz "\\nS3: "
__p_msg: .asciiz "\\nP:\\n"
__newline_msg: .asciiz "\\n"

.text
.globl main
main:
    # Set up register inputs using relative mapped addresses
    la $s0, __Memory
    addi $s0, $s0, {offset_s0}
    
    la $s2, __Memory
    addi $s2, $s2, {offset_s2}
    
    li $s1, {s1_val}
    li $s3, {s3_val}
    
    # Initialize array A in memory
{sw_initialization}

    # Execute student/instructor MIPS code
{mips_code}

    # Save final results before syscalls (which modify $a0, $v0)
    move $s6, $s2  # Final value of $s2
    move $s7, $s3  # Final value of $s3

    # Print "S2: "
    li $v0, 4
    la $a0, __s2_msg
    syscall

    # Map s2 back to nominal value: final_s2 - __Memory - 1000 + min_val
    la $t0, __Memory
    sub $t1, $s6, $t0
    addi $t1, $t1, -1000
    addi $t1, $t1, {min_val}

    # Print nominal s2
    li $v0, 1
    move $a0, $t1
    syscall

    # Print "S3: "
    li $v0, 4
    la $a0, __s3_msg
    syscall

    # Print final s3
    li $v0, 1
    move $a0, $s7
    syscall

    # Print "P:\\n"
    li $v0, 4
    la $a0, __p_msg
    syscall

    # Load initial P base address
    la $t1, __Memory
    addi $t1, $t1, {offset_s2}
    
    # Load s3 (size)
    move $t2, $s7
    
    # Guard: if s3 <= 0, don't print anything
    blez $t2, __print_p_done
    
    # Guard: if s3 > 100, cap it at 100 to prevent infinite loops
    li $t8, 100
    ble $t2, $t8, __start_print
    move $t2, $t8
    
__start_print:
    li $t3, 0
__print_p_loop:
    bge $t3, $t2, __print_p_done
    
    # Load and print element
    lw $a0, 0($t1)
    li $v0, 1
    syscall
    
    # Print newline
    li $v0, 4
    la $a0, __newline_msg
    syscall
    
    # Increment P address pointer and loop counter
    addi $t1, $t1, 4
    addi $t3, $t3, 1
    j __print_p_loop
    
__print_p_done:
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


def parse_output(spim_output):
    """
    Parses the SPIM output to extract:
    - final nominal value of $s2
    - final value of $s3
    - array P elements
    """
    s2_match = re.search(r"S2:\s*(-?\d+)", spim_output)
    if not s2_match:
        raise ValueError("Could not find 'S2:' in SPIM output.")
    s2 = int(s2_match.group(1))

    s3_match = re.search(r"S3:\s*(-?\d+)", spim_output)
    if not s3_match:
        raise ValueError("Could not find 'S3:' in SPIM output.")
    s3 = int(s3_match.group(1))

    p_index = spim_output.find("P:")
    if p_index == -1:
        raise ValueError("Could not find 'P:' in SPIM output.")
    
    p_part = spim_output[p_index:]
    p_elements = [int(x) for x in re.findall(r"-?\d+", p_part)]
    
    if s3 < 0:
        return s2, s3, []
        
    if len(p_elements) < s3:
        raise ValueError(f"Expected {s3} elements in P, but only parsed {len(p_elements)}.")
        
    return s2, s3, p_elements[:s3]


def grade_testcase(test_case, student_code):
    """
    Runs a single test case. Builds and executes harnesses for both the
    professor's solution and the student's solution, then compares the output.
    """
    s0 = test_case["s0"]
    s1 = test_case["s1"]
    s2 = test_case["s2"]
    s3 = test_case["s3"]
    array = test_case["array"]
    name = test_case["name"]

    # 1. Instructor Oracle Execution
    prof_harness = build_harness(PROF_SOLUTION, s0, s1, s2, s3, array)
    prof_asm_path = f"/tmp/prof_harness_{s0}_{s1}.asm"
    prof_output = ""
    try:
        with open(prof_asm_path, "w") as f:
            f.write(prof_harness)
        prof_output = run_spim(prof_asm_path)
        
        prof_error = check_spim_errors(prof_output)
        if prof_error:
            raise RuntimeError(f"Oracle solution run produced error:\n{prof_error}")
            
        prof_s2, prof_s3, prof_p = parse_output(prof_output)
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
    student_harness = build_harness(student_code, s0, s1, s2, s3, array)
    student_asm_path = f"/tmp/student_harness_{s0}_{s1}.asm"
    student_output = ""
    try:
        with open(student_asm_path, "w") as f:
            f.write(student_harness)
        student_output = run_spim(student_asm_path)
        
        student_error = check_spim_errors(student_output)
        if student_error:
            raise RuntimeError(f"SPIM error during execution:\n{student_error}")
            
        student_s2, student_s3, student_p = parse_output(student_output)
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
    s2_match = (student_s2 == prof_s2)
    s3_match = (student_s3 == prof_s3)
    p_match = (student_p == prof_p)
    
    if s2_match and s3_match and p_match:
        student_res = {
            "name": name,
            "score": 1.0,
            "max_score": 1.0,
            "status": "passed",
            "output": "Pass"
        }
        instructor_detail = (
            f"Pass.\n"
            f"Correct output $s2: {student_s2}\n"
            f"Correct output $s3: {student_s3}\n"
            f"Correct output P: {student_p}"
        )
    else:
        details = []
        if not s2_match:
            details.append(f"$s2 mismatch: Expected {prof_s2}, Got {student_s2}")
        if not s3_match:
            details.append(f"$s3 mismatch: Expected {prof_s3}, Got {student_s3}")
        if not p_match:
            details.append(f"P array mismatch: Expected {prof_p}, Got {student_p}")
            
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
            f"Expected: $s2={prof_s2}, $s3={prof_s3}, P={prof_p}\n"
            f"Got:      $s2={student_s2}, $s3={student_s3}, P={student_p}\n\n"
            f"Details:\n{output_details}"
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
