#!/usr/bin/env python3
"""
Gradescope Autograder for MIPS Assignment (Question 2)
Uses the instructor's MIPS code as the oracle solution.
"""

import json
import os
import subprocess
import re

# ----------------------------------------------------------------------
# Professor's MIPS solution (from Zylab2/MIPSSolution)
# ----------------------------------------------------------------------
PROF_SOLUTION = """\
Main:          addi $t1, $zero, 0	   # i = 0
               addi $s2, $s1, -1
first_loop:    bge $t1, $s1, Exit	   # if i >= size exit
               sll $t3, $t1, 2	   	# i*4
               add $t3, $s0, $t3	      # address of Array[i]
               lw $t4, 0($t3)		      # value of Array[i]
               addi $t2, $t1, 1		   # j = i + 1
second_loop:   bge $t2, $s1, end_while	# if j >= size end second loop
               array_val:     sll $t3, $t2, 2		   # j*4
               add $t3, $s0, $t3	      # address of Array[j]
               lw $t5, 0($t3)		      # value of Array[j]
compare:       beq $t4, $t5, for_start	# if Array[i] = Array[j] enter for loop
               addi $t2, $t2, 1		   # j ++ if values unequal
               j second_loop
for_start:     addi $t8, $t2, 0		   # k = j
for_loop:      bge $t8, $s2, end_for	# if k >= size end for loop               
               sll $t9, $t8, 2		   # k*4
               add $t9, $s0, $t9	      # address of Array[k]
               lw $t7, 4($t9)		      # Value of Array[k+1]
               sw $t7, 0($t9)		      # write to Array[k]
               addi $t8, $t8,1		   # k ++
               j for_loop
end_for:       addi $s1, $s1, -1	      # size -- if duplicate found
               addi $s2, $s1, -1
               j second_loop 
end_while:     addi $t1, $t1, 1		   # i ++
               j first_loop
Exit:
"""

# ----------------------------------------------------------------------
# Hidden Test Cases
# ----------------------------------------------------------------------
TEST_CASES = [
    {
        "name": "Test Case 1",
        "base": 4000,
        "size": 10,
        "array": [4, 8, -13, 8, -13, -13, 0, 8, 4, 0]
    },
    {
        "name": "Test Case 2",
        "base": 13804,
        "size": 4,
        "array": [-8, -4, 4, 8]
    },
    {
        "name": "Test Case 3",
        "base": 8016,
        "size": 9,
        "array": [-50, 80, 100, 0, -80, -50, -100, 0, 100]
    },
    {
        "name": "Test Case 4",
        "base": 10000,
        "size": 5,
        "array": [230, 230, 230, 230, 230]
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


def build_harness(mips_code, base, size, array_vals):
    """
    Generates a complete MIPS test harness assembly program.
    The harness initializes array A with test case values, executes
    the given MIPS code, and then prints the final size and remaining array elements.
    """
    word_declarations = "\n".join(f".word {val}" for val in array_vals)
    
    harness = f"""\
.data
__Array:
{word_declarations}

__size_msg: .asciiz "SIZE: "
__array_msg: .asciiz "\\nARRAY: "
__space_msg: .asciiz " "

.text
.globl main
main:
    la $s0, __Array
    li $s1, {size}

{mips_code}

    # Save final results before syscalls (which modify $a0, $v0)
    move $s3, $s1
    move $s4, $s0

    # Print size prefix
    li $v0, 4
    la $a0, __size_msg
    syscall

    # Print final size
    li $v0, 1
    move $a0, $s3
    syscall

    # Print array elements prefix
    li $v0, 4
    la $a0, __array_msg
    syscall

    # Loop to print array elements
    li $t0, 0
__print_loop:
    bge $t0, $s3, __print_done
    
    sll $t1, $t0, 2
    add $t1, $s4, $t1
    lw $a0, 0($t1)
    
    li $v0, 1
    syscall

    li $v0, 4
    la $a0, __space_msg
    syscall

    addi $t0, $t0, 1
    j __print_loop

__print_done:
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
    - final value of $s1 (size)
    - first $s1 integers remaining in memory (array)
    """
    size_match = re.search(r"SIZE:\s*(-?\d+)", spim_output)
    if not size_match:
        raise ValueError("Could not find 'SIZE:' in SPIM output.")
    size = int(size_match.group(1))
    
    array_match = re.search(r"ARRAY:\s*(.*)", spim_output)
    if not array_match:
        raise ValueError("Could not find 'ARRAY:' in SPIM output.")
    
    array_str = array_match.group(1)
    array_elements = [int(x) for x in re.findall(r"-?\d+", array_str)]
    
    if size < 0:
        return size, []
        
    if len(array_elements) < size:
        raise ValueError(f"Expected {size} array elements, but only parsed {len(array_elements)}.")
        
    return size, array_elements[:size]


def grade_testcase(test_case, student_code):
    """
    Runs a single test case. Builds and executes harnesses for both the
    professor's solution and the student's solution, then compares the output.
    """
    base = test_case["base"]
    size = test_case["size"]
    array = test_case["array"]
    name = test_case["name"]

    # 1. Instructor Oracle Execution
    prof_harness = build_harness(PROF_SOLUTION, base, size, array)
    prof_asm_path = f"/tmp/prof_harness_{base}_{size}.asm"
    prof_output = ""
    try:
        with open(prof_asm_path, "w") as f:
            f.write(prof_harness)
        prof_output = run_spim(prof_asm_path)
        
        prof_error = check_spim_errors(prof_output)
        if prof_error:
            raise RuntimeError(f"Oracle solution run produced error:\n{prof_error}")
            
        prof_size, prof_array = parse_output(prof_output)
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
    student_harness = build_harness(student_code, base, size, array)
    student_asm_path = f"/tmp/student_harness_{base}_{size}.asm"
    student_output = ""
    try:
        with open(student_asm_path, "w") as f:
            f.write(student_harness)
        student_output = run_spim(student_asm_path)
        
        student_error = check_spim_errors(student_output)
        if student_error:
            raise RuntimeError(f"SPIM error during execution:\n{student_error}")
            
        student_size, student_array = parse_output(student_output)
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
    size_match = (student_size == prof_size)
    array_match = (student_array == prof_array)
    
    if size_match and array_match:
        student_res = {
            "name": name,
            "score": 1.0,
            "max_score": 1.0,
            "status": "passed",
            "output": "Pass"
        }
        instructor_detail = (
            f"Pass.\n"
            f"Correct output size: {student_size}\n"
            f"Correct output array: {student_array}"
        )
    else:
        details = []
        if not size_match:
            details.append(f"Size mismatch: Expected {prof_size}, Got {student_size}")
        if not array_match:
            details.append(f"Array mismatch: Expected {prof_array}, Got {student_array}")
            
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
            f"Expected: Size={prof_size}, Array={prof_array}\n"
            f"Got:      Size={student_size}, Array={student_array}\n\n"
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
